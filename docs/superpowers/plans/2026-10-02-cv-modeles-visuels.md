# Modèles visuels du CV adapté — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter les modèles Classique et Créatif, une couleur d'accent parmi six, moderniser Sidebar Elegance et Executive Minimalist, et prouver par un test PDF réel que les quatre modèles passent les règles ATS.

**Architecture:** Un registre Python (`cv_templates.py`) est la source unique des modèles, des couleurs et des titres de section. Il valide l'API (422) et alimente le rendu Jinja2. Les quatre gabarits partagent des macros (`_macros.html`) et une feuille de base (`base_cv.css`) pilotée par trois variables CSS d'accent. Le frontend lit une constante miroir (`lib/cvTemplates.ts`), vérifiée contre le registre par un test backend.

**Tech Stack:** FastAPI, Pydantic v2 (`Literal`), Jinja2 + markupsafe, Playwright/Chromium (PDF), pdfplumber, pymupdf 1.28, pytest (asyncio_mode=auto), Next.js/React/TypeScript, Tailwind.

**Spec:** `docs/superpowers/specs/2026-10-02-cv-modeles-visuels-design.md` (commit 4b8f711). Les écarts au spec sont listés plus bas, avec leur raison.

## Global Constraints

- **Aucun commit ni push sans demande explicite de l'utilisateur.** Chaque tâche se termine par un point d'arrêt, pas par un commit.
- Fichiers qui portent déjà des modifications non commitées de l'utilisateur :
  - `backend/app/templates/cv/sidebar_elegance.html` : le `page-break-avoid` a été retiré des sections. Ne pas le remettre sur une section, seulement sur chaque poste et chaque projet.
  - `backend/app/models.py` : éditions ciblées uniquement, avec `Edit`, jamais de réécriture.
  - `frontend/src/lib/api.ts` : n'éditer que l'import de la ligne 20 et la zone `resumeApi` (lignes 768-830). `invitation_code` (vers la ligne 447) ne doit pas bouger.
  - Avant de toucher un de ces fichiers : `git diff <fichier>` pour voir l'état actuel.
- Palette exacte, clé → `primary` / `tint` / `line` :
  - `marine` #1e3a8a / #eef2fb / #a9b8e0 (défaut, couleur actuelle) ;
  - `bleu_vert` #0f766e / #e6f2f1 / #99c9c4 ;
  - `ardoise` #4f6d8a / #eff3f7 / #b3c3d3 ;
  - `sauge` #4d6b4f / #eff4ef / #b5c7b6 ;
  - `bordeaux` #8b1e3f / #f8eef1 / #d8a9b7 ;
  - `graphite` #374151 / #f1f2f4 / #c3c7ce.
- Titres de section exacts : « Expérience professionnelle », « Compétences », « Formation », « Langues », « Certifications & habilitations », « Projets », « Centres d'intérêt ».
- On stocke la **clé** de couleur, jamais un code hexadécimal. Le CSS d'accent ne contient que des valeurs du registre.
- Interdits, établis par le spike du 2026-10-02 :
  - `font-variant: small-caps` (casse l'extraction) ;
  - `letter-spacing` supérieur à `.08em` sur du texte ;
  - emoji dans un gabarit ;
  - texte caché (`sr-only`, transparent, 1 px blanc, largeur nulle) ;
  - lettres en CSS `content:` ou en SVG `<text>` ;
  - monogramme écrit en texte.
- Commandes :
  - backend : `cd backend && uv run pytest <fichier> -v` ;
  - frontend : `cd frontend && npm run lint && npm run build`. Il n'y a pas de framework de test frontend.
- Textes visibles de l'interface : en français.

## Review Focus

1. **Ancien document** sans champ `accent`, ou avec `template` à `None` ou inconnu : le CV s'ouvre et se télécharge en marine / Sidebar, sans erreur, côté back comme côté front. Tests : Tâche 1 (`None` au rendu), Tâche 2 (PDF d'un document sans `accent`), Tâche 8 (`resolveTemplateKey` / `resolveAccentKey` partout où on lit un document).
2. **Clics rapides sur plusieurs couleurs** dans l'aperçu : l'aperçu et la base finissent sur la dernière couleur cliquée. Couverture : Tâche 10 (garde `pdfRequestRef`, file `appearanceQueueRef`, init limitée au changement de CV), vérification manuelle en Tâche 11.
3. **Interlettrage** : le nom serré (`-0.03em`) ou les titres espacés (`.08em`) pourraient fusionner ou séparer des lettres à l'extraction. Tests : contrôles « nom en 1re ligne » et « titres présents » du test ATS, Tâches 4 à 7.
4. **Classique avec la photo demandée** (document passé de Sidebar avec photo à Classique) : aucune `<img>`, bouton Photo masqué, choix photo conservé pour les autres modèles. Tests : Tâche 6 (rendu), Tâche 10 (`supportsPhoto`).
5. **Poste coupé entre deux pages** et teinte de la colonne latérale qui déborde sur la page 2. Tests : contrôle « intitulé et 1re puce sur la même page » et PDF d'au moins deux pages (Tâche 4), contrôle visuel (Tâche 11).

## Écarts au spec (à valider à la relecture)

1. Le bloc `:root` d'accent est injecté **après** `base_css`, dans la même chaîne (`Markup(base_css + accent_css)`), et non « en tête du CSS ». Raison : `@import` doit rester la première règle de la feuille, sinon Chromium l'ignore.
2. Les titres standard vivent dans `SECTION_TITLES` (Python), exposé à Jinja comme variable globale `{clé: Markup(titre)}`, et non dans une macro `section_titles`. Raison : le test PDF les importe directement, et `Markup` garde `&` et `'` bruts dans le HTML.
3. Mobilité et disponibilité passent par une macro `mobility_line` en texte, sans icône, et non par `contacts`. Raison : les tests existants exigent la ligne `class="cv-mobility"` jointe par « · ».
4. `TailoredResume.template` et `accent` restent des `string` côté front, toujours lus via `resolveTemplateKey` / `resolveAccentKey`. Raison : le routeur renvoie le document Mongo brut, donc un ancien document n'a pas `accent`. Les requêtes, elles, sont typées `CvTemplateKey` / `CvAccentKey`.
5. Classique : « Langues » et « Centres d'intérêt » sont deux sections séparées, et non « Langues · Centres d'intérêt » comme sur la maquette. Raison : règle ATS 3 (titres standard).
6. Executive et Créatif : une ligne par catégorie de compétences, au lieu d'une grille en colonnes. Raison : pas d'entrelacement de colonnes à l'extraction.
7. La colonne latérale de Sidebar est en `align-self: start` : la teinte s'arrête avec son contenu au lieu de s'étirer sur la page 2.
8. Correction de bug : `{{ base_css }}` était autoéchappé (`@import url(&#39;…)`, `&#39;Inter&#39;`), donc Inter ne se chargeait probablement pas. Après la Tâche 1, les PDF passent réellement en Inter : le rendu change légèrement pour tous les CV.
9. Aperçu : le rechargement du PDF ne dépend plus de `resume.updated_at`, sinon chaque `PUT` d'apparence déclencherait un second rendu Chromium. Après l'enregistrement du contenu, le retour à l'onglet Aperçu recharge le PDF.
10. `<img>` de la photo : `alt=""`. Si l'image ne charge pas, le nom n'est pas réimprimé dans la colonne latérale.

## Carte des fichiers

| Fichier | Rôle | Tâches |
|---|---|---|
| `backend/app/services/cv_templates.py` | Registre (modèles, couleurs, titres), résolution, rendu | 1, 6, 7 |
| `backend/app/routers/resumes.py` | Validation `Literal`, enregistrement de `accent`, paramètre PDF | 2 |
| `backend/app/models.py` | `TailoredResumeInDB.accent` | 2 |
| `backend/app/templates/cv/_macros.html` (nouveau) | `icon`, `contacts`, `mobility_line`, `chips`, `tools_line`, `monogram` | 3 |
| `backend/app/templates/cv/base_cv.css` | Alias d'accent, ligatures, composants communs | 3, 5 |
| `backend/app/templates/cv/sidebar_elegance.html` | Sidebar modernisé, DOM `main` puis `aside` | 1, 4 |
| `backend/app/templates/cv/executive_minimalist.html` | Minimalist modernisé | 1, 5 |
| `backend/app/templates/cv/classique.html` (nouveau) | Classique | 6 |
| `backend/app/templates/cv/creatif.html` (nouveau) | Créatif | 7 |
| `backend/tests/test_cv_templates.py` | Rendu HTML, sans Chromium | 1, 3-7 |
| `backend/tests/test_resumes_api.py` | API : accent, 422, repli | 2, 6 |
| `backend/tests/test_cv_pdf_renderer.py` | Test ATS sur un vrai PDF | 4-7 |
| `backend/tests/test_cv_registry_parity.py` (nouveau) | Registre Python = constante TS | 8 |
| `frontend/src/lib/cvTemplates.ts` (nouveau) | Constante miroir, résolution des clés | 8 |
| `frontend/src/components/resumes/AccentSwatches.tsx` (nouveau) | Pastilles de couleur partagées | 8 |
| `frontend/src/types/resume.ts` | Types `accent`, `PdfOptions` | 8 |
| `frontend/src/lib/api.ts` | `PdfOptions`, `pdfQuery` | 8 |
| `frontend/src/components/resumes/ResumeCard.tsx` | Libellé et téléchargement | 8 |
| `frontend/src/app/resumes/page.tsx` | Fenêtre de génération, apparence, filtre | 8, 9, 10 |
| `frontend/src/components/resumes/ResumePreviewModal.tsx` | 2e barre d'outils, gardes | 8, 10 |

---

### Task 1: Registre, rendu et titres standard

**Files:**
- Modify: `backend/app/services/cv_templates.py` (fichier entier, 63 lignes)
- Modify: `backend/app/templates/cv/sidebar_elegance.html` (lignes de titres uniquement)
- Modify: `backend/app/templates/cv/executive_minimalist.html` (lignes de titres uniquement)
- Test: `backend/tests/test_cv_templates.py`

**Interfaces:**
- Consumes : rien.
- Produces :
  - `CV_TEMPLATES: tuple[str, ...]`, ici `("sidebar_elegance", "executive_minimalist")`, étendu en Tâches 6 et 7 ;
  - `CV_TEMPLATES_WITHOUT_PHOTO: frozenset[str]`, vide ici, `{"classique"}` en Tâche 6 ;
  - `CV_ACCENTS: dict[str, dict[str, str]]` (clés `primary`, `tint`, `line`) ;
  - `DEFAULT_TEMPLATE = "sidebar_elegance"`, `DEFAULT_ACCENT = "marine"` ;
  - `SECTION_TITLES: dict[str, str]`, clés `experience`, `skills`, `education`, `languages`, `certifications`, `projects`, `interests` ; variable globale Jinja `SECTION_TITLES` (valeurs `Markup`) ;
  - `render_cv_html(cv, candidate, template_name: Optional[str] = DEFAULT_TEMPLATE, with_photo: bool = False, photo_url: Optional[str] = None, accent: Optional[str] = DEFAULT_ACCENT) -> str` ;
  - variables CSS `--accent`, `--accent-tint`, `--accent-line` sur `:root` dans chaque page rendue.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter en bas de `backend/tests/test_cv_templates.py` :

```python
import logging

from app.services.cv_templates import SECTION_TITLES


def test_accent_injects_registry_colors():
    html = render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE, accent="bordeaux")
    assert "--accent: #8b1e3f" in html
    assert "--accent-tint: #f8eef1" in html
    assert "--accent-line: #d8a9b7" in html


def test_unknown_accent_falls_back_to_marine_with_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="app.services.cv_templates"):
        html = render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE, accent="fluo")
    assert "--accent: #1e3a8a" in html
    assert "fluo" in caplog.text


def test_missing_template_and_accent_fall_back_to_defaults():
    html = render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE, template_name=None, accent=None)
    assert "cv-layout-sidebar" in html
    assert "--accent: #1e3a8a" in html


def test_base_css_is_not_html_escaped():
    html = render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE)
    assert "@import url('https://fonts.googleapis.com" in html
    assert "&#39;Inter&#39;" not in html


def test_accent_block_follows_font_import():
    html = render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE)
    assert html.index("@import") < html.index("--accent: #")


@pytest.mark.parametrize("template", TEMPLATES)
def test_section_titles_come_from_registry(template):
    html = _render(template)
    assert f">{SECTION_TITLES['experience']}<" in html
    assert "Expérience Professionnelle" not in html
    assert "Projets Clés" not in html
    assert "Compétences Clés" not in html
```

Mettre à jour deux tests existants :
- `test_projects_section_hidden_when_empty` (lignes 181-184) : remplacer les deux `">Projets Clés & Réalisations<"` par `">Projets<"`.
- `test_sidebar_order_skills_certifications_languages_formation_interests` (ligne 190) : remplacer `">Compétences Clés<"` par `">Compétences<"`.

- [ ] **Step 2: Vérifier qu'ils échouent**

Run : `cd backend && uv run pytest tests/test_cv_templates.py -v`
Attendu : FAIL. `ImportError: cannot import name 'SECTION_TITLES'` fait échouer tout le module.

- [ ] **Step 3: Réécrire `backend/app/services/cv_templates.py`**

