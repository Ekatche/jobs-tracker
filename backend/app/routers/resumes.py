import logging
import re
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.database import get_database
from app.models import (
    ApiUsageAction,
    TailoredCVSchema,
    UserModel,
    utcnow_with_timezone,
)
from app.services.cv_pdf_renderer import generate_cv_pdf
from app.services.cv_tailor import DEFAULT_CV_MODEL, generate_tailored_cv_content
from app.services.cv_templates import render_cv_html
from app.services.usage_tracker import record_api_usage, require_user_quota
from app.utils import serialize_mongodb_doc

logger = logging.getLogger(__name__)

resumes_router = APIRouter(prefix="/resumes", tags=["resumes"])


class GenerateResumeRequest(BaseModel):
    offer_id: str
    application_id: Optional[str] = None
    template: str = "sidebar_elegance"
    with_photo: bool = False


class UpdateResumeRequest(BaseModel):
    content: Optional[TailoredCVSchema] = None
    template: Optional[str] = None
    with_photo: Optional[bool] = None


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", cleaned)


@resumes_router.get("")
async def list_resumes(
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all tailored resumes created by the current user."""
    cursor = db["tailored_resumes"].find({"user_id": ObjectId(current_user.id)}).sort("updated_at", -1)
    resumes = await cursor.to_list(length=100)
    return [serialize_mongodb_doc(r) for r in resumes]


@resumes_router.post("/generate")
async def generate_resume(
    request: GenerateResumeRequest,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate a new tailored CV from a job offer and user's profile."""
    # Quota check
    await require_user_quota(db, current_user.id, ApiUsageAction.CV_TAILORING)

    # Validate candidate profile
    profile_query = [{"user_id": str(current_user.id)}]
    if ObjectId.is_valid(str(current_user.id)):
        profile_query.append({"user_id": ObjectId(current_user.id)})
    profile_doc = await db["candidate_profile"].find_one({"$or": profile_query})
    if not profile_doc:
        raise HTTPException(
            status_code=400,
            detail="Profil candidat introuvable. Veuillez compléter votre profil ou importer votre CV."
        )

    # Validate job offer
    if not ObjectId.is_valid(request.offer_id):
        raise HTTPException(status_code=400, detail="Identifiant d'offre invalide.")

    offer_doc = await db["job_offers"].find_one({"_id": ObjectId(request.offer_id)})
    if not offer_doc:
        raise HTTPException(status_code=404, detail="Offre d'emploi non trouvée.")

    # Retrieve optional Bloc B evaluation
    evaluation_doc = await db["offer_evaluations"].find_one({
        "offer_id": ObjectId(request.offer_id),
        "user_id": ObjectId(current_user.id),
    })

    # Generate tailored content
    try:
        tailored_cv = await generate_tailored_cv_content(
            profile=profile_doc,
            offer=offer_doc,
            evaluation=evaluation_doc,
        )
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=f"Erreur de validation du CV: {ve}")
    except Exception as e:
        logger.error(f"Error generating tailored CV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Échec de la génération automatique du CV.")

    # Record API quota usage
    await record_api_usage(
        user_id=current_user.id,
        action=ApiUsageAction.CV_TAILORING,
        model=DEFAULT_CV_MODEL,
        db=db
    )

    # Persist in MongoDB
    now = utcnow_with_timezone()
    resume_doc = {
        "user_id": ObjectId(current_user.id),
        "offer_id": ObjectId(request.offer_id),
        "application_id": ObjectId(request.application_id) if request.application_id and ObjectId.is_valid(request.application_id) else None,
        "target_role": offer_doc.get("title", tailored_cv.target_role_title),
        "target_company": offer_doc.get("company", ""),
        "template": request.template,
        "with_photo": request.with_photo,
        "content": tailored_cv.model_dump(),
        "created_at": now,
        "updated_at": now,
    }

    result = await db["tailored_resumes"].insert_one(resume_doc)
    resume_doc["_id"] = result.inserted_id

    return serialize_mongodb_doc(resume_doc)


