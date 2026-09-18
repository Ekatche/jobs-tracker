# Spécification Technique : Moteur de Génération de CV Tailored ATS

**Date** : 2026-09-18  
**Statut** : Validé  
**Auteur** : Antigravity & Équipe Architecture  
**Périmètre** : Phase 5B du Master Plan Career-Ops (`docs/CAREER_OPS_INTEGRATION_PLAN.md`)

---

## 1. Contexte & Objectifs

L'envoi de candidatures génériques produit des taux de conversion faibles : les recruteurs et les systèmes ATS (Greenhouse, Lever, Workable, Taleo) scannent les CVs en cherchant la nomenclature exacte et les compétences clés de la fiche de poste.
L'objectif de cette fonctionnalité est de générer automatiquement un **CV vectoriel sur-mesure au format A4**, parfaitement calibré pour l'offre visée :

1. **Non-hallucination stricte** : Aucun mensonge ni compétence inventée ; seules les données vérifiées du `CandidateProfile` sont utilisées, mais réordonnées, contextualisées et mises en valeur.
2. **Alignement sur l'évaluation Two-Pass (Bloc B)** : Exploitation directe des exigences prioritaires (`critical`, `high`, `meaningful`) et des preuves *verbatim* extraites lors de la Phase 3.
3. **Excellence esthétique européenne (Option B)** : Deux templates au choix adaptés aux standards européens :
   - **Template 1 : "Sidebar Elegance"** (Standard européen moderne à 2 colonnes avec volet latéral pour compétences, langues CECRL, formations, et toggle photo).
   - **Template 2 : "Executive Minimalist"** (Mono-colonne épurée et dense, inspirée des design systems de scale-ups et cabinets de conseil).
4. **Parsing ATS 100% garanti** : Vrai texte vectoriel sélectionnable, balisage sémantique propre (`<h1>`, `<h2>`, `<p>`, `<ul>`, `<li>`), aucun tableau imbriqué complexe, polices standards vectorisées.

---

## 2. Parcours Utilisateur (UX)

### 2.1 Points d'accès dans l'application
- **Page détaillée de l'offre** (`/offers/[id]`) : Bouton d'action principal *"Générer mon CV sur-mesure"*.
- **Sidebar Kanban** (`/applications`) : Onglet ou bouton direct *"CV adapté"* sur la carte de candidature.

### 2.2 Modale de prévisualisation & personnalisation
Lorsque l'utilisateur déclenche la génération :
1. **Contrôle de quota** : Appel backend vérifiant le quota mensuel (`require_user_quota(user, "cv_tailoring")`).
2. **Sélecteur de template (Option B)** :
   - Radio buttons interactifs : `Sidebar Elegance` (sélectionné par défaut) ou `Executive Minimalist`.
3. **Options de mise en page** :
   - `Toggle Photo` : Bascule entre photo de profil circulaire ou monogramme/initiales sobres (respect des préférences personnelles et contextes régionaux).