```python
import logging
from pathlib import Path
from typing import Any, Collection, Dict, Optional, Union

import jinja2
from markupsafe import Markup

from app.models import TailoredCVSchema

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates" / "cv"

# Registre : source unique des modèles et des couleurs (API, rendu, test de parité frontend).
CV_TEMPLATES = ("sidebar_elegance", "executive_minimalist")
CV_TEMPLATES_WITHOUT_PHOTO: frozenset = frozenset()
CV_ACCENTS = {
    "marine":    {"primary": "#1e3a8a", "tint": "#eef2fb", "line": "#a9b8e0"},
    "bleu_vert": {"primary": "#0f766e", "tint": "#e6f2f1", "line": "#99c9c4"},
    "ardoise":   {"primary": "#4f6d8a", "tint": "#eff3f7", "line": "#b3c3d3"},
    "sauge":     {"primary": "#4d6b4f", "tint": "#eff4ef", "line": "#b5c7b6"},
    "bordeaux":  {"primary": "#8b1e3f", "tint": "#f8eef1", "line": "#d8a9b7"},
    "graphite":  {"primary": "#374151", "tint": "#f1f2f4", "line": "#c3c7ce"},
}
DEFAULT_TEMPLATE = "sidebar_elegance"
DEFAULT_ACCENT = "marine"

# Titres de section standard (règle ATS 3), communs aux quatre modèles.
SECTION_TITLES = {
    "experience": "Expérience professionnelle",
    "skills": "Compétences",
    "education": "Formation",
    "languages": "Langues",
    "certifications": "Certifications & habilitations",
    "projects": "Projets",
    "interests": "Centres d'intérêt",
}

_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
)
# Markup : « & » et « ' » restent bruts, comme un titre écrit en dur dans le gabarit.
_jinja_env.globals["SECTION_TITLES"] = {key: Markup(title) for key, title in SECTION_TITLES.items()}


def _get_monogram(full_name: str) -> str:
    parts = full_name.strip().split()
    if not parts:
        return "CV"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def _resolve(value: Optional[str], allowed: Collection[str], default: str, kind: str) -> str:
    """Clé du registre, ou valeur par défaut pour une clé absente ou inconnue (ancien document)."""
    key = (value or "").lower().strip()
    if key in allowed:
        return key
    if value:
        logger.warning("Unknown CV %s '%s', defaulting to '%s'", kind, value, default)
    return default


def _accent_css(accent: str) -> str:
    colors = CV_ACCENTS[accent]
    return (
        f":root {{ --accent: {colors['primary']}; "
        f"--accent-tint: {colors['tint']}; --accent-line: {colors['line']}; }}"
    )


def render_cv_html(
    cv: Union[TailoredCVSchema, Dict[str, Any]],
    candidate: Dict[str, Any],
    template_name: Optional[str] = DEFAULT_TEMPLATE,
    with_photo: bool = False,
    photo_url: Optional[str] = None,
    accent: Optional[str] = DEFAULT_ACCENT,
) -> str:
    """
    Render a tailored CV into a self-contained HTML page using Jinja2 and base European A4 print CSS.
    """
    cv_dict = cv.model_dump() if isinstance(cv, TailoredCVSchema) else cv

    base_css_file = TEMPLATES_DIR / "base_cv.css"
    base_css = base_css_file.read_text(encoding="utf-8") if base_css_file.exists() else ""

    template_key = _resolve(template_name, CV_TEMPLATES, DEFAULT_TEMPLATE, "template")
    accent_key = _resolve(accent, CV_ACCENTS, DEFAULT_ACCENT, "accent")
    if template_key in CV_TEMPLATES_WITHOUT_PHOTO:
        with_photo = False

    template = _jinja_env.get_template(f"{template_key}.html")
    monogram = _get_monogram(candidate.get("full_name") or "CV")

    # Le bloc :root vient après base_css : @import doit rester la première règle de la feuille.
    styles = Markup(base_css + "\n" + _accent_css(accent_key))

    return template.render(
        cv=cv_dict,
        candidate=candidate,
        monogram=monogram,
        with_photo=with_photo,
        photo_url=photo_url,
        base_css=styles,
    )
```

- [ ] **Step 4: Remplacer les titres écrits en dur dans les deux gabarits existants**

Avec `Edit`, une occurrence à la fois. Ne rien changer d'autre : ces fichiers portent des modifications de l'utilisateur.

`backend/app/templates/cv/sidebar_elegance.html` :
- `<div class="sidebar-block-title">Compétences Clés</div>` → `<div class="sidebar-block-title">{{ SECTION_TITLES.skills }}</div>`
- `<div class="sidebar-block-title">Certifications & habilitations</div>` → `<div class="sidebar-block-title">{{ SECTION_TITLES.certifications }}</div>`
- `<div class="sidebar-block-title">Langues</div>` → `<div class="sidebar-block-title">{{ SECTION_TITLES.languages }}</div>`
- `<div class="sidebar-block-title">Formation</div>` → `<div class="sidebar-block-title">{{ SECTION_TITLES.education }}</div>`
- `<div class="sidebar-block-title">Centres d'intérêt</div>` → `<div class="sidebar-block-title">{{ SECTION_TITLES.interests }}</div>`
- `<h2 class="section-title">Expérience Professionnelle</h2>` → `<h2 class="section-title">{{ SECTION_TITLES.experience }}</h2>`
- `<h2 class="section-title">Projets Clés & Réalisations</h2>` → `<h2 class="section-title">{{ SECTION_TITLES.projects }}</h2>`

`backend/app/templates/cv/executive_minimalist.html` :
- `<h2 class="section-title">Expérience Professionnelle</h2>` → `<h2 class="section-title">{{ SECTION_TITLES.experience }}</h2>`
- `<h2 class="section-title">Compétences</h2>` → `<h2 class="section-title">{{ SECTION_TITLES.skills }}</h2>`
- `<h2 class="section-title">Certifications & habilitations</h2>` → `<h2 class="section-title">{{ SECTION_TITLES.certifications }}</h2>`
- `<h2 class="section-title">Projets Clés & Réalisations</h2>` → `<h2 class="section-title">{{ SECTION_TITLES.projects }}</h2>`
- `<h2 class="section-title">Formation</h2>` → `<h2 class="section-title">{{ SECTION_TITLES.education }}</h2>`
- `<h2 class="section-title">Langues</h2>` → `<h2 class="section-title">{{ SECTION_TITLES.languages }}</h2>`
- `<h2 class="section-title" style="margin-top: 8px;">Centres d'intérêt</h2>` → `<h2 class="section-title" style="margin-top: 8px;">{{ SECTION_TITLES.interests }}</h2>`

- [ ] **Step 5: Vérifier que tout passe**

Run : `cd backend && uv run pytest tests/test_cv_templates.py tests/test_cv_pdf_renderer.py -v`
Attendu : PASS, tests existants compris.

- [ ] **Step 6: Point d'arrêt — pas de commit sans demande de l'utilisateur**

---

### Task 2: API et modèle : `accent`, validation 422, repli

**Files:**
- Modify: `backend/app/routers/resumes.py` (imports l.17-21, l.28-38, l.151-162, l.208-214, l.225-264)
- Modify: `backend/app/models.py:751` (édition ciblée)
- Test: `backend/tests/test_resumes_api.py`

**Interfaces:**
- Consumes : `CV_TEMPLATES`, `CV_ACCENTS`, `DEFAULT_TEMPLATE`, `DEFAULT_ACCENT`, `render_cv_html(..., accent=)` (Tâche 1).
- Produces :
  - `POST /resumes/generate` accepte `accent` (défaut `"marine"`) et l'enregistre ;
  - `PUT /resumes/{id}` accepte `accent` et `template` optionnels ;
  - `GET /resumes/{id}/pdf?template=&accent=&with_photo=` ;
  - toute valeur hors registre renvoie une 422 ;
  - le document renvoyé contient `accent` s'il a été enregistré (ancien document : champ absent).

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter en bas de `backend/tests/test_resumes_api.py` :

```python
def _resume_doc(**overrides):
    """Document Mongo d'un CV ; sans `accent` par défaut, comme un ancien document."""
    return {
        "_id": ObjectId(),
        "user_id": ObjectId(MOCK_USER_ID),
        "target_role": "Lead Architect",
        "target_company": "Cloud SA",
        "template": "sidebar_elegance",
        "with_photo": False,
        "content": SAMPLE_CV_SCHEMA.model_dump(),
        **overrides,
    }


def _post_generate(client, payload):
    offer_id = ObjectId()
    insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    colls = {
        "candidate_profile": MagicMock(find_one=AsyncMock(return_value={"user_id": ObjectId(MOCK_USER_ID), "full_name": "Jean Dupont"})),
        "job_offers": MagicMock(find_one=AsyncMock(return_value={"_id": offer_id, "title": "Dev", "company": "Acme"})),
        "offer_evaluations": MagicMock(find_one=AsyncMock(return_value=None)),
        "tailored_resumes": MagicMock(insert_one=insert_one),
    }
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: create_mock_db(colls)
    with patch("app.routers.resumes.generate_tailored_cv_content", new_callable=AsyncMock, return_value=SAMPLE_CV_SCHEMA), \
         patch("app.routers.resumes.require_user_quota", new_callable=AsyncMock), \
         patch("app.routers.resumes.record_api_usage", new_callable=AsyncMock):
        res = client.post("/resumes/generate", json={"offer_id": str(offer_id), **payload})
    return res, insert_one


def test_generate_resume_saves_accent(client):
    res, insert_one = _post_generate(client, {"template": "executive_minimalist", "accent": "bordeaux"})
    assert res.status_code == 200
    saved = insert_one.call_args.args[0]
    assert saved["template"] == "executive_minimalist"
    assert saved["accent"] == "bordeaux"
    assert res.json()["accent"] == "bordeaux"


def test_generate_resume_defaults_to_sidebar_and_marine(client):
    res, insert_one = _post_generate(client, {})
    assert res.status_code == 200
    saved = insert_one.call_args.args[0]
    assert saved["template"] == "sidebar_elegance"
    assert saved["accent"] == "marine"


def test_update_resume_saves_accent(client):
    doc = _resume_doc()
    tailored = MagicMock(find_one=AsyncMock(return_value=doc), update_one=AsyncMock())
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: create_mock_db({"tailored_resumes": tailored})

    res = client.put(f"/resumes/{doc['_id']}", json={"accent": "sauge"})

    assert res.status_code == 200
    update_set = tailored.update_one.call_args.args[1]["$set"]
    assert update_set["accent"] == "sauge"
    assert "template" not in update_set


INVALID_APPEARANCE_REQUESTS = [
    ("post", "generate", {"json": {"offer_id": "60c72b2f9b1d8b2bad7f0001", "template": "fancy"}}),
    ("post", "generate", {"json": {"offer_id": "60c72b2f9b1d8b2bad7f0001", "accent": "fluo"}}),
    ("put", "{id}", {"json": {"template": "fancy"}}),
    ("put", "{id}", {"json": {"accent": "fluo"}}),
    ("get", "{id}/pdf", {"params": {"template": "fancy"}}),
    ("get", "{id}/pdf", {"params": {"accent": "fluo"}}),
]


@pytest.mark.parametrize("method, path, kwargs", INVALID_APPEARANCE_REQUESTS)
def test_unknown_template_or_accent_is_rejected(client, method, path, kwargs):
    doc = _resume_doc()
    tailored = MagicMock(find_one=AsyncMock(return_value=doc), update_one=AsyncMock())
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: create_mock_db({"tailored_resumes": tailored})

    res = getattr(client, method)("/resumes/" + path.format(id=doc["_id"]), **kwargs)

    assert res.status_code == 422
    tailored.update_one.assert_not_called()


@pytest.mark.parametrize("stored, query, expected", [
    ({}, {}, "marine"),
    ({"accent": "bordeaux"}, {}, "bordeaux"),
    ({"accent": "bordeaux"}, {"accent": "sauge"}, "sauge"),
    ({"template": None}, {}, "marine"),
])
def test_pdf_uses_query_then_stored_then_default_accent(client, stored, query, expected):
    doc = _resume_doc(**stored)
    colls = {
        "tailored_resumes": MagicMock(find_one=AsyncMock(return_value=doc)),
        "candidate_profile": MagicMock(find_one=AsyncMock(return_value={"full_name": "Jean Dupont"})),
    }
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: create_mock_db(colls)

    with patch("app.routers.resumes.render_cv_html", return_value="<html>CV</html>") as mock_render, \
         patch("app.routers.resumes.generate_cv_pdf", new_callable=AsyncMock, return_value=b"%PDF-1.4"):
        res = client.get(f"/resumes/{doc['_id']}/pdf", params=query)

    assert res.status_code == 200
    assert mock_render.call_args.kwargs["accent"] == expected
    assert mock_render.call_args.kwargs["template_name"] == (stored.get("template") or "sidebar_elegance")
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run : `cd backend && uv run pytest tests/test_resumes_api.py -v`
Attendu : FAIL. `saved["accent"]` donne `KeyError`, les cas 422 renvoient 200, et `kwargs["accent"]` donne `KeyError`.

- [ ] **Step 3: Modifier le routeur**

Dans `backend/app/routers/resumes.py`.

Imports : remplacer `from typing import Any, Dict, List, Optional` par `from typing import Any, Dict, List, Literal, Optional`, et `from app.services.cv_templates import render_cv_html` par :

```python
from app.services.cv_templates import (
    CV_ACCENTS,
    CV_TEMPLATES,
    DEFAULT_ACCENT,
    DEFAULT_TEMPLATE,
    render_cv_html,
)
```

Remplacer les deux classes de requête (lignes 28-38) :

```python
# Construits depuis le registre : une valeur hors registre renvoie une 422.
TemplateKey = Literal[CV_TEMPLATES]
AccentKey = Literal[tuple(CV_ACCENTS)]


class GenerateResumeRequest(BaseModel):
    offer_id: str
    application_id: Optional[str] = None
    template: TemplateKey = DEFAULT_TEMPLATE
    accent: AccentKey = DEFAULT_ACCENT
    with_photo: bool = False


class UpdateResumeRequest(BaseModel):
    content: Optional[TailoredCVSchema] = None
    template: Optional[TemplateKey] = None
    accent: Optional[AccentKey] = None
    with_photo: Optional[bool] = None
```

Dans `resume_doc` (`generate_resume`), après `"template": request.template,` ajouter :

```python
        "accent": request.accent,
```

Dans `update_resume`, après le bloc `if request.template is not None:` ajouter :

```python
    if request.accent is not None:
        update_fields["accent"] = request.accent