@resumes_router.get("/{resume_id}")
async def get_resume(
    resume_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve tailored resume details by ID."""
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="ID de CV invalide.")

    resume = await db["tailored_resumes"].find_one({"_id": ObjectId(resume_id)})
    if not resume:
        raise HTTPException(status_code=404, detail="CV personnalisé non trouvé.")

    if str(resume.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à ce CV.")

    return serialize_mongodb_doc(resume)


@resumes_router.put("/{resume_id}")
async def update_resume(
    resume_id: str,
    request: UpdateResumeRequest,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update tailored resume content, template, or photo preference."""
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="ID de CV invalide.")

    resume = await db["tailored_resumes"].find_one({"_id": ObjectId(resume_id)})
    if not resume:
        raise HTTPException(status_code=404, detail="CV personnalisé non trouvé.")

    if str(resume.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à ce CV.")

    update_fields: Dict[str, Any] = {"updated_at": utcnow_with_timezone()}
    if request.content is not None:
        update_fields["content"] = request.content.model_dump()
    if request.template is not None:
        update_fields["template"] = request.template
    if request.with_photo is not None:
        update_fields["with_photo"] = request.with_photo

    await db["tailored_resumes"].update_one(
        {"_id": ObjectId(resume_id)},
        {"$set": update_fields}
    )

    updated_doc = await db["tailored_resumes"].find_one({"_id": ObjectId(resume_id)})
    return serialize_mongodb_doc(updated_doc)


@resumes_router.get("/{resume_id}/pdf")
async def get_resume_pdf(
    resume_id: str,
    template: Optional[str] = Query(None),
    with_photo: Optional[bool] = Query(None),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Generate and stream a vector A4 PDF of the tailored resume."""
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="ID de CV invalide.")

    resume = await db["tailored_resumes"].find_one({"_id": ObjectId(resume_id)})
    if not resume:
        raise HTTPException(status_code=404, detail="CV personnalisé non trouvé.")

    if str(resume.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à ce CV.")

    # Candidate profile info for contact details & photo
    profile_query = [{"user_id": str(current_user.id)}]
    if ObjectId.is_valid(str(current_user.id)):
        profile_query.append({"user_id": ObjectId(current_user.id)})
    profile_doc = await db["candidate_profile"].find_one({"$or": profile_query}) or {}
    contact_info = profile_doc.get("personal_info") or profile_doc.get("contact") or {}

    candidate = {
        "full_name": contact_info.get("full_name") or profile_doc.get("full_name") or current_user.username,
        "email": contact_info.get("email") or profile_doc.get("email") or current_user.email,
        "phone": contact_info.get("phone") or profile_doc.get("phone"),
        "location": contact_info.get("location") or profile_doc.get("location"),
        "linkedin_url": contact_info.get("linkedin_url") or contact_info.get("linkedin") or profile_doc.get("linkedin_url"),
        "github_url": contact_info.get("github_url") or contact_info.get("github") or profile_doc.get("github_url"),
    }

    chosen_template = template or resume.get("template", "sidebar_elegance")
    chosen_with_photo = with_photo if with_photo is not None else resume.get("with_photo", False)
    photo_url = contact_info.get("photo_url") or profile_doc.get("photo_url")

    # Render HTML
    html_content = render_cv_html(
        cv=resume["content"],
        candidate=candidate,
        template_name=chosen_template,
        with_photo=chosen_with_photo,
        photo_url=photo_url,
    )

    # Render vector PDF
    try:
        pdf_bytes = await generate_cv_pdf(html_content)
    except Exception as e:
        logger.error(f"Failed to render vector PDF for resume {resume_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Échec du rendu PDF du CV.")

    # Slugify filename
    name_slug = _slugify(candidate["full_name"])
    company_slug = _slugify(resume.get("target_company", "offre"))
    filename = f"CV_{name_slug}_{company_slug}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Type": "application/pdf"
        }
    )


@resumes_router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
) -> Dict[str, str]:
    """Delete a tailored CV."""
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="ID de CV invalide.")

    resume = await db["tailored_resumes"].find_one({"_id": ObjectId(resume_id)})
    if not resume:
        raise HTTPException(status_code=404, detail="CV personnalisé non trouvé.")

    if str(resume.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à ce CV.")

    await db["tailored_resumes"].delete_one({"_id": ObjectId(resume_id)})
    return {"status": "deleted"}