4. **Viewer PDF intégré** : Aperçu temps réel du document A4 généré dans le navigateur.
5. **Actions** :
   - `Télécharger le PDF` (nommé `CV_<Nom>_<Entreprise>_<Poste>.pdf`).
   - `Régénérer avec ajustements` (permet de forcer l'accent sur un projet ou une compétence précise).

---

## 3. Architecture du Moteur d'Adaptation IA (Agent "CV Tailor")

### 3.1 Données injectées en entrée (Context Fusion)
- **`CandidateProfile`** :
  - `experiences` : titres, entreprises, dates, descriptions et bullet points existants.
  - `projects` : projets GitHub, portfolio et réalisations marquantes.
  - `skills` & `technologies` : compétences vérifiées du profil.
  - `education` & `certifications` : diplômes, écoles/universités, années.
  - `languages` : langues et niveaux CECRL (Natif, C1, B2, etc.).
- **`JobOffer`** :
  - `poste`, `entreprise`, `localisation`, `type_contrat`, `description`.
- **`OfferEvaluationInDB` (Bloc B)** :
  - `requirement_matches` : exigences satisfaites avec niveau de priorité (`critical`, `high`, `meaningful`).
  - `missing_requirements` : points faibles ou exigences non couvertes (à ne surtout pas inventer).

### 3.2 Modèle de Données Pydantic (`TailoredCVContent`)

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class TailoredExperienceItem(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    start_date: str
    end_date: Optional[str] = "Présent"
    bullet_points: List[str] = Field(..., max_items=4, description="3-4 puces d'impact réordonnées et alignées sur l'offre")
    relevant_technologies: List[str] = []

class TailoredProjectItem(BaseModel):
    name: str
    description: str
    technologies: List[str]
    url: Optional[str] = None

class TailoredSkillGroup(BaseModel):
    category: str  # ex: "IA & Machine Learning", "Cloud & MLOps", "Langages"
    skills: List[str]

class TailoredLanguage(BaseModel):
    language: str
    level: str  # ex: "Natif", "C1 - Professionnel courant"

class TailoredEducationItem(BaseModel):
    degree: str
    institution: str
    year: str
    details: Optional[str] = None

class TailoredCVSchema(BaseModel):
    target_role_title: str
    professional_summary: str = Field(..., max_length=450, description="Accroche ciblée 3-4 lignes")
    prioritized_skills: List[TailoredSkillGroup]
    experiences: List[TailoredExperienceItem]
    featured_projects: List[TailoredProjectItem]
    education: List[TailoredEducationItem]
    languages: List[TailoredLanguage]
    certifications: Optional[List[str]] = []
```

### 3.3 Guardrails Anti-Hallucination
Une fonction pure `verify_cv_honesty(tailored: TailoredCVSchema, source: CandidateProfile) -> bool` vérifie avant compilation PDF :
1. Chaque entreprise listée provient obligatoirement du profil source.
2. Chaque diplôme provient du profil source.
3. Aucune technologie majeure citée dans `prioritized_skills` n'est inconnue du profil source (tolérance uniquement pour les synonymes exacts normalisés via `role_normalizer`).

---

## 4. Moteur de Rendu PDF & Templates HTML/CSS

### 4.1 Moteur de génération
- Moteur principal : **WeasyPrint** (Python) pour une conversion directe HTML+CSS vers PDF A4 vectoriel sans dépendance de navigateur externe.
- Polices typographiques intégrées localement : **Inter** et **Geist Sans** (formats WOFF2/TTF) garantissant un rendu identique en tout environnement (Docker, CI, production).

### 4.2 Spécification des Templates

#### Template 1 : "Sidebar Elegance" (`templates/cv/sidebar_elegance.html`)
- **Structure** : Conteneur CSS Grid / Flexbox à 2 colonnes avec ratio `28% / 72%`.
- **Sidebar gauche (fond #f4f6f8)** :
  - Photo ronde ou monogramme initiales dans un cercle raffiné.
  - Coordonnées : Email, Téléphone, Ville, Mobilité/Télétravail, Liens (LinkedIn, GitHub, Portfolio).
  - Compétences classées par groupe avec micro-badges.
  - Langues avec badges de niveau CECRL.
  - Formations / Diplômes.
  - Certifications.
- **Colonne droite (fond blanc pur)** :
  - En-tête : Nom en `font-weight: 700`, Titre du poste visé en couleur d'accentuation (bleu ardoise profond `#1e3a8a`).
  - Résumé professionnel d'impact (accroche personnalisée).
  - Expériences professionnelles avec puces aérées et technos en ligne.
  - Projets techniques majeurs avec métriques et liens.

#### Template 2 : "Executive Minimalist" (`templates/cv/executive_minimalist.html`)
- **Structure** : Mono-colonne séquentielle verticale à forte densité d'information.
- **En-tête centré ou aligné à gauche** : Nom, Titre, strip horizontal de coordonnées et liens cliquables.
- **Ligne de séparation fine** `#e2e8f0`.
- **Sections séquentielles** :
  - Résumé exécutif
  - Expériences professionnelles chronologiques
  - Projets sélectionnés
  - Compétences techniques & Certifications (badges gris clair)
  - Formation & Langues

### 4.3 Règles Paged Media (Impression A4)
```css
@page {
    size: A4;
    margin: 10mm 12mm;
}

@page :first {
    margin-top: 10mm;
}

/* Éviter la coupure disgracieuse d'une expérience sur deux pages */
.experience-block, .project-block {
    page-break-inside: avoid;
    break-inside: avoid;
}

h2 {
    page-break-after: avoid;
    break-after: avoid;
}
```

---

## 5. Endpoints API Backend (`app/routers/resumes.py`)

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/applications/{id}/tailored-cv/generate` | Déclenche l'Agent LLM d'adaptation et stocke le contenu structuré dans MongoDB. |
| `GET` | `/applications/{id}/tailored-cv` | Récupère le contenu JSON du CV sur-mesure pour prévisualisation ou édition. |
| `PUT` | `/applications/{id}/tailored-cv` | Permet à l'utilisateur de retoucher manuellement un champ avant export. |
| `GET` | `/applications/{id}/tailored-cv/pdf` | Retourne le flux binaire `application/pdf` avec query params `template=sidebar_elegance|executive_minimalist` et `with_photo=true|false`. |

---

## 6. Sécurité, Quotas et Multi-Tenant
- Chaque document et requête vérifie la correspondance stricte du `user_id` avec le token JWT actif.
- Chaque génération décompte une unité de quota sur `user_quotas.cv_tailoring` via le middleware existant `require_user_quota`.
- Les appels LLM sont tracés dans `api_usage` avec le modèle utilisé, la latence et le nombre de tokens.

---

## 7. Plan de Validation & Tests
1. **Tests unitaires de l'Agent d'adaptation** : Vérifier que le JSON produit est valide et que les bullet points correspondent aux exigences de l'offre.
2. **Test anti-hallucination** : Vérifier que toute compétence absente du profil source est détectée et rejetée.
3. **Test de rendu WeasyPrint** : Vérifier la compilation d'un PDF A4 valide pour les 2 templates avec et sans photo.
4. **Test de lisibilité ATS** : Extraction du texte brut via `pypdf` ou `pdfplumber` pour s'assurer que 100% des mots-clés et sections sont extraits dans le bon ordre logique.