```

Dans `get_resume_pdf`, remplacer la signature :

```python
async def get_resume_pdf(
    resume_id: str,
    template: Optional[TemplateKey] = Query(None),
    accent: Optional[AccentKey] = Query(None),
    with_photo: Optional[bool] = Query(None),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
```

Remplacer `chosen_template = template or resume.get("template", "sidebar_elegance")` par :

```python
    # Paramètre d'URL, sinon valeur enregistrée, sinon défaut (ancien document sans accent).
    chosen_template = template or resume.get("template") or DEFAULT_TEMPLATE
    chosen_accent = accent or resume.get("accent") or DEFAULT_ACCENT
```

Dans l'appel `render_cv_html(...)`, après `photo_url=photo_url,` ajouter `accent=chosen_accent,`.

- [ ] **Step 4: Modifier le modèle (édition ciblée)**

`git diff backend/app/models.py` d'abord. Puis, avec `Edit` dans `TailoredResumeInDB` :

ancien :
```python
    template: str = "sidebar_elegance"  # "sidebar_elegance" or "executive_minimalist"
```
nouveau :
```python
    template: str = "sidebar_elegance"
    accent: str = "marine"
```

Pas de test dédié : le routeur n'instancie pas ce modèle, le champ documente la forme du document.

- [ ] **Step 5: Vérifier que tout passe**

Run : `cd backend && uv run pytest tests/test_resumes_api.py tests/test_cv_templates.py -v`
Attendu : PASS. Si `test_generate_resume_passes_evaluation_stored_with_string_ids` échoue faute de Mongo de test, lancer `docker compose up -d mongo_test` et relancer. C'est l'environnement, pas ce changement.

- [ ] **Step 6: Point d'arrêt — pas de commit sans demande de l'utilisateur**

---

### Task 3: Macros partagées et feuille de base

**Files:**
- Create: `backend/app/templates/cv/_macros.html`
- Modify: `backend/app/templates/cv/base_cv.css`
- Test: `backend/tests/test_cv_templates.py`

**Interfaces:**
- Consumes : `_jinja_env` (Tâche 1).
- Produces, dans un gabarit, après `{% import "_macros.html" as m %}` :
  - `m.icon(name)` : `name` parmi `mail|phone|pin|in|git|web`. Produit `<svg class="icon" data-icon="<name>" … aria-hidden="true">`, chemins seulement, aucun `<text>`.
  - `m.contacts(candidate)` : `<span class="contact"><svg…/><span>valeur</span></span>` pour `email`, `phone`, `location`, `linkedin_url`, `github_url`, `website_url` renseignés, séparés par un saut de ligne.
  - `m.mobility_line(candidate)` : `<div class="cv-mobility">A · B</div>`, ou rien si les deux champs sont vides.
  - `m.chips(items)` : `<span class="chip">A</span><span class="dot"> · </span><span class="chip">B</span>`.
  - `m.tools_line(items)` : `<div class="tools">A · B</div>`.
  - `m.monogram(initials)` : `<canvas class="monogram" width="232" height="232" data-initials="..">` suivi de son script.
- Classes CSS communes : `.chip`, `.dot`, `.icon`, `.contact`, `.tools`, `.cv-mobility`, `.monogram`, `.section-title`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter en bas de `backend/tests/test_cv_templates.py` :

```python
from app.services.cv_templates import _jinja_env


def _macro(call, **context):
    return _jinja_env.from_string('{% import "_macros.html" as m %}' + call).render(**context)


def test_chips_separated_by_visible_dot():
    assert _macro('{{ m.chips(["Python", "FastAPI"]) }}') == (
        '<span class="chip">Python</span><span class="dot"> · </span><span class="chip">FastAPI</span>'
    )


def test_chips_escape_content():
    assert "&lt;b&gt;" in _macro('{{ m.chips(["<b>"]) }}')


def test_tools_line_is_plain_text():
    assert _macro('{{ m.tools_line(["SAP", "Excel"]) }}') == '<div class="tools">SAP · Excel</div>'


def test_contacts_use_svg_icons_and_real_text():
    html = _macro("{{ m.contacts(candidate) }}", candidate={"email": "jean@x.fr", "website_url": "https://jean.fr"})
    assert 'data-icon="mail"' in html
    assert 'data-icon="web"' in html
    assert ">jean@x.fr<" in html
    assert 'data-icon="phone"' not in html
    assert "<text" not in html


def test_mobility_line_only_when_filled():
    both = _macro("{{ m.mobility_line(candidate) }}", candidate={"mobility": "Permis B", "availability": "2x8"})
    assert both == '<div class="cv-mobility">Permis B · 2x8</div>'
    assert _macro("{{ m.mobility_line(candidate) }}", candidate={}) == ""


def test_monogram_is_canvas_not_text():
    html = _macro('{{ m.monogram("JD") }}')
    assert '<canvas class="monogram"' in html
    assert 'data-initials="JD"' in html
    assert ">JD<" not in html


def test_base_css_disables_ligatures_and_aliases_accent():
    html = render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE)
    assert "font-variant-ligatures: none" in html
    assert "--color-primary: var(--accent)" in html
    assert "small-caps" not in html
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run : `cd backend && uv run pytest tests/test_cv_templates.py -v -k "chips or tools_line or contacts or mobility_line_only or monogram_is or base_css_disables"`
Attendu : FAIL avec `jinja2.exceptions.TemplateNotFound: _macros.html` et une assertion fausse sur `font-variant-ligatures`.

- [ ] **Step 3: Créer `backend/app/templates/cv/_macros.html`**

Les chemins SVG viennent des maquettes validées (`modernisation-existants.html`, `creatif-layout-v2.html`).

```jinja
{# Macros partagées par les quatre modèles de CV. Règles ATS : spec 2026-10-02 section 1. #}

{% macro icon(name) -%}
<svg class="icon" data-icon="{{ name }}" viewBox="0 0 24 24" aria-hidden="true">
{%- if name == "mail" %}<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>
{%- elif name == "phone" %}<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>
{%- elif name == "pin" %}<path d="M12 21s-7-6.5-7-12a7 7 0 0 1 14 0c0 5.5-7 12-7 12z"/><circle cx="12" cy="9" r="2.5"/>
{%- elif name == "in" %}<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M8 10v7M8 7v.01M12 17v-4a2 2 0 0 1 4 0v4M12 10v7"/>
{%- elif name == "git" %}<path d="M9 19c-4 1.5-4-2-6-2.5M15 21v-3.5a3 3 0 0 0-1-2.5c3 0 6-1.5 6-6.5a5 5 0 0 0-1.5-3.5 4.5 4.5 0 0 0-.1-3.5s-1.2-.3-3.9 1.5a13 13 0 0 0-7 0C4.8 1.2 3.6 1.5 3.6 1.5a4.5 4.5 0 0 0-.1 3.5A5 5 0 0 0 2 8.5c0 5 3 6.5 6 6.5a3 3 0 0 0-1 2.5V21"/>
{%- elif name == "web" %}<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>
{%- endif %}</svg>
{%- endmacro %}

{# Chaque contact : icône décorative puis le texte réel (règle ATS 5). #}
{% macro contacts(candidate) -%}
{%- for field, name in [("email", "mail"), ("phone", "phone"), ("location", "pin"), ("linkedin_url", "in"), ("github_url", "git"), ("website_url", "web")] %}
{%- if candidate[field] %}
<span class="contact">{{ icon(name) }}<span>{{ candidate[field] }}</span></span>
{%- endif %}
{%- endfor %}
{%- endmacro %}

{% macro mobility_line(candidate) -%}
{%- if candidate.mobility or candidate.availability -%}
<div class="cv-mobility">{{ [candidate.mobility, candidate.availability] | select | join(" · ") }}</div>
{%- endif -%}
{%- endmacro %}

{# Le « · » visible est le seul séparateur restitué à l'extraction (règle ATS 4). #}
{% macro chips(items) -%}
{%- for item in items -%}
{%- if not loop.first %}<span class="dot"> · </span>{% endif -%}
<span class="chip">{{ item }}</span>
{%- endfor -%}
{%- endmacro %}

{% macro tools_line(items) -%}
<div class="tools">{{ items | join(" · ") }}</div>
{%- endmacro %}

{# Initiales dessinées dans un canvas (4×, impression) : une image dans le PDF, jamais du texte (règle ATS 8). #}
{% macro monogram(initials) -%}
<canvas class="monogram" width="232" height="232" data-initials="{{ initials }}" aria-hidden="true"></canvas>
<script>
(function (c) {
  function draw() {
    var ctx = c.getContext("2d");
    var s = c.width;
    ctx.clearRect(0, 0, s, s);
    ctx.fillStyle = getComputedStyle(c).getPropertyValue("--accent").trim() || "#1e3a8a";
    ctx.beginPath();
    ctx.arc(s / 2, s / 2, s / 2, 0, 2 * Math.PI);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.font = "700 " + Math.round(s * 0.36) + "px Inter, Helvetica, Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(c.dataset.initials, s / 2, s / 2 + s * 0.02);
  }
  draw();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(draw);
})(document.currentScript.previousElementSibling);
</script>
{%- endmacro %}
```

- [ ] **Step 4: Modifier `backend/app/templates/cv/base_cv.css`**

Cinq remplacements avec `Edit`.

a) Charger la graisse 800 du nom. Ligne 2 :
```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
```

b) Dans `:root`, remplacer les trois lignes `--color-primary`, `--color-primary-light` et `--color-accent` (inutilisée) par :
```css
  /* Alias de l'accent injecté par render_cv_html depuis le registre CV_ACCENTS */
  --color-primary: var(--accent);
  --color-primary-light: var(--accent-tint);
```

c) Dans `body`, après `-webkit-font-smoothing: antialiased;`, ajouter :
```css
  font-variant-ligatures: none; /* « fi » extrait en deux lettres, pas en U+FB01 (règle ATS 6) */
```

d) Remplacer tout le bloc `.monogram { … }` par :
```css
.monogram {
  display: block;
  width: 58px;
  height: 58px;
  border-radius: 50%;
}
```

e) Remplacer tout le bloc `.section-title { … }` par le bloc suivant, puis ajouter les composants à la fin du fichier :
```css
/* Majuscules par text-transform, interlettrage ≤ .08em : pas de petites capitales (cassent l'extraction). */
.section-title {
  font-size: 8.5pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--accent);
  margin-bottom: 6px;
}

.chip {
  display: inline-block;
  padding: 1px 7px;
  font-size: 8pt;
  color: var(--color-slate-800);
  background: #ffffff;
  border: 1px solid var(--accent-line);
  border-radius: 999px;
  margin-bottom: 3px;
}

.dot {
  color: var(--accent-line);
  font-size: 7pt;
}

.icon {
  width: 9px;
  height: 9px;
  flex: none;
  stroke: var(--accent);
  fill: none;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.contact {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.tools {
  margin-top: 2px;
  font-size: 8pt;
  color: var(--color-slate-500);
}

.cv-mobility {
  font-size: 8.5pt;
  color: var(--color-slate-600);
  margin-top: 3px;
}
```

`.badge` et `.badge-primary` restent jusqu'à la Tâche 5 : les deux gabarits existants les utilisent encore.

- [ ] **Step 5: Vérifier que tout passe**

Run : `cd backend && uv run pytest tests/test_cv_templates.py tests/test_cv_pdf_renderer.py -v`
Attendu : PASS.

- [ ] **Step 6: Point d'arrêt — pas de commit sans demande de l'utilisateur**

---

### Task 4: Sidebar Elegance modernisé et test ATS sur PDF réel

**Files:**
- Modify: `backend/app/templates/cv/sidebar_elegance.html` (réécriture complète)
- Test: `backend/tests/test_cv_templates.py`, `backend/tests/test_cv_pdf_renderer.py`

**Interfaces:**
- Consumes : macros `m.*` (Tâche 3), `SECTION_TITLES` (Tâche 1), `generate_cv_pdf(html) -> bytes` (existant ; lance un Chromium neuf à chaque appel, donc `asyncio.run` répété est sûr).
- Produces :
  - dans `test_cv_templates.py` : `ATS_SAFE_TEMPLATES` (liste), `EMOJI_RE` ;
  - dans `test_cv_pdf_renderer.py` : `ATS_CANDIDATE`, `ATS_CV`, `ATS_TEMPLATES` (liste), `_extract(template) -> (pages_pdfplumber, pages_pymupdf)`. Les Tâches 5 à 7 ajoutent leur modèle à ces listes.

- [ ] **Step 1: Écrire les tests HTML qui échouent**

Dans `backend/tests/test_cv_templates.py` :
- `test_render_sidebar_elegance`, ligne 82 : remplacer `assert "JD" in html  # Monogram initials when with_photo is False` par :
```python
    assert '<canvas class="monogram"' in html  # Monogramme dessiné, pas du texte
    assert 'data-initials="JD"' in html
    assert ">JD<" not in html
```
- `test_portfolio_link_shown_only_when_set`, ligne 154 : remplacer `assert "🌐" not in _render(template, website_url=None)` par `assert 'data-icon="web"' not in _render(template, website_url=None)`.

Ajouter en bas :

```python
import re

EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿-]")
ATS_SAFE_TEMPLATES = ["sidebar_elegance"]


@pytest.mark.parametrize("template", ATS_SAFE_TEMPLATES)
def test_no_emoji_in_html(template):
    html = _render(template, website_url="https://jeandupont.fr", interests=["Football"])
    assert not EMOJI_RE.search(html)


@pytest.mark.parametrize("template", ATS_SAFE_TEMPLATES)
def test_contacts_use_svg_icons(template):
    html = _render(template)
    assert 'data-icon="mail"' in html
    assert 'data-icon="pin"' in html


def test_sidebar_main_precedes_aside():
    html = _render("sidebar_elegance")
    assert html.index("<main") < html.index("<aside")


def test_sidebar_skills_render_as_chips():
    html = _render("sidebar_elegance")
    assert '<span class="chip">Python</span><span class="dot"> · </span><span class="chip">FastAPI</span>' in html
    assert 'class="badge' not in html
```

- [ ] **Step 2: Écrire le test ATS PDF qui échoue**

Ajouter en bas de `backend/tests/test_cv_pdf_renderer.py`, sans toucher au test existant :

