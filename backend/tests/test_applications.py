from datetime import datetime, timezone, timedelta
import pytest
from app.models import (
    ApplicationStatus,
    JobApplication,
    JobApplicationCreate,
    JobApplicationResponse,
)
from app.routers.applications import enrich_application_with_cadences


def test_cadence_enrichment_unit():
    now = datetime.now(timezone.utc)

    # 1. Candidature envoyée il y a 8 jours -> Relance J+7 due
    date_8_days_ago = (now - timedelta(days=8)).isoformat()
    app_doc = {
        "status": ApplicationStatus.APPLIED.value,
        "application_date": date_8_days_ago,
    }
    enriched = enrich_application_with_cadences(app_doc)
    assert enriched["days_since_application"] >= 8
    assert enriched["follow_up_alert"] == "relance_due"

    # 2. Candidature envoyée il y a 3 jours -> Pas d'alerte
    date_3_days_ago = (now - timedelta(days=3)).isoformat()
    app_doc_recent = {
        "status": ApplicationStatus.APPLIED.value,
        "application_date": date_3_days_ago,
    }
    enriched_recent = enrich_application_with_cadences(app_doc_recent)
    assert enriched_recent["days_since_application"] in (3, 4)
    assert enriched_recent["follow_up_alert"] is None

    # 3. Entretien passé il y a 2 jours -> Remerciement J+1 du
    date_2_days_ago = (now - timedelta(days=2)).isoformat()
    app_doc_interview = {
        "status": ApplicationStatus.INTERVIEW.value,
        "application_date": date_2_days_ago,
    }
    enriched_interview = enrich_application_with_cadences(app_doc_interview)
    assert enriched_interview["follow_up_alert"] == "remerciement_due"

    # 4. Offre reçue / Refusée -> Pas d'alerte
    app_doc_closed = {
        "status": ApplicationStatus.OFFER_RECEIVED.value,
        "application_date": date_8_days_ago,
    }
    enriched_closed = enrich_application_with_cadences(app_doc_closed)
    assert enriched_closed["follow_up_alert"] is None


def test_create_and_get_application_with_offer_id(client, auth_headers):
    # Création d'une candidature liée à une offre
    payload = {
        "company": "Tech Corp",
        "position": "Senior Backend Developer",
        "location": "Paris",
        "status": ApplicationStatus.APPLIED.value,
        "offer_id": "673f1c9d8e5f2a1b3c4d5e6f",
        "description": "Poste orienté microservices Python",
    }
    resp = client.post("/applications/", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    app_id = created["_id"]

    assert created["company"] == "Tech Corp"
    assert created["offer_id"] == "673f1c9d8e5f2a1b3c4d5e6f"
    assert created["days_since_application"] == 0
    assert created["follow_up_alert"] is None

    # Récupération de la liste
    list_resp = client.get("/applications/", headers=auth_headers)
    assert list_resp.status_code == 200
    apps = list_resp.json()
    matching = [a for a in apps if a["_id"] == app_id]
    assert len(matching) == 1
    assert matching[0]["offer_id"] == "673f1c9d8e5f2a1b3c4d5e6f"

    # Récupération unitaire
    get_resp = client.get(f"/applications/{app_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["offer_id"] == "673f1c9d8e5f2a1b3c4d5e6f"

    # Mise à jour
    update_payload = {
        "status": ApplicationStatus.INTERVIEW.value,
        "location": "Paris / Télétravail",
    }
    put_resp = client.put(f"/applications/{app_id}", json=update_payload, headers=auth_headers)
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["status"] == ApplicationStatus.INTERVIEW.value
    assert updated["offer_id"] == "673f1c9d8e5f2a1b3c4d5e6f"

    # Suppression
    del_resp = client.delete(f"/applications/{app_id}", headers=auth_headers)
    assert del_resp.status_code == 204
