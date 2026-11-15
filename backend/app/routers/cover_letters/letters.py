import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.database import get_database
from app.llm.provider_errors import llm_http_exception
from app.models import ApiUsageAction, UserModel
from app.utils import serialize_mongodb_doc

router = APIRouter()


def _pkg():
    return sys.modules[__package__]


class CoverLetterEdit(BaseModel):
    body: str


class RewritePassageRequest(BaseModel):
    letter: str = Field(..., min_length=1, max_length=8000)
    passage: str = Field(..., min_length=1, max_length=2000)
    instruction: str = Field(default="", max_length=500)


@router.get("/applications/{application_id}/cover-letter")
async def get_cover_letter(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(app_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette candidature")

    letter = await db["cover_letters"].find_one({"application_id": ObjectId(application_id)})
    if not letter:
        return {"status": "none"}
    letter.pop("guard_context", None)
    return serialize_mongodb_doc(letter)


@router.post("/applications/{application_id}/cover-letter/regenerate")
async def regenerate_cover_letter(
    application_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    pkg = _pkg()
    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(app_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette candidature")

    await db["cover_letters"].update_one(
        {"application_id": ObjectId(application_id)},
        {"$set": {"status": "pending", "error": None, "updated_at": datetime.now(timezone.utc)}},
    )
    background_tasks.add_task(
        pkg._generate_cover_letter_bg,
        ObjectId(application_id),
        ObjectId(current_user.id),
        db,
    )
    return {"status": "scheduled"}


@router.patch("/applications/{application_id}/cover-letter")
async def edit_cover_letter(
    application_id: str,
    body_data: CoverLetterEdit,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    pkg = _pkg()
    letter = await db["cover_letters"].find_one({"application_id": ObjectId(application_id)})
    if not letter:
        raise HTTPException(status_code=404, detail="Lettre non trouvée")
    if str(letter.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    new_version_num = len(letter.get("versions", [])) + 1
    body = body_data.body
    new_version = {
        "n": new_version_num,
        "body": body,
        "origin": "edited",
        "models": {},
        "created_at": datetime.now(timezone.utc),
    }
    update_set = {"current_version": new_version_num, "updated_at": datetime.now(timezone.utc)}

    guard_context = letter.get("guard_context")
    if guard_context:
        app_doc = await db["applications"].find_one({"_id": letter["application_id"]}) or {}
        report = pkg.evaluate_letter_guards(
            body, app_doc.get("description") or "", guard_context.get("analyst_data") or {}
        )
        current = next(
            (v for v in letter.get("versions", []) if v.get("n") == letter.get("current_version")),
            {},
        )
        if " ".join(body.split()) == " ".join((current.get("body") or "").split()):
            carried = [
                v
                for v in (current.get("guard_report") or {}).get("violations", [])
                if v.startswith("Fidélité :") and v not in report.violations
            ]
            if carried:
                report = report.model_copy(
                    update={"violations": report.violations + carried, "is_blocking": True}
                )
        new_version["guard_report"] = report.model_dump()
        update_set["status"] = "needs_review" if report.is_blocking else "ready"

    await db["cover_letters"].update_one(
        {"_id": letter["_id"]},
        {"$set": update_set, "$push": {"versions": new_version}},
    )
    updated = await db["cover_letters"].find_one({"_id": letter["_id"]})
    updated.pop("guard_context", None)
    return serialize_mongodb_doc(updated)


@router.get("/applications/{application_id}/cover-letter/pdf")
async def get_cover_letter_pdf(
    application_id: str,
    acknowledge_review: bool = False,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Render and download the cover letter as a vector A4 PDF."""
    pkg = _pkg()
    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="ID de candidature invalide")

    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(app_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette candidature")

    letter = await db["cover_letters"].find_one({"application_id": ObjectId(application_id)})
    status = letter.get("status") if letter else None
    if status not in ("ready", "needs_review"):
        raise HTTPException(
            status_code=404, detail="Lettre de motivation non disponible ou non prête"
        )
    if status == "needs_review" and not acknowledge_review:
        raise HTTPException(
            status_code=409,
            detail="Cette lettre contient encore des points à corriger. Confirmez l'export pour la télécharger malgré tout.",
        )

    versions = letter.get("versions") or []
    current_v = letter.get("current_version", 1)
    version_doc = next((v for v in versions if v.get("n") == current_v), None)
    if not version_doc and versions:
        version_doc = versions[-1]
    if not version_doc or not version_doc.get("body"):
        raise HTTPException(status_code=404, detail="Contenu de la lettre introuvable")

    profile_query = [{"user_id": str(current_user.id)}]
    if ObjectId.is_valid(str(current_user.id)):
        profile_query.append({"user_id": ObjectId(current_user.id)})
    profile_doc = await db["candidate_profile"].find_one({"$or": profile_query}) or {}
    candidate = pkg.build_candidate_info(profile_doc, current_user)

    html_content = pkg.render_letter_html(
        body=version_doc["body"],
        candidate=candidate,
        company=app_doc.get("company", "Entreprise"),
        position=app_doc.get("position", ""),
        location=app_doc.get("location"),
    )
    try:
        pdf_bytes = await pkg.generate_cv_pdf(html_content)
    except Exception as e:
        pkg.logger.error(f"Erreur rendu PDF lettre pour application {application_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Échec du rendu PDF de la lettre de motivation.")

    name_slug = pkg.slugify(candidate.get("full_name") or "candidat")
    company_slug = pkg.slugify(app_doc.get("company") or "entreprise")
    raw_pos = (app_doc.get("position") or "").strip()
    filename = (
        f"Lettre_{name_slug}_{pkg.slugify(raw_pos)}_{company_slug}.pdf"
        if raw_pos
        else f"Lettre_{name_slug}_{company_slug}.pdf"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf",
        },
    )


@router.post("/applications/{application_id}/cover-letter/rewrite")
async def rewrite_cover_letter_passage(
    application_id: str,
    payload: RewritePassageRequest,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Rewrite a selected cover-letter passage using a custom instruction."""
    pkg = _pkg()
    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="ID de candidature invalide")

    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(app_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette candidature")

    if not payload.passage.strip() or payload.passage not in payload.letter:
        raise HTTPException(
            status_code=422, detail="Le passage sélectionné est vide ou absent de la lettre"
        )

    await pkg.require_user_quota(db, current_user.id, ApiUsageAction.LETTER_REWRITE)

    job_trackers_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "job_trackers"
        / "src"
        / "job_trackers"
    )
    if str(job_trackers_path) not in sys.path:
        sys.path.insert(0, str(job_trackers_path))
    from cover_letter_crew import RewriteFailedError, rewrite_letter_passage_async

    try:
        result = await rewrite_letter_passage_async(
            letter=payload.letter, passage=payload.passage, instruction=payload.instruction
        )
    except RewriteFailedError:
        raise HTTPException(status_code=502, detail="La réécriture n'a pas abouti, réessayez.")
    except HTTPException:
        raise
    except Exception as e:
        mapped_err = llm_http_exception(e)
        if mapped_err:
            raise mapped_err
        pkg.logger.exception("Échec inattendu de la réécriture de passage pour %s", application_id)
        raise HTTPException(status_code=502, detail="La réécriture n'a pas abouti, réessayez.")

    await pkg.record_api_usage(
        db,
        current_user.id,
        ApiUsageAction.LETTER_REWRITE,
        model=result.get("model"),
        input_tokens=result.get("input_tokens", 0),
        output_tokens=result.get("output_tokens", 0),
        metadata={"application_id": application_id},
    )
    return {"rewritten": result["text"], "warnings": result["warnings"]}