```python
import asyncio
import re
from functools import lru_cache

import pymupdf

from app.models import TailoredProjectItem
from app.services.cv_templates import SECTION_TITLES

ATS_TEMPLATES = ["sidebar_elegance"]
EMOJI_OR_PRIVATE_USE = re.compile("[\U0001F000-\U0001FAFF☀-➿-]")
JOB_COUNT = 6

ATS_CANDIDATE = {
    "full_name": "Jean Dupont",
    "email": "jean.dupont@email.com",
    "phone": "+33 6 12 34 56 78",
    "location": "Lyon, France",
    "linkedin_url": "https://linkedin.com/in/jeandupont",
    "github_url": "https://github.com/jeandupont",
    "website_url": "https://jeandupont.fr",
    "mobility": "Permis B, véhiculé",
    "availability": "Disponible immédiatement",
    "interests": ["Football", "Randonnée", "Photographie"],
}


def _job(i):
    return TailoredExperienceItem(
        title=f"Poste numéro {i}",
        company=f"Entreprise {i}",
        location="Lyon",
        start_date=str(2010 + 2 * i),
        end_date=str(2012 + 2 * i),
        bullet_points=[
            f"Réalisation {i}.{j} : pilotage d'un chantier de modernisation avec une équipe "
            "pluridisciplinaire, suivi des indicateurs et amélioration continue des processus."
            for j in range(1, 5)
        ],
        # Outils distincts des compétences : « Python · FastAPI » ne peut venir que des pastilles.
        relevant_technologies=["SAP", "Excel"],
    )


ATS_CV = TailoredCVSchema(
    target_role_title="Responsable des opérations",
    professional_summary=(
        "Responsable des opérations, douze ans d'expérience en pilotage d'équipes et en "
        "amélioration continue, habitué aux environnements multisites."
    ),
    prioritized_skills=[
        TailoredSkillGroup(category="Technique", skills=["Python", "FastAPI", "Docker", "Kubernetes", "PostgreSQL", "Redis"]),
        TailoredSkillGroup(category="Gestion", skills=["Planification", "Budget", "Recrutement", "Animation d'équipe"]),
    ],
    experiences=[_job(i) for i in range(1, JOB_COUNT + 1)],
    featured_projects=[
        TailoredProjectItem(
            name="Refonte logistique",
            description="Réorganisation des flux d'un entrepôt de 20 000 m².",
            technologies=["Airflow", "Tableau"],
        )
    ],
    education=[TailoredEducationItem(degree="Master Management", institution="IAE Lyon", year="2010")],
    languages=[
        TailoredLanguage(language="Anglais", level="C1"),
        TailoredLanguage(language="Allemand", level="B2"),
    ],
    certifications=["Auditeur certifié ISO 9001", "Sauveteur Secouriste du Travail"],
)


def _normalize(text):
    return " ".join(text.split())


@lru_cache(maxsize=None)
def _extract(template):
    """Texte par page : pdfplumber (ordre de lecture visuel) et pymupdf (ordre du flux, donc du DOM)."""
    html = render_cv_html(cv=ATS_CV, candidate=ATS_CANDIDATE, template_name=template)
    pdf_bytes = asyncio.run(generate_cv_pdf(html))
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = tuple(page.extract_text() or "" for page in pdf.pages)
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        flow = tuple(page.get_text(sort=False) for page in doc)
    return pages, flow


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_name_is_first_line(template):
    pages, _ = _extract(template)
    lines = [line.strip() for line in pages[0].splitlines() if line.strip()]
    assert lines[0] == "Jean Dupont"


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_profile_fills_two_pages(template):
    pages, _ = _extract(template)
    assert len(pages) >= 2


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_standard_section_titles_extracted(template):
    pages, _ = _extract(template)
    text = _normalize(" ".join(pages)).casefold()
    assert [t for t in SECTION_TITLES.values() if t.casefold() not in text] == []


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_skills_separated_in_text(template):
    pages, _ = _extract(template)
    text = _normalize(" ".join(pages))
    assert "Python · FastAPI" in text
    assert "PythonFastAPI" not in text


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_no_side_column_line_inside_a_job(template):
    _, flow = _extract(template)
    text = _normalize(" ".join(flow))
    for i in range(1, JOB_COUNT + 1):
        start = text.index(f"Poste numéro {i}")
        block = text[start:text.index(f"Réalisation {i}.4", start)]
        assert "jean.dupont@email.com" not in block
        assert "Allemand" not in block


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_no_ligature_glyph(template):
    pages, _ = _extract(template)
    text = _normalize(" ".join(pages))
    assert "ﬁ" not in text and "ﬂ" not in text
    assert "certifié" in text.casefold()


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_monogram_initials_not_extracted(template):
    pages, _ = _extract(template)
    assert "JD" not in {line.strip() for page in pages for line in page.splitlines()}


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_no_emoji_or_private_use_glyph(template):
    pages, _ = _extract(template)
    assert not EMOJI_OR_PRIVATE_USE.search(" ".join(pages))


@pytest.mark.parametrize("template", ATS_TEMPLATES)
def test_ats_job_title_and_first_bullet_on_same_page(template):
    pages, _ = _extract(template)
    flat = [_normalize(page) for page in pages]
    for i in range(1, JOB_COUNT + 1):
        title_page = next(n for n, page in enumerate(flat) if f"Poste numéro {i}" in page)
        bullet_page = next(n for n, page in enumerate(flat) if f"Réalisation {i}.1" in page)
        assert title_page == bullet_page
```

- [ ] **Step 3: Vérifier qu'ils échouent**

Run : `cd backend && uv run pytest tests/test_cv_templates.py tests/test_cv_pdf_renderer.py -v`
Attendu : FAIL sur canvas, `data-icon`, `<main` avant `<aside`, emoji, « Python · FastAPI », monogramme « JD » extrait. Le premier test ATS, `test_ats_name_is_first_line`, échoue probablement aussi (« JD » ou la colonne latérale lue avant le nom).

- [ ] **Step 4: Réécrire `backend/app/templates/cv/sidebar_elegance.html`**

`git diff backend/app/templates/cv/sidebar_elegance.html` d'abord : la seule modification de l'utilisateur est le retrait de `page-break-avoid` sur les sections. La version ci-dessous la respecte : la classe n'est que sur `.experience-item` et `.project-item`.

```html
<!DOCTYPE html>
<html lang="fr">
{% import "_macros.html" as m %}
<head>
  <meta charset="UTF-8">
  <title>{{ candidate.full_name }} - {{ cv.target_role_title }}</title>
  <style>
    {{ base_css }}

    /* Le DOM place <main> avant <aside> (règle ATS 1) : la grille remet la colonne à gauche. */
    .cv-layout-sidebar {
      display: grid;
      grid-template-columns: 31fr 69fr;
      grid-template-areas: "aside main";
      column-gap: 18px;
    }

    .cv-main {
      grid-area: main;
      min-width: 0;
      padding: 4px 2px 12px 0;
    }

    .cv-aside {
      grid-area: aside;
      align-self: start; /* la teinte s'arrête avec le contenu, elle ne s'étire pas sur la page 2 */
      min-width: 0;
      background: var(--accent-tint);
      border-radius: 8px;
      padding: 14px 12px;
    }

    .aside-visual { margin-bottom: 14px; }
    .aside-block { margin-bottom: 14px; }
    .cv-aside .section-title { font-size: 7.5pt; margin-bottom: 5px; }

    .cv-aside .contact {
      display: flex;
      margin-bottom: 4px;
      font-size: 8pt;
      color: var(--color-slate-700);
      word-break: break-word;
    }

    .skill-category { margin-bottom: 7px; }
    .skill-category-name { font-size: 7.5pt; font-weight: 600; color: var(--color-slate-500); margin-bottom: 3px; }
    .lang-item { font-size: 8pt; margin-bottom: 3px; }
    .lang-level { color: var(--color-slate-500); }
    .edu-item { margin-bottom: 6px; font-size: 8pt; }
    .edu-degree { font-weight: 600; color: var(--color-slate-800); }
    .edu-inst { color: var(--color-slate-600); font-size: 7.5pt; }
    .interest-item { font-size: 8pt; color: var(--color-slate-700); margin-bottom: 2px; }

    .main-header { margin-bottom: 10px; }

    .main-candidate-name {
      font-size: 22pt;
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1.05;
      color: var(--color-slate-900);
    }

    .main-role-title { font-size: 11pt; font-weight: 600; color: var(--accent); margin-top: 4px; }
    .summary { font-size: 8.8pt; color: var(--color-slate-700); line-height: 1.5; margin-bottom: 14px; }
    .main-section { margin-bottom: 12px; }
    .experience-item { margin-bottom: 11px; }

    .exp-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 8px;
    }

    .exp-title { font-size: 9.5pt; font-weight: 700; color: var(--color-slate-900); }
    .exp-dates { font-size: 8pt; color: var(--color-slate-500); white-space: nowrap; }
    .exp-subtitle { font-size: 8.5pt; color: var(--accent); font-weight: 600; margin-bottom: 3px; }
    .exp-location { font-weight: 400; color: var(--color-slate-500); }
    .exp-bullets { list-style-type: disc; padding-left: 14px; }
    .exp-bullets li { font-size: 8.5pt; color: var(--color-slate-700); margin-bottom: 2px; line-height: 1.35; }
    .project-item { margin-bottom: 8px; }
    .project-title { font-size: 9pt; font-weight: 600; color: var(--color-slate-900); }
    .project-url { font-weight: 400; font-size: 7.5pt; color: var(--color-slate-500); }
    .project-desc { font-size: 8pt; color: var(--color-slate-600); margin-top: 1px; }
  </style>
</head>
<body>
  <div class="cv-layout-sidebar">
    <main class="cv-main">
      <header class="main-header">
        <h1 class="main-candidate-name">{{ candidate.full_name }}</h1>
        <div class="main-role-title">{{ cv.target_role_title }}</div>
        {{ m.mobility_line(candidate) }}
      </header>

      {% if cv.professional_summary %}
      <p class="summary">{{ cv.professional_summary }}</p>
      {% endif %}

      {% if cv.experiences %}
      <section class="main-section">
        <h2 class="section-title">{{ SECTION_TITLES.experience }}</h2>
        {% for exp in cv.experiences %}
        <article class="experience-item page-break-avoid">
          <div class="exp-header">
            <h3 class="exp-title">{{ exp.title }}</h3>
            <span class="exp-dates">{{ exp.start_date }} – {{ exp.end_date or 'Présent' }}</span>
          </div>
          <div class="exp-subtitle">
            {{ exp.company }}{% if exp.location %} <span class="exp-location">· {{ exp.location }}</span>{% endif %}
          </div>
          {% if exp.bullet_points %}
          <ul class="exp-bullets">
            {% for bp in exp.bullet_points %}
            <li>{{ bp }}</li>
            {% endfor %}
          </ul>
          {% endif %}
          {% if exp.relevant_technologies %}{{ m.tools_line(exp.relevant_technologies) }}{% endif %}
        </article>
        {% endfor %}
      </section>
      {% endif %}

      {% if cv.featured_projects %}
      <section class="main-section">
        <h2 class="section-title">{{ SECTION_TITLES.projects }}</h2>
        {% for proj in cv.featured_projects %}
        <div class="project-item page-break-avoid">
          <div class="project-title">
            {{ proj.name }}{% if proj.url %} <span class="project-url">({{ proj.url }})</span>{% endif %}
          </div>
          <div class="project-desc">{{ proj.description }}</div>
          {% if proj.technologies %}{{ m.tools_line(proj.technologies) }}{% endif %}
        </div>
        {% endfor %}
      </section>
      {% endif %}
    </main>

    <aside class="cv-aside">
      <div class="aside-visual">
        {% if with_photo and photo_url %}
        <img class="avatar-img" src="{{ photo_url }}" alt="" />
        {% else %}
        {{ m.monogram(monogram) }}
        {% endif %}
      </div>

      <div class="aside-block">
        <h2 class="section-title">Contact</h2>
        {{ m.contacts(candidate) }}
      </div>

      {% if cv.prioritized_skills %}
      <div class="aside-block">
        <h2 class="section-title">{{ SECTION_TITLES.skills }}</h2>
        {% for group in cv.prioritized_skills %}
        <div class="skill-category">
          <div class="skill-category-name">{{ group.category }}</div>
          <div>{{ m.chips(group.skills) }}</div>
        </div>
        {% endfor %}
      </div>
      {% endif %}

      {% if cv.certifications %}
      <div class="aside-block">
        <h2 class="section-title">{{ SECTION_TITLES.certifications }}</h2>
        {% for cert in cv.certifications %}
        <div class="edu-item"><div class="edu-degree">{{ cert }}</div></div>
        {% endfor %}
      </div>
      {% endif %}

      {% if cv.languages %}
      <div class="aside-block">
        <h2 class="section-title">{{ SECTION_TITLES.languages }}</h2>
        {% for lang in cv.languages %}
        <div class="lang-item"><strong>{{ lang.language }}</strong> <span class="lang-level">· {{ lang.level }}</span></div>
        {% endfor %}
      </div>
      {% endif %}

      {% if cv.education %}
      <div class="aside-block">
        <h2 class="section-title">{{ SECTION_TITLES.education }}</h2>
        {% for edu in cv.education %}
        <div class="edu-item">
          <div class="edu-degree">{{ edu.degree }}</div>
          <div class="edu-inst">{{ edu.institution }} — {{ edu.year }}</div>
          {% if edu.details %}<div class="edu-inst">{{ edu.details }}</div>{% endif %}
        </div>
        {% endfor %}
      </div>
      {% endif %}

      {% if candidate.interests %}
      <div class="aside-block">
        <h2 class="section-title">{{ SECTION_TITLES.interests }}</h2>
        {% for interest in candidate.interests %}
        <div class="interest-item">{{ interest }}</div>
        {% endfor %}
      </div>
      {% endif %}
    </aside>
  </div>
</body>
</html>
```

- [ ] **Step 5: Vérifier que tout passe**

Run : `cd backend && uv run pytest tests/test_cv_templates.py tests/test_cv_pdf_renderer.py -v`
Attendu : PASS.

Si seul `test_ats_skills_separated_in_text` échoue (bordure ou padding des pastilles qui collent le « · ») : repli prévu au spec, dans `base_cv.css`, retirer bordure et padding de `.chip` :
```css
.chip {
  display: inline;
  padding: 0;
  font-size: 8pt;
  color: var(--color-slate-800);
  border: none;
}
```
Puis relancer. Signaler le repli à l'utilisateur, car il change l'aspect validé sur maquette.

Si `test_ats_name_is_first_line` échoue sur Sidebar parce qu'une ligne de la colonne latérale est à la même hauteur que le nom : augmenter `.aside-visual { margin-bottom }` n'aide pas. Vérifier d'abord que le monogramme est bien un canvas, puis que `padding-top` de `.cv-aside` (14px) laisse le nom seul sur sa ligne.

- [ ] **Step 6: Point d'arrêt — pas de commit sans demande de l'utilisateur**

---

### Task 5: Executive Minimalist modernisé, fin des badges

**Files:**
- Modify: `backend/app/templates/cv/executive_minimalist.html` (réécriture complète)
- Modify: `backend/app/templates/cv/base_cv.css` (suppression de `.badge` et `.badge-primary`)
- Test: `backend/tests/test_cv_templates.py`, `backend/tests/test_cv_pdf_renderer.py`

**Interfaces:**
- Consumes : macros (Tâche 3), `SECTION_TITLES`, `ATS_SAFE_TEMPLATES`, `ATS_TEMPLATES` (Tâche 4).
- Produces : classes `cv-executive-container` et `exec-*` (le test existant cherche « executive »), pied de page `.footer-cols`.

- [ ] **Step 1: Écrire les tests qui échouent**

`backend/tests/test_cv_templates.py` : remplacer `ATS_SAFE_TEMPLATES = ["sidebar_elegance"]` par `ATS_SAFE_TEMPLATES = ["sidebar_elegance", "executive_minimalist"]`, puis ajouter :

```python
def test_executive_footer_titles_followed_by_their_content():
    html = _render("executive_minimalist", interests=["Randonnée"])
    positions = [
        html.index(">Formation<"),
        html.index("Master Informatique"),
        html.index(">Langues<"),
        html.index("C1 - Professionnel courant"),
        html.index(">Centres d'intérêt<"),
        html.index("Randonnée"),
    ]
    assert positions == sorted(positions)


def test_executive_has_no_black_rule_nor_summary_frame():
    html = _render("executive_minimalist")
    assert "2px solid var(--color-slate-900)" not in html
    assert "border-left: 3px" not in html


def test_badges_are_gone_from_base_css():
    assert ".badge" not in render_cv_html(cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE)
```

`backend/tests/test_cv_pdf_renderer.py` : remplacer `ATS_TEMPLATES = ["sidebar_elegance"]` par `ATS_TEMPLATES = ["sidebar_elegance", "executive_minimalist"]`.

- [ ] **Step 2: Vérifier qu'ils échouent**

Run : `cd backend && uv run pytest tests/test_cv_templates.py tests/test_cv_pdf_renderer.py -v -k "executive or badges or emoji or svg_icons"`
Attendu : FAIL : 🏅 ✉ (emoji), `data-icon`, trait noir, `.badge`, « Python · FastAPI » sur Minimalist.

- [ ] **Step 3: Réécrire `backend/app/templates/cv/executive_minimalist.html`**

```html
<!DOCTYPE html>
<html lang="fr">
{% import "_macros.html" as m %}
<head>
  <meta charset="UTF-8">
  <title>{{ candidate.full_name }} - {{ cv.target_role_title }}</title>
  <style>
    {{ base_css }}

    .cv-executive-container { max-width: 100%; margin: 0 auto; }

    .exec-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 12px;
    }

    .exec-name {
      font-size: 24pt;
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1.05;
      color: var(--color-slate-900);
    }

    .exec-title { font-size: 11pt; font-weight: 600; color: var(--accent); margin-top: 4px; }

    .exec-contact {
      display: flex;
      flex-wrap: wrap;
      column-gap: 12px;
      row-gap: 2px;
      font-size: 8pt;
      color: var(--color-slate-600);
      margin-top: 7px;
    }

    .exec-rule { height: 1px; background: var(--color-slate-200); margin-bottom: 12px; }
    .exec-summary { font-size: 8.8pt; line-height: 1.5; color: var(--color-slate-700); margin-bottom: 14px; }
    .section-block { margin-bottom: 13px; }
    .exec-exp-item { margin-bottom: 11px; }

    .exec-exp-head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 8px;
    }

    .exec-exp-role { font-size: 9.5pt; font-weight: 700; color: var(--color-slate-900); }
    .exec-sep { color: var(--color-slate-400); }
    .exec-exp-company { font-size: 8.8pt; font-weight: 600; color: var(--accent); }
    .exec-exp-location { font-size: 7.5pt; color: var(--color-slate-500); }
    .exec-exp-dates { font-size: 8pt; color: var(--color-slate-500); white-space: nowrap; }
    .exec-exp-bullets { list-style-type: disc; padding-left: 15px; margin-top: 3px; }
    .exec-exp-bullets li { font-size: 8.5pt; color: var(--color-slate-700); margin-bottom: 2px; line-height: 1.35; }

    /* Une ligne par catégorie : pas de colonnes côte à côte qui s'entrelaceraient à l'extraction. */
    .skill-row { display: flex; gap: 8px; align-items: baseline; margin-bottom: 4px; }
    .skill-cat-title { width: 20%; flex: none; font-size: 8pt; font-weight: 600; color: var(--color-slate-600); }
    .cert-item { font-size: 8.5pt; color: var(--color-slate-700); margin-bottom: 3px; }
    .exec-project { margin-bottom: 7px; }
    .exec-project-name { font-size: 8.8pt; font-weight: 600; color: var(--color-slate-900); }
    .exec-project-url { font-weight: 400; font-size: 7.5pt; color: var(--color-slate-500); }
    .exec-project-desc { font-size: 8pt; color: var(--color-slate-600); }

    .footer-cols { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 4px; }
    .footer-line { font-size: 8pt; color: var(--color-slate-700); margin-bottom: 4px; }
    .footer-muted { color: var(--color-slate-500); font-size: 7.5pt; }
  </style>
</head>
<body>
  <div class="cv-executive-container">
    <header class="exec-header">
      <div>
        <h1 class="exec-name">{{ candidate.full_name }}</h1>
        <div class="exec-title">{{ cv.target_role_title }}</div>
        {{ m.mobility_line(candidate) }}
        <div class="exec-contact">{{ m.contacts(candidate) }}</div>
      </div>
      {% if with_photo and photo_url %}
      <img class="avatar-img" src="{{ photo_url }}" alt="" />
      {% endif %}
    </header>
    <div class="exec-rule"></div>

    {% if cv.professional_summary %}
    <p class="exec-summary">{{ cv.professional_summary }}</p>
    {% endif %}

    {% if cv.experiences %}
    <section class="section-block">
      <h2 class="section-title">{{ SECTION_TITLES.experience }}</h2>
      {% for exp in cv.experiences %}
      <article class="exec-exp-item page-break-avoid">
        <div class="exec-exp-head">
          <div>
            <span class="exec-exp-role">{{ exp.title }}</span><span class="exec-sep"> · </span><span class="exec-exp-company">{{ exp.company }}</span>{% if exp.location %} <span class="exec-exp-location">({{ exp.location }})</span>{% endif %}
          </div>
          <span class="exec-exp-dates">{{ exp.start_date }} – {{ exp.end_date or 'Présent' }}</span>
        </div>
        {% if exp.bullet_points %}
        <ul class="exec-exp-bullets">
          {% for bp in exp.bullet_points %}
          <li>{{ bp }}</li>
          {% endfor %}
        </ul>
        {% endif %}
        {% if exp.relevant_technologies %}{{ m.tools_line(exp.relevant_technologies) }}{% endif %}
      </article>
      {% endfor %}
    </section>
    {% endif %}

    {% if cv.prioritized_skills %}
    <section class="section-block">
      <h2 class="section-title">{{ SECTION_TITLES.skills }}</h2>
      {% for group in cv.prioritized_skills %}
      <div class="skill-row">
        <div class="skill-cat-title">{{ group.category }}</div>
        <div>{{ m.chips(group.skills) }}</div>
      </div>
      {% endfor %}
    </section>
    {% endif %}

    {% if cv.certifications %}
    <section class="section-block">
      <h2 class="section-title">{{ SECTION_TITLES.certifications }}</h2>
      {% for cert in cv.certifications %}
      <div class="cert-item">{{ cert }}</div>
      {% endfor %}
    </section>
    {% endif %}

    {% if cv.featured_projects %}
    <section class="section-block">
      <h2 class="section-title">{{ SECTION_TITLES.projects }}</h2>
      {% for proj in cv.featured_projects %}
      <div class="exec-project page-break-avoid">
        <div class="exec-project-name">
          {{ proj.name }}{% if proj.url %} <span class="exec-project-url">({{ proj.url }})</span>{% endif %}
        </div>
        <div class="exec-project-desc">{{ proj.description }}</div>
        {% if proj.technologies %}{{ m.tools_line(proj.technologies) }}{% endif %}
      </div>
      {% endfor %}
    </section>
    {% endif %}

    {% if cv.education or cv.languages or candidate.interests %}
    <div class="footer-cols">
      {% if cv.education %}
      <div>
        <h2 class="section-title">{{ SECTION_TITLES.education }}</h2>
        {% for edu in cv.education %}
        <div class="footer-line">
          <strong>{{ edu.degree }}</strong><br>
          <span class="footer-muted">{{ edu.institution }} — {{ edu.year }}</span>
          {% if edu.details %}<br><span class="footer-muted">{{ edu.details }}</span>{% endif %}
        </div>
        {% endfor %}
      </div>
      {% endif %}
      {% if cv.languages %}
      <div>
        <h2 class="section-title">{{ SECTION_TITLES.languages }}</h2>
        {% for lang in cv.languages %}
        <div class="footer-line"><strong>{{ lang.language }}</strong> : {{ lang.level }}</div>
        {% endfor %}
      </div>
      {% endif %}
      {% if candidate.interests %}
      <div>
        <h2 class="section-title">{{ SECTION_TITLES.interests }}</h2>
        <div class="footer-line">{{ candidate.interests | join(" · ") }}</div>
      </div>
      {% endif %}
    </div>
    {% endif %}
  </div>
</body>
</html>
```

- [ ] **Step 4: Supprimer les badges de `base_cv.css`**

Vérifier d'abord qu'aucun gabarit ne les utilise plus :
Run : `rtk grep -rn "badge" backend/app/templates/cv`
Attendu : seules les deux règles de `base_cv.css`. Supprimer alors les blocs `.badge { … }` et `.badge-primary { … }`.

- [ ] **Step 5: Vérifier que tout passe**

Run : `cd backend && uv run pytest tests/test_cv_templates.py tests/test_cv_pdf_renderer.py -v`
Attendu : PASS.

- [ ] **Step 6: Point d'arrêt — pas de commit sans demande de l'utilisateur**

---

### Task 6: Modèle Classique

**Files:**
- Create: `backend/app/templates/cv/classique.html`
- Modify: `backend/app/services/cv_templates.py` (registre)
- Test: `backend/tests/test_cv_templates.py`, `backend/tests/test_cv_pdf_renderer.py`, `backend/tests/test_resumes_api.py`

**Interfaces:**
- Consumes : macros (`contacts`, `mobility_line`, `tools_line`), `SECTION_TITLES`, `_post_generate` (Tâche 2).
- Produces :
  - `CV_TEMPLATES = ("sidebar_elegance", "executive_minimalist", "classique")` ;
  - `CV_TEMPLATES_WITHOUT_PHOTO = frozenset({"classique"})` ;
  - l'API accepte `template="classique"` (le `Literal` est construit depuis le registre).

- [ ] **Step 1: Écrire les tests qui échouent**

`backend/tests/test_cv_templates.py` :
- remplacer `TEMPLATES = ["sidebar_elegance", "executive_minimalist"]` (ligne 126) par `TEMPLATES = ["sidebar_elegance", "executive_minimalist", "classique"]` ;
- remplacer la liste `ATS_SAFE_TEMPLATES` par `ATS_SAFE_TEMPLATES = ["sidebar_elegance", "executive_minimalist", "classique"]` ;
- ajouter :

```python
def test_classique_never_renders_photo():
    html = render_cv_html(
        cv=SAMPLE_CV,
        candidate=SAMPLE_CANDIDATE,
        template_name="classique",
        with_photo=True,
        photo_url="https://example.com/avatar.jpg",
    )
    assert "<img" not in html
    assert "avatar.jpg" not in html


def test_classique_section_order():
    html = _render("classique", interests=["Football"])
    positions = [
        html.index(">Expérience professionnelle<"),
        html.index(">Projets<"),
        html.index(">Certifications & habilitations<"),
        html.index(">Compétences<"),
        html.index(">Formation<"),
        html.index(">Langues<"),
        html.index(">Centres d'intérêt<"),
    ]
    assert positions == sorted(positions)


def test_classique_skills_as_plain_text_lines():
    assert "<strong>Backend</strong> : Python · FastAPI · Go" in _render("classique")


def test_classique_uses_grey_bands_and_accent_only_on_name():
    html = _render("classique")
    assert '<h2 class="cl-band">' in html
    assert ".cl-band" in html and "var(--color-slate-100)" in html
```

`backend/tests/test_cv_pdf_renderer.py` : `ATS_TEMPLATES = ["sidebar_elegance", "executive_minimalist", "classique"]`.

`backend/tests/test_resumes_api.py`, ajouter :

```python
def test_generate_accepts_classique(client):
    res, insert_one = _post_generate(client, {"template": "classique"})
    assert res.status_code == 200
    assert insert_one.call_args.args[0]["template"] == "classique"
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run : `cd backend && uv run pytest tests/test_cv_templates.py tests/test_cv_pdf_renderer.py tests/test_resumes_api.py -v -k classique`
Attendu : FAIL. « classique » retombe sur Sidebar (titre `cl-band` absent, `<img` présent), et l'API renvoie 422.

- [ ] **Step 3: Étendre le registre**

Dans `backend/app/services/cv_templates.py` :
```python
CV_TEMPLATES = ("sidebar_elegance", "executive_minimalist", "classique")
CV_TEMPLATES_WITHOUT_PHOTO: frozenset = frozenset({"classique"})
```

- [ ] **Step 4: Créer `backend/app/templates/cv/classique.html`**

Maquette : `classique-layout.html`, choix B. Ce gabarit ne référence jamais `photo_url`.

```html
<!DOCTYPE html>
<html lang="fr">
{% import "_macros.html" as m %}
<head>
  <meta charset="UTF-8">
  <title>{{ candidate.full_name }} - {{ cv.target_role_title }}</title>
  <style>
    {{ base_css }}

    body { font-size: 9pt; color: var(--color-slate-900); }

    .cl-header { margin-bottom: 10px; }
    /* L'accent ne colore que le nom et le titre visé ; le reste reste sobre, lisible en noir et blanc. */
    .cl-name { font-size: 20pt; font-weight: 700; line-height: 1.1; color: var(--accent); }
    .cl-role { font-size: 11pt; font-weight: 600; color: var(--accent); margin-top: 3px; }

    .cl-contact {
      display: flex;
      flex-wrap: wrap;
      column-gap: 12px;
      row-gap: 2px;
      font-size: 8.5pt;
      color: var(--color-slate-600);
      margin-top: 6px;
    }

    .cl-contact .icon { stroke: var(--color-slate-600); }
    .cl-summary { color: var(--color-slate-800); line-height: 1.45; }

    .cl-band {
      background: var(--color-slate-100);
      color: var(--color-slate-900);
      font-size: 9pt;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      padding: 3px 8px;
      margin: 12px 0 6px;
    }

    .cl-item { margin-bottom: 8px; }

    .cl-row {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
    }

    .cl-dates { color: var(--color-slate-600); font-size: 8.5pt; white-space: nowrap; }
    .cl-item ul, .cl-list { padding-left: 16px; margin-top: 2px; }
    .cl-item li, .cl-list li { margin-bottom: 1px; }
    .cl-line { margin-bottom: 3px; }
  </style>
</head>
<body>
  <header class="cl-header">
    <h1 class="cl-name">{{ candidate.full_name }}</h1>
    <div class="cl-role">{{ cv.target_role_title }}</div>
    <div class="cl-contact">{{ m.contacts(candidate) }}</div>
    {{ m.mobility_line(candidate) }}
  </header>

  {% if cv.professional_summary %}
  <p class="cl-summary">{{ cv.professional_summary }}</p>
  {% endif %}

  {% if cv.experiences %}
  <h2 class="cl-band">{{ SECTION_TITLES.experience }}</h2>
  {% for exp in cv.experiences %}
  <article class="cl-item page-break-avoid">
    <div class="cl-row">
      <span><strong>{{ exp.title }}</strong> — {{ exp.company }}{% if exp.location %}, {{ exp.location }}{% endif %}</span>
      <span class="cl-dates">{{ exp.start_date }} – {{ exp.end_date or 'Présent' }}</span>
    </div>
    {% if exp.bullet_points %}
    <ul>
      {% for bp in exp.bullet_points %}
      <li>{{ bp }}</li>
      {% endfor %}
    </ul>
    {% endif %}
    {% if exp.relevant_technologies %}{{ m.tools_line(exp.relevant_technologies) }}{% endif %}
  </article>
  {% endfor %}
  {% endif %}

  {% if cv.featured_projects %}
  <h2 class="cl-band">{{ SECTION_TITLES.projects }}</h2>
  {% for proj in cv.featured_projects %}
  <div class="cl-item page-break-avoid">
    <strong>{{ proj.name }}</strong>{% if proj.url %} ({{ proj.url }}){% endif %} — {{ proj.description }}
    {% if proj.technologies %}{{ m.tools_line(proj.technologies) }}{% endif %}
  </div>
  {% endfor %}
  {% endif %}

  {% if cv.certifications %}
  <h2 class="cl-band">{{ SECTION_TITLES.certifications }}</h2>
  <ul class="cl-list">
    {% for cert in cv.certifications %}
    <li>{{ cert }}</li>
    {% endfor %}
  </ul>
  {% endif %}

  {% if cv.prioritized_skills %}
  <h2 class="cl-band">{{ SECTION_TITLES.skills }}</h2>
  {% for group in cv.prioritized_skills %}
  <div class="cl-line"><strong>{{ group.category }}</strong> : {{ group.skills | join(" · ") }}</div>
  {% endfor %}
  {% endif %}

  {% if cv.education %}
  <h2 class="cl-band">{{ SECTION_TITLES.education }}</h2>
  {% for edu in cv.education %}
  <div class="cl-row cl-line">
    <span><strong>{{ edu.degree }}</strong> — {{ edu.institution }}{% if edu.details %} ({{ edu.details }}){% endif %}</span>
    <span class="cl-dates">{{ edu.year }}</span>
  </div>
  {% endfor %}
  {% endif %}

  {% if cv.languages %}
  <h2 class="cl-band">{{ SECTION_TITLES.languages }}</h2>
  <div class="cl-line">
    {% for lang in cv.languages %}{{ lang.language }} ({{ lang.level }}){% if not loop.last %} · {% endif %}{% endfor %}
  </div>
  {% endif %}

  {% if candidate.interests %}
  <h2 class="cl-band">{{ SECTION_TITLES.interests }}</h2>
  <div class="cl-line">{{ candidate.interests | join(" · ") }}</div>
  {% endif %}
</body>
</html>
```

- [ ] **Step 5: Vérifier que tout passe**

Run : `cd backend && uv run pytest tests/test_cv_templates.py tests/test_cv_pdf_renderer.py tests/test_resumes_api.py -v`
Attendu : PASS.

- [ ] **Step 6: Point d'arrêt — pas de commit sans demande de l'utilisateur**

---

### Task 7: Modèle Créatif

**Files:**
- Create: `backend/app/templates/cv/creatif.html`
- Modify: `backend/app/services/cv_templates.py` (registre)
- Test: `backend/tests/test_cv_templates.py`, `backend/tests/test_cv_pdf_renderer.py`

**Interfaces:**
- Consumes : macros, `SECTION_TITLES`.
- Produces : `CV_TEMPLATES = ("sidebar_elegance", "executive_minimalist", "classique", "creatif")`, l'ordre définitif, repris tel quel par la constante frontend (Tâche 8).

- [ ] **Step 1: Écrire les tests qui échouent**

`backend/tests/test_cv_templates.py` :
- remplacer la ligne `TEMPLATES = […]` par `TEMPLATES = list(CV_TEMPLATES)`, et ajouter `CV_TEMPLATES` à l'import `from app.services.cv_templates import …` en tête de fichier ;
- remplacer la liste `ATS_SAFE_TEMPLATES` par `ATS_SAFE_TEMPLATES = TEMPLATES` ;
- ajouter :

```python
def test_registry_lists_four_templates_in_display_order():
    assert CV_TEMPLATES == ("sidebar_elegance", "executive_minimalist", "classique", "creatif")


def test_creatif_photo_is_optional_and_never_a_monogram():
    with_photo = render_cv_html(
        cv=SAMPLE_CV, candidate=SAMPLE_CANDIDATE, template_name="creatif",
        with_photo=True, photo_url="https://example.com/avatar.jpg",
    )
    assert 'class="cr-photo"' in with_photo
    without = _render("creatif")
    assert "<img" not in without
    assert "<canvas" not in without


def test_creatif_titles_have_dot_and_rule():
    html = _render("creatif")
    assert '<span class="cr-dot"></span><span>Expérience professionnelle</span><span class="cr-rule"></span>' in html


def test_creatif_footer_titles_followed_by_their_content():
    html = _render("creatif", interests=["Randonnée"])
    positions = [
        html.index(">Formation<"),
        html.index("Master Informatique"),
        html.index(">Langues<"),
        html.index("C1 - Professionnel courant"),
        html.index(">Centres d'intérêt<"),
        html.index("Randonnée"),
    ]
    assert positions == sorted(positions)
```

`backend/tests/test_cv_pdf_renderer.py` : remplacer la liste par `ATS_TEMPLATES = list(CV_TEMPLATES)`, et étendre l'import en `from app.services.cv_templates import CV_TEMPLATES, SECTION_TITLES`.

- [ ] **Step 2: Vérifier qu'ils échouent**

Run : `cd backend && uv run pytest tests/test_cv_templates.py tests/test_cv_pdf_renderer.py -v -k "creatif or four_templates"`
Attendu : FAIL. Le registre n'a que trois modèles, et « creatif » retombe sur Sidebar.

- [ ] **Step 3: Étendre le registre**

```python
CV_TEMPLATES = ("sidebar_elegance", "executive_minimalist", "classique", "creatif")
```

- [ ] **Step 4: Créer `backend/app/templates/cv/creatif.html`**

Maquette : `creatif-layout-v2.html`, choix B.

```html
<!DOCTYPE html>
<html lang="fr">
{% import "_macros.html" as m %}
<head>
  <meta charset="UTF-8">
  <title>{{ candidate.full_name }} - {{ cv.target_role_title }}</title>
  <style>
    {{ base_css }}

    .cr-card {
      display: flex;
      align-items: center;
      gap: 12px;
      background: var(--accent-tint);
      border-radius: 10px;
      padding: 13px 14px;
      margin-bottom: 10px;
    }

    .cr-photo { width: 44px; height: 44px; border-radius: 50%; object-fit: cover; flex: none; }

    .cr-name {
      font-size: 21pt;
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1.05;
      color: var(--color-slate-900);
    }

    .cr-role { font-size: 10.5pt; font-weight: 600; color: var(--accent); margin-top: 3px; }

    .cr-contact {
      display: flex;
      flex-wrap: wrap;
      column-gap: 12px;
      row-gap: 2px;
      font-size: 8pt;
      color: var(--color-slate-600);
      margin-top: 6px;
    }

    .cr-body { padding: 0 2px; }
    .cr-summary { font-size: 8.8pt; color: var(--color-slate-700); line-height: 1.5; }

    .cr-title {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 10pt;
      font-weight: 700;
      color: var(--color-slate-900);
      margin: 13px 0 6px;
    }

    .cr-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--accent); flex: none; }
    .cr-rule { flex: 1; height: 1px; background: var(--accent-line); }
    .cr-item { margin-bottom: 9px; }

    .cr-row {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 10px;
    }

    .cr-dates { font-size: 8pt; color: var(--color-slate-500); white-space: nowrap; }
    .cr-item ul { padding-left: 14px; margin-top: 2px; }
    .cr-item li { font-size: 8.5pt; color: var(--color-slate-700); margin-bottom: 2px; line-height: 1.35; }
    .cr-skill-row { display: flex; gap: 8px; align-items: baseline; margin-bottom: 4px; }
    .cr-skill-cat { width: 20%; flex: none; font-size: 8pt; font-weight: 600; color: var(--color-slate-600); }
    .cr-cert { font-size: 8.5pt; color: var(--color-slate-700); margin-bottom: 3px; }

    .cr-footer { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 14px; }

    .cr-lbl {
      font-size: 7.5pt;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--accent);
      margin-bottom: 4px;
    }

    .cr-footer-line { font-size: 8pt; color: var(--color-slate-700); margin-bottom: 3px; }
    .cr-muted { color: var(--color-slate-500); }
  </style>
</head>
<body>
  <header class="cr-card">
    {% if with_photo and photo_url %}
    <img class="cr-photo" src="{{ photo_url }}" alt="" />
    {% endif %}
    <div>
      <h1 class="cr-name">{{ candidate.full_name }}</h1>
      <div class="cr-role">{{ cv.target_role_title }}</div>
      <div class="cr-contact">{{ m.contacts(candidate) }}</div>
      {{ m.mobility_line(candidate) }}
    </div>
  </header>

  <div class="cr-body">
    {% if cv.professional_summary %}
    <p class="cr-summary">{{ cv.professional_summary }}</p>
    {% endif %}

    {% if cv.experiences %}
    <h2 class="cr-title"><span class="cr-dot"></span><span>{{ SECTION_TITLES.experience }}</span><span class="cr-rule"></span></h2>
    {% for exp in cv.experiences %}
    <article class="cr-item page-break-avoid">
      <div class="cr-row">
        <span><strong>{{ exp.title }}</strong> · {{ exp.company }}{% if exp.location %}, {{ exp.location }}{% endif %}</span>
        <span class="cr-dates">{{ exp.start_date }} – {{ exp.end_date or 'Présent' }}</span>
      </div>
      {% if exp.bullet_points %}
      <ul>
        {% for bp in exp.bullet_points %}
        <li>{{ bp }}</li>
        {% endfor %}
      </ul>
      {% endif %}
      {% if exp.relevant_technologies %}{{ m.tools_line(exp.relevant_technologies) }}{% endif %}
    </article>
    {% endfor %}
    {% endif %}

    {% if cv.prioritized_skills %}
    <h2 class="cr-title"><span class="cr-dot"></span><span>{{ SECTION_TITLES.skills }}</span><span class="cr-rule"></span></h2>
    {% for group in cv.prioritized_skills %}
    <div class="cr-skill-row">
      <div class="cr-skill-cat">{{ group.category }}</div>
      <div>{{ m.chips(group.skills) }}</div>
    </div>
    {% endfor %}
    {% endif %}

    {% if cv.certifications %}
    <h2 class="cr-title"><span class="cr-dot"></span><span>{{ SECTION_TITLES.certifications }}</span><span class="cr-rule"></span></h2>
    {% for cert in cv.certifications %}
    <div class="cr-cert">{{ cert }}</div>
    {% endfor %}
    {% endif %}

    {% if cv.featured_projects %}
    <h2 class="cr-title"><span class="cr-dot"></span><span>{{ SECTION_TITLES.projects }}</span><span class="cr-rule"></span></h2>
    {% for proj in cv.featured_projects %}
    <div class="cr-item page-break-avoid">
      <strong>{{ proj.name }}</strong>{% if proj.url %} <span class="cr-muted">({{ proj.url }})</span>{% endif %} — {{ proj.description }}
      {% if proj.technologies %}{{ m.tools_line(proj.technologies) }}{% endif %}
    </div>
    {% endfor %}
    {% endif %}

    {% if cv.education or cv.languages or candidate.interests %}
    <div class="cr-footer">
      {% if cv.education %}
      <div>
        <h2 class="cr-lbl">{{ SECTION_TITLES.education }}</h2>
        {% for edu in cv.education %}
        <div class="cr-footer-line">
          {{ edu.degree }}<br><span class="cr-muted">{{ edu.institution }} · {{ edu.year }}</span>
          {% if edu.details %}<br><span class="cr-muted">{{ edu.details }}</span>{% endif %}
        </div>
        {% endfor %}
      </div>
      {% endif %}
      {% if cv.languages %}
      <div>
        <h2 class="cr-lbl">{{ SECTION_TITLES.languages }}</h2>
        {% for lang in cv.languages %}
        <div class="cr-footer-line">{{ lang.language }} {{ lang.level }}</div>
        {% endfor %}
      </div>
      {% endif %}
      {% if candidate.interests %}
      <div>
        <h2 class="cr-lbl">{{ SECTION_TITLES.interests }}</h2>
        <div class="cr-footer-line">{{ candidate.interests | join(" · ") }}</div>
      </div>
      {% endif %}
    </div>
    {% endif %}
  </div>
</body>
</html>
```

- [ ] **Step 5: Vérifier que toute la suite backend touchée passe**

Run : `cd backend && uv run pytest tests/test_cv_templates.py tests/test_cv_pdf_renderer.py tests/test_resumes_api.py -v`
Attendu : PASS, avec quatre modèles sur chaque contrôle ATS.

- [ ] **Step 6: Point d'arrêt — pas de commit sans demande de l'utilisateur**

---

### Task 8: Constante frontend, types, client API, pastilles, carte

**Files:**
- Create: `frontend/src/lib/cvTemplates.ts`
- Create: `frontend/src/components/resumes/AccentSwatches.tsx`
- Create: `backend/tests/test_cv_registry_parity.py`
- Modify: `frontend/src/types/resume.ts:46-72`
- Modify: `frontend/src/lib/api.ts:20` et `:768-830` uniquement
- Modify: `frontend/src/components/resumes/ResumeCard.tsx:1-6, 46, 87`
- Modify: `frontend/src/app/resumes/page.tsx` (appels `generate` et `update`, adaptation minimale)
- Modify: `frontend/src/components/resumes/ResumePreviewModal.tsx:17-18, 73, 99` (adaptation minimale)

**Interfaces:**
- Consumes : registre backend final (Tâche 7).
- Produces :
  - dans `@/lib/cvTemplates` :
    - `CV_TEMPLATES` (`readonly {key, label, hint, supportsPhoto}[]`) et `CV_ACCENTS` (`readonly {key, label, primary}[]`) ;
    - types `CvTemplateKey`, `CvAccentKey`, `CvTemplate`, `ResumeAppearance { template: CvTemplateKey; accent: CvAccentKey; withPhoto: boolean }` ;
    - `DEFAULT_TEMPLATE`, `DEFAULT_ACCENT` ;
    - `resolveTemplateKey(value?: string | null): CvTemplateKey`, `resolveAccentKey(value?: string | null): CvAccentKey`, `getTemplate(key: CvTemplateKey): CvTemplate`.
  - Dans `@/types/resume` : `PdfOptions { template?: CvTemplateKey; accent?: CvAccentKey; withPhoto?: boolean }` ; `TailoredResume.accent?: string`.
  - `resumeApi.downloadPdf(id: string, options?: PdfOptions, filename?: string)` et `resumeApi.getPdfBlobUrl(id: string, options?: PdfOptions)`.
  - Composant `<AccentSwatches value={CvAccentKey} onChange={(k: CvAccentKey) => void} disabled? />`.

- [ ] **Step 1: Écrire le test de parité qui échoue**

Créer `backend/tests/test_cv_registry_parity.py` :

```python
"""La constante frontend reprend le registre backend : mêmes clés, même ordre, mêmes couleurs."""
import re
from pathlib import Path

import pytest

from app.services.cv_templates import CV_ACCENTS, CV_TEMPLATES, CV_TEMPLATES_WITHOUT_PHOTO

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
CONSTANT_FILE = FRONTEND_DIR / "src" / "lib" / "cvTemplates.ts"


@pytest.fixture
def source():
    if not FRONTEND_DIR.exists():
        pytest.skip("frontend absent (conteneur backend seul)")
    return CONSTANT_FILE.read_text(encoding="utf-8")


def test_template_keys_match_registry(source):
    keys = re.findall(r'key: "([a-z_]+)",\s*label: "[^"]+",\s*hint:', source)
    assert tuple(keys) == CV_TEMPLATES


def test_photo_support_matches_registry(source):
    entries = re.findall(r'key: "([a-z_]+)",[^}]*supportsPhoto: (true|false)', source)
    assert {key for key, value in entries if value == "false"} == set(CV_TEMPLATES_WITHOUT_PHOTO)


def test_accent_colors_match_registry(source):
    pairs = re.findall(r'key: "([a-z_]+)", label: "[^"]+", primary: "(#[0-9a-f]{6})"', source)
    assert dict(pairs) == {key: colors["primary"] for key, colors in CV_ACCENTS.items()}
```

Run : `cd backend && uv run pytest tests/test_cv_registry_parity.py -v`
Attendu : FAIL, `FileNotFoundError` sur `cvTemplates.ts`.

- [ ] **Step 2: Créer `frontend/src/lib/cvTemplates.ts`**

Le format (une clé par objet, champs dans cet ordre) est lu par le test de parité.

```ts
// Miroir du registre backend (backend/app/services/cv_templates.py).
// backend/tests/test_cv_registry_parity.py vérifie que clés, ordre et couleurs concordent.

export const CV_TEMPLATES = [
  {
    key: "sidebar_elegance", label: "Sidebar Elegance",
    hint: "2 colonnes · tech, data, profils riches en compétences", supportsPhoto: true,
  },
  {
    key: "executive_minimalist", label: "Executive Minimalist",
    hint: "1 colonne épurée · cadres, conseil, finance", supportsPhoto: true,
  },
  {
    key: "classique", label: "Classique",
    hint: "Sobre, sans photo · logistique, industrie, RH", supportsPhoto: false,
  },
  {
    key: "creatif", label: "Créatif",
    hint: "En-tête en carte, photo possible · marketing, communication", supportsPhoto: true,
  },
] as const;

export const CV_ACCENTS = [
  { key: "marine", label: "Marine", primary: "#1e3a8a" },
  { key: "bleu_vert", label: "Bleu-vert", primary: "#0f766e" },
  { key: "ardoise", label: "Ardoise", primary: "#4f6d8a" },
  { key: "sauge", label: "Sauge", primary: "#4d6b4f" },
  { key: "bordeaux", label: "Bordeaux", primary: "#8b1e3f" },
  { key: "graphite", label: "Graphite", primary: "#374151" },
] as const;

export type CvTemplate = (typeof CV_TEMPLATES)[number];
export type CvTemplateKey = CvTemplate["key"];
export type CvAccentKey = (typeof CV_ACCENTS)[number]["key"];

export const DEFAULT_TEMPLATE: CvTemplateKey = "sidebar_elegance";
export const DEFAULT_ACCENT: CvAccentKey = "marine";

export interface ResumeAppearance {
  template: CvTemplateKey;
  accent: CvAccentKey;
  withPhoto: boolean;
}

// Un document ancien ou corrompu peut porter une clé absente ou inconnue : même repli que le backend.
export function resolveTemplateKey(value?: string | null): CvTemplateKey {
  const key = (value ?? "").trim().toLowerCase();
  return CV_TEMPLATES.find((t) => t.key === key)?.key ?? DEFAULT_TEMPLATE;
}

export function resolveAccentKey(value?: string | null): CvAccentKey {
  const key = (value ?? "").trim().toLowerCase();
  return CV_ACCENTS.find((a) => a.key === key)?.key ?? DEFAULT_ACCENT;
}

export function getTemplate(key: CvTemplateKey): CvTemplate {
  return CV_TEMPLATES.find((t) => t.key === key) ?? CV_TEMPLATES[0];
}
```

Run : `cd backend && uv run pytest tests/test_cv_registry_parity.py -v`
Attendu : PASS.

- [ ] **Step 3: Créer `frontend/src/components/resumes/AccentSwatches.tsx`**

```tsx
"use client";

import { CV_ACCENTS, type CvAccentKey } from "@/lib/cvTemplates";

interface AccentSwatchesProps {
  value: CvAccentKey;
  onChange: (accent: CvAccentKey) => void;
  disabled?: boolean;
}

export default function AccentSwatches({ value, onChange, disabled = false }: AccentSwatchesProps) {
  return (
    <div className="flex items-center gap-1.5" role="group" aria-label="Couleur d'accent">
      {CV_ACCENTS.map((accent) => {
        const selected = accent.key === value;
        return (
          <button
            key={accent.key}
            type="button"
            onClick={() => onChange(accent.key)}
            disabled={disabled}
            aria-label={accent.label}
            aria-pressed={selected}
            title={accent.label}
            style={{ backgroundColor: accent.primary }}
            className={`w-5 h-5 rounded-full border transition-all disabled:opacity-50 ${
              selected
                ? "border-white ring-2 ring-white ring-offset-2 ring-offset-[#152238]"
                : "border-white/20 hover:scale-110"
            }`}
          />
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Mettre à jour `frontend/src/types/resume.ts`**

En tête du fichier :
```ts
import type { CvAccentKey, CvTemplateKey } from "@/lib/cvTemplates";

```

Remplacer `TailoredResume.template` (ligne 54) par :
```ts
  // Clés brutes du document Mongo (un ancien CV n'a pas `accent`) : lire via resolveTemplateKey / resolveAccentKey.
  template: string;
  accent?: string;
```

Remplacer les deux interfaces de requête (lignes 61-72) par :
```ts
export interface GenerateResumeRequest {
  offer_id: string;
  application_id?: string;
  template?: CvTemplateKey;
  accent?: CvAccentKey;
  with_photo?: boolean;
}

export interface UpdateResumeRequest {
  content?: Partial<TailoredCVSchema>;
  template?: CvTemplateKey;
  accent?: CvAccentKey;
  with_photo?: boolean;
}

export interface PdfOptions {
  template?: CvTemplateKey;
  accent?: CvAccentKey;
  withPhoto?: boolean;
}
```

- [ ] **Step 5: Mettre à jour `frontend/src/lib/api.ts` (deux zones seulement)**

`git diff frontend/src/lib/api.ts` d'abord.

Ligne 20 :
```ts
import { TailoredResume, GenerateResumeRequest, UpdateResumeRequest, PdfOptions } from "@/types/resume";
```

Juste après le commentaire `// API Tailored Resumes (CV Adaptés)` (ligne 768), avant `export const resumeApi = {`, insérer :
```ts
const pdfQuery = ({ template, accent, withPhoto }: PdfOptions): string => {
  const params = new URLSearchParams();
  if (template) params.append("template", template);
  if (accent) params.append("accent", accent);
  if (withPhoto !== undefined) params.append("with_photo", withPhoto ? "true" : "false");
  const query = params.toString();
  return query ? `?${query}` : "";
};

```

Dans `downloadPdf`, remplacer la signature et les quatre lignes `params` / `query` par :
```ts
  downloadPdf: async (id: string, options: PdfOptions = {}, filename?: string): Promise<void> => {
    const query = pdfQuery(options);
    const token = getToken();
```
Dans `getPdfBlobUrl`, de même :
```ts
  getPdfBlobUrl: async (id: string, options: PdfOptions = {}): Promise<string> => {
    const query = pdfQuery(options);
    const token = getToken();
```
Le reste des deux fonctions (`fetch`, gestion d'erreur, blob) ne change pas.

- [ ] **Step 6: Adapter les appelants**

`frontend/src/components/resumes/ResumeCard.tsx` :
- après l'import de `resumeApi`, ajouter :
```ts
import { getTemplate, resolveAccentKey, resolveTemplateKey } from "@/lib/cvTemplates";
```
- ligne 46 :
```ts
      await resumeApi.downloadPdf(
        resumeId,
        {
          template: resolveTemplateKey(resume.template),
          accent: resolveAccentKey(resume.accent),
          withPhoto: resume.with_photo,
        },
        filename,
      );
```
- ligne 87 :
```tsx
            {getTemplate(resolveTemplateKey(resume.template)).label}
```

`frontend/src/app/resumes/page.tsx`, adaptation minimale (les Tâches 9 et 10 remplacent ces lignes) :
- ajouter l'import :
```ts
import { resolveAccentKey, resolveTemplateKey } from "@/lib/cvTemplates";
```
- dans `handleGenerateSubmit` : `template: resolveTemplateKey(selectedTemplate),`
- dans `handleUpdateTemplate` : `const updated = await resumeApi.update(id, { template: resolveTemplateKey(template), with_photo: withPhoto });`
- dans `handleRegenerateResume`, remplacer `template: resume.template,` par :
```ts
        template: resolveTemplateKey(resume.template),
        accent: resolveAccentKey(resume.accent),
```

`frontend/src/components/resumes/ResumePreviewModal.tsx`, adaptation minimale :
- ajouter l'import :
```ts
import { resolveTemplateKey } from "@/lib/cvTemplates";
```
- ligne 73 : `const url = await resumeApi.getPdfBlobUrl(resumeId, { template: resolveTemplateKey(selectedTemplate), withPhoto });`
- ligne 99 : `await resumeApi.downloadPdf(resumeId, { template: resolveTemplateKey(selectedTemplate), withPhoto }, filename);`

- [ ] **Step 7: Vérifier**

Run : `cd frontend && npm run lint && npm run build`
Attendu : aucune erreur. Les avertissements `react-hooks/exhaustive-deps` existants sont tolérés.

Run : `cd backend && uv run pytest tests/test_cv_registry_parity.py -v`
Attendu : PASS.

- [ ] **Step 8: Point d'arrêt — pas de commit sans demande de l'utilisateur**

---

### Task 9: Fenêtre « Générer mon CV » : quatre cartes et couleur

**Files:**
- Modify: `frontend/src/app/resumes/page.tsx` (imports, l.35, l.100-104, l.401-430)

**Interfaces:**
- Consumes : `CV_TEMPLATES`, `DEFAULT_TEMPLATE`, `DEFAULT_ACCENT`, `CvTemplateKey`, `CvAccentKey` ; `AccentSwatches` (Tâche 8).
- Produces : la requête `generate` envoie `template` et `accent` choisis.

- [ ] **Step 1: Imports et état**

Remplacer l'import ajouté en Tâche 8 par :
```ts
import {
  CV_TEMPLATES,
  DEFAULT_ACCENT,
  DEFAULT_TEMPLATE,
  resolveAccentKey,
  resolveTemplateKey,
  type CvAccentKey,
  type CvTemplateKey,
} from "@/lib/cvTemplates";
import AccentSwatches from "@/components/resumes/AccentSwatches";
```

Ligne 35, remplacer l'état du modèle par :
```ts
  const [selectedTemplate, setSelectedTemplate] = useState<CvTemplateKey>(DEFAULT_TEMPLATE);
  const [selectedAccent, setSelectedAccent] = useState<CvAccentKey>(DEFAULT_ACCENT);
```

- [ ] **Step 2: Requête de génération**

Dans `handleGenerateSubmit` :
```ts
      const newResume = await resumeApi.generate({
        offer_id: selectedOfferId,
        template: selectedTemplate,
        accent: selectedAccent,
        with_photo: false,
      });
```

- [ ] **Step 3: Cartes et pastilles**

Remplacer tout le bloc `<div>` « Modèle de départ » (lignes 401-430, de `<div>` à son `</div>` fermant, avant le pied du formulaire) par :
```tsx
              <div>
                <div className="block text-xs font-semibold text-slate-300 mb-1.5">Modèle</div>
                <div className="grid grid-cols-2 gap-3">
                  {CV_TEMPLATES.map((tmpl) => {
                    const selected = selectedTemplate === tmpl.key;
                    return (
                      <button
                        key={tmpl.key}
                        type="button"
                        onClick={() => setSelectedTemplate(tmpl.key)}
                        aria-pressed={selected}
                        className={`text-left border rounded-xl p-3 text-xs transition-all ${
                          selected
                            ? "border-blue-500 bg-blue-900/30 text-white"
                            : "border-slate-800 bg-slate-900/40 text-slate-400 hover:border-slate-700"
                        }`}
                      >
                        <div className="font-semibold mb-0.5">{tmpl.label}</div>
                        <div className="text-[11px] text-slate-400">{tmpl.hint}</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <div className="block text-xs font-semibold text-slate-300 mb-1.5">Couleur</div>
                <AccentSwatches value={selectedAccent} onChange={setSelectedAccent} />
              </div>
```

- [ ] **Step 4: Vérifier**

Run : `cd frontend && npm run lint && npm run build`
Attendu : aucune erreur.

- [ ] **Step 5: Point d'arrêt — pas de commit sans demande de l'utilisateur**

---

### Task 10: Aperçu : barre Modèle / Couleur / Photo, gardes de concurrence

**Files:**
- Modify: `frontend/src/components/resumes/ResumePreviewModal.tsx` (imports, props l.20-37, état l.39-48, effets l.53-87, handlers l.93-157, en-tête l.209 et 241-317)
- Modify: `frontend/src/app/resumes/page.tsx` (`handleUpdateTemplate`, filtre l.178-184 et 231-239, prop l.298)

**Interfaces:**
- Consumes : `CV_TEMPLATES`, `getTemplate`, `resolveTemplateKey`, `resolveAccentKey`, `ResumeAppearance`, `AccentSwatches`, `resumeApi.getPdfBlobUrl(id, PdfOptions)`, `resumeApi.downloadPdf(id, PdfOptions, filename)`.
- Produces : la prop `onUpdateAppearance?: (resumeId: string, appearance: ResumeAppearance) => Promise<void>` remplace `onUpdateTemplate`.

- [ ] **Step 1: Imports, props et état de la modale**

Imports :
```ts
import { useEffect, useRef, useState } from "react";
```
Remplacer l'import `resolveTemplateKey` de la Tâche 8 par :
```ts
import {
  CV_TEMPLATES,
  DEFAULT_ACCENT,
  DEFAULT_TEMPLATE,
  getTemplate,
  resolveAccentKey,
  resolveTemplateKey,
  type CvAccentKey,
  type CvTemplateKey,
  type ResumeAppearance,
} from "@/lib/cvTemplates";
import AccentSwatches from "@/components/resumes/AccentSwatches";
```

Dans l'interface des props et la déstructuration, remplacer `onUpdateTemplate` par :
```ts
  onUpdateAppearance?: (resumeId: string, appearance: ResumeAppearance) => Promise<void>;
```

État : remplacer `const [selectedTemplate, setSelectedTemplate] = useState<string>("sidebar_elegance");` par :
```ts
  const [selectedTemplate, setSelectedTemplate] = useState<CvTemplateKey>(DEFAULT_TEMPLATE);
  const [selectedAccent, setSelectedAccent] = useState<CvAccentKey>(DEFAULT_ACCENT);
```
et, après `const [error, setError] = …`, ajouter :
```ts
  // Numéro du dernier chargement de PDF : une réponse plus ancienne est ignorée (clics rapides).
  const pdfRequestRef = useRef(0);
  // Les PUT d'apparence partent l'un après l'autre : le dernier clic est le dernier enregistré.
  const appearanceQueueRef = useRef<Promise<void>>(Promise.resolve());
```

- [ ] **Step 2: Effets et chargement du PDF**

Remplacer l'effet d'initialisation (lignes 53-62) par :
```ts
  useEffect(() => {
    if (resume) {
      setSelectedTemplate(resolveTemplateKey(resume.template));
      setSelectedAccent(resolveAccentKey(resume.accent));
      setWithPhoto(resume.with_photo || false);
      setEditableContent(resume.content ? JSON.parse(JSON.stringify(resume.content)) : null);
    }
    if (initialTab) {
      setActiveTab(initialTab);
    }
    // Réinitialiser à l'ouverture ou au changement de CV seulement : la réponse tardive d'un PUT
    // d'apparence ne doit pas écraser la couleur choisie entre-temps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resume?.id, resume?._id, isOpen, initialTab]);
```

Remplacer `loadPdf` et son effet (lignes 64-87) par :
```ts
  const loadPdf = async () => {
    if (!resume || !isOpen) return;
    const resumeId = resume.id || resume._id;
    if (!resumeId) return;

    const requestId = ++pdfRequestRef.current;
    setLoadingPdf(true);
    setError(null);
    try {
      const url = await resumeApi.getPdfBlobUrl(resumeId, {
        template: selectedTemplate,
        accent: selectedAccent,
        withPhoto,
      });
      if (requestId !== pdfRequestRef.current) {
        window.URL.revokeObjectURL(url);
        return;
      }
      setPdfUrl((previous) => {
        if (previous) window.URL.revokeObjectURL(previous);
        return url;
      });
    } catch (err: unknown) {
      if (requestId !== pdfRequestRef.current) return;
      console.error("Failed to load CV PDF preview:", err);
      setError("Erreur lors de la génération de l'aperçu PDF.");
    } finally {
      if (requestId === pdfRequestRef.current) setLoadingPdf(false);
    }
  };

  // Pas de dépendance à updated_at : chaque PUT d'apparence déclencherait un second rendu Chromium.
  useEffect(() => {
    if (activeTab === "preview") {
      loadPdf();
    }
  }, [resume?.id, resume?._id, selectedTemplate, selectedAccent, withPhoto, isOpen, activeTab]);
```

- [ ] **Step 3: Handlers**

Après `const resumeId = resume.id || resume._id || "";` ajouter :
```ts
  const supportsPhoto = getTemplate(selectedTemplate).supportsPhoto;

  const saveAppearance = (appearance: ResumeAppearance) => {
    if (!onUpdateAppearance) return;
    appearanceQueueRef.current = appearanceQueueRef.current
      .then(() => onUpdateAppearance(resumeId, appearance))
      .catch((err) => console.error("Failed to save CV appearance:", err));
  };
```

Dans `handleDownload` :
```ts
      await resumeApi.downloadPdf(
        resumeId,
        { template: selectedTemplate, accent: selectedAccent, withPhoto },
        filename,
      );
```

Remplacer `handleTemplateChange` et `handlePhotoToggle` (lignes 108-121) par :
```ts
  const handleTemplateChange = (template: CvTemplateKey) => {
    setSelectedTemplate(template);
    saveAppearance({ template, accent: selectedAccent, withPhoto });
  };

  const handleAccentChange = (accent: CvAccentKey) => {
    setSelectedAccent(accent);
    saveAppearance({ template: selectedTemplate, accent, withPhoto });
  };

  const handlePhotoToggle = () => {
    const next = !withPhoto;
    setWithPhoto(next);
    saveAppearance({ template: selectedTemplate, accent: selectedAccent, withPhoto: next });
  };
```

Dans `handleSaveContent`, supprimer la ligne `await loadPdf();` et son commentaire `// Reload preview`. `setActiveTab("preview")` qui suit déclenche le rechargement par l'effet.

- [ ] **Step 4: En-tête et seconde barre d'outils**

Ligne 209, sous-titre :
```tsx
              CV vectoriel A4 certifié ATS • Modèle {getTemplate(selectedTemplate).label}
```

Supprimer de l'en-tête les deux blocs `{/* Template Selector (in preview mode) */}` et `{/* Photo Toggle */}` (lignes 241-283).

Juste après la fermeture de l'en-tête (le `</div>` de la ligne 317, avant `{/* Modal Body */}`), insérer :
```tsx
        {activeTab === "preview" && (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-6 py-2.5 border-b border-slate-800 bg-[#131d31] text-xs">
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Modèle</span>
              <div className="flex bg-slate-900/60 p-1 rounded-lg border border-slate-700/60">
                {CV_TEMPLATES.map((tmpl) => (
                  <button
                    key={tmpl.key}
                    type="button"
                    onClick={() => handleTemplateChange(tmpl.key)}
                    aria-pressed={selectedTemplate === tmpl.key}
                    title={tmpl.hint}
                    className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                      selectedTemplate === tmpl.key
                        ? "bg-blue-600 text-white shadow-sm"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    {tmpl.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-slate-400">Couleur</span>
              <AccentSwatches value={selectedAccent} onChange={handleAccentChange} />
            </div>

            {/* Masqué pour un modèle sans photo ; le choix est conservé pour les autres modèles. */}
            {supportsPhoto && (
              <button
                type="button"
                onClick={handlePhotoToggle}
                aria-pressed={withPhoto}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg border font-medium transition-colors ${
                  withPhoto
                    ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                    : "bg-slate-800/80 border-slate-700 text-slate-400 hover:text-slate-200"
                }`}
                title="Afficher ou masquer la photo"
              >
                <FiImage />
                <span>Photo : {withPhoto ? "Oui" : "Non"}</span>
              </button>
            )}
          </div>
        )}
```

- [ ] **Step 5: Page : apparence et filtre**

Dans `frontend/src/app/resumes/page.tsx`, ajouter `type ResumeAppearance` à l'import `@/lib/cvTemplates`, puis remplacer `handleUpdateTemplate` par :
```ts
  const handleUpdateAppearance = async (id: string, appearance: ResumeAppearance) => {
    try {
      const updated = await resumeApi.update(id, {
        template: appearance.template,
        accent: appearance.accent,
        with_photo: appearance.withPhoto,
      });
      setResumes((prev) => prev.map((r) => ((r.id || r._id) === id ? updated : r)));
      setActiveResumeForPreview((current) =>
        current && (current.id || current._id) === id ? updated : current
      );
    } catch (err) {
      console.error("Failed to update resume appearance:", err);
    }
  };
```

Prop de la modale (ligne 298) : `onUpdateAppearance={handleUpdateAppearance}`.

Filtre, ligne 182 :
```ts
    const matchesTemplate = templateFilter === "all" || resolveTemplateKey(r.template) === templateFilter;
```
Options du `<select>` (lignes 237-238), remplacer les deux `<option>` en dur par :
```tsx
            {CV_TEMPLATES.map((tmpl) => (
              <option key={tmpl.key} value={tmpl.key}>{tmpl.label}</option>
            ))}
```

- [ ] **Step 6: Vérifier**

Run : `cd frontend && npm run lint && npm run build`
Attendu : aucune erreur.

Run : `rtk grep -rn -e "onUpdateTemplate" -e "executive_minimalist\"" frontend/src`
Attendu : aucune occurrence en dehors de `lib/cvTemplates.ts`.

- [ ] **Step 7: Point d'arrêt — pas de commit sans demande de l'utilisateur**

---

### Task 11: Vérification de bout en bout et contrôle visuel

**Files:** aucun fichier du dépôt modifié. Les PDF de contrôle vont dans le dossier temporaire.

- [ ] **Step 1: Suite backend complète**

Run : `cd backend && uv run pytest -v`
Attendu : PASS, ou les mêmes échecs qu'avant la Tâche 1. Comparer avec `git stash`, jamais sur les fichiers de l'utilisateur : en cas de doute, relancer seulement les fichiers de test touchés et signaler les autres échecs sans les corriger.

- [ ] **Step 2: Contrôle visuel, un PDF par modèle en deux couleurs**

```bash
cd backend && uv run python - <<'EOF'
import asyncio
import tempfile
from pathlib import Path

from app.services.cv_pdf_renderer import generate_cv_pdf
from app.services.cv_templates import CV_TEMPLATES, render_cv_html
from tests.test_cv_pdf_renderer import ATS_CANDIDATE, ATS_CV

out = Path(tempfile.gettempdir()) / "cv-modeles"
out.mkdir(exist_ok=True)
for template in CV_TEMPLATES:
    for accent in ("marine", "bordeaux"):
        html = render_cv_html(ATS_CV, ATS_CANDIDATE, template_name=template, accent=accent)
        (out / f"{template}_{accent}.pdf").write_bytes(asyncio.run(generate_cv_pdf(html)))
print(out)
print(sorted(p.name for p in out.iterdir()))
EOF
```

Ouvrir les huit PDF et vérifier à l'œil :
- police Inter, nom en 800 ;
- pastilles fines séparées par « · » ;
- icônes au trait dans la couleur d'accent (gris pour Classique) ;
- aucun poste coupé entre deux pages ;
- Sidebar : teinte de la colonne arrêtée avec son contenu, monogramme rond lisible ;
- Classique : accent sur le nom et le titre seulement, bandeaux gris ;
- Créatif : carte teintée, titres point + filet, pied de page sur trois colonnes.

Montrer les PDF à l'utilisateur avant de conclure.

- [ ] **Step 3: Vérification manuelle dans le navigateur**

Run : `docker compose up -d backend frontend mongodb` puis ouvrir http://localhost:3000/resumes.

Vérifier :
1. Fenêtre de génération : quatre cartes avec leur ligne d'aide, six pastilles, marine sélectionnée par défaut. Générer un CV en Créatif + Sauge : la carte affiche « Créatif ».
2. Aperçu : les quatre modèles en deux couleurs s'affichent.
3. Classique : le bouton Photo disparaît. Repasser à Sidebar : l'état Photo d'avant revient.
4. Cliquer vite sur cinq couleurs : l'aperçu finit sur la dernière couleur cliquée. Fermer, rouvrir : la même couleur est enregistrée.
5. Un CV généré avant ce chantier (sans `accent`) s'ouvre en marine, se télécharge, et le filtre « Modèle » le classe correctement.
6. Téléchargement depuis la carte : le PDF a le modèle et la couleur enregistrés.
7. Éditer le contenu puis enregistrer : l'aperçu se recharge une seule fois avec le nouveau texte.

- [ ] **Step 4: Point d'arrêt final — rapport à l'utilisateur, pas de commit sans demande**

Rapporter : résultat des suites, PDF de contrôle, points manuels vérifiés ou non, écarts au spec appliqués, et repli éventuel des pastilles (Tâche 4, étape 5).
