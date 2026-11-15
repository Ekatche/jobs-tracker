# Spec Design — Intégration Frontend Career-Ops v1.32+ & Modèles IA

Date : 2026-11-15  
Statut : Brouillon pour validation  
Périmètre : Frontend Next.js (`frontend/src/`)  

## 1. Objectif & Principes d'Architecture

Exposer dans l'interface Next.js l'ensemble des évolutions backend Career-Ops v1.32+ et des modèles LLM mis à jour (`openai/gpt-5.6-terra`, `gemini/gemini-3.8-flash`, `gemini/gemini-3.5-flash-lite`), tout en appliquant une discipline stricte de modularité :
- **Approche modulaire** : chaque nouvelle capacité est isolée dans un sous-composant dédié (≤ 300 lignes) afin de ne pas alourdir les pages historiques volumineuses (`offers/page.tsx`, `ApplicationDetails.tsx`, `ResumePreviewModal.tsx`).
- **Chargement à la demande** : les endpoints analytics (`/applications/pipeline/calibrate`, `/job-offers/analytics/skill-gaps`, `/resumes/{id}/ats-score`, `/resumes/{id}/export-text`) ne sont appelés qu'à l'ouverture de l'onglet ou de la modale dédiée.
- **Compatibilité rétroactive** : toutes les nouvelles propriétés d'évaluation (`importance_evidence_tier`, `dropped_requirements_count`, `risk_summary`, `company_history_note`, `bloc_h`) sont optionnelles côté TypeScript pour supporter les anciens documents MongoDB déjà évalués.

---

## 2. Modèles IA à jour & Guide utilisateur

### 2.1 Fallbacks modèles dans le panneau Lettres
- **Fichier** : `frontend/src/components/applications/CoverLetterPanel.tsx`
- Remplacer les valeurs de repli affichées lorsque `currentVersionData.models` n'est pas renseigné :
  - `writer` fallback : `"gpt-4o-mini"` → `"openai/gpt-5.6-terra"`
  - `critic` fallback : `"mistral-small-2501"` → `"gemini/gemini-3.8-flash"`

### 2.2 Mise à jour de la FAQ / Guide (`/guide`)
- **Fichier** : `frontend/src/app/guide/page.tsx`
- Mettre à jour l'item `airflow-sources` pour mentionner les connecteurs directs ATS Zero-Token (Ashby, Workday CXS, Greenhouse, Lever, SmartRecruiters durci) et le filtrage des pages non exploitables (murs de connexion, 404 shells, paywalls).
- Ajouter une FAQ dans la catégorie `matching` (ou `generation`) expliquant :
  1. Le **Bloc H** (réponses brouillons de formulaire générées automatiquement pour les offres `>= 4.0`).
  2. Le **Score ATS (0–100, grade A–D)** et l'export texte/Markdown nettoyé de tout caractère Unicode invisible.
  3. Les vues **Calibration IA** (`/applications`) et **Lacunes compétences JD** (`/offers`).

---

## 3. Évaluation Two-Pass Enrichie (Blocs B, G & H)

### 3.1 Contrats TypeScript (`frontend/src/types/jobOffer.ts`)
Alignés exactement sur `backend/app/models.py` :
- `ImportanceEvidenceTier = "stated" | "structural" | "inferred"`
- `RequirementMatch` et `MissingRequirement` : ajout de `importance_evidence_tier?: ImportanceEvidenceTier`
- `BlocB` : ajout de `dropped_requirements_count?: number`
- `RiskSummaryItem` : `{ signal: string; status: string }`
- `BlocG` : ajout de :
  - `employment_classification_risk?: string | null`
  - `pay_range_width_warning?: string | null`
  - `ai_buzzword_mismatch?: string | null`
  - `company_history_note?: string | null`
  - `risk_summary?: RiskSummaryItem[]`
- `DraftApplicationAnswer` : `{ question: string; answer: string }`
- `BlocH` : `{ eligible: boolean; answers: DraftApplicationAnswer[]; key_achievements: string[]; gaps_flagged: string[]; jd_keywords: string[] }`
- `OfferEvaluation` : ajout de `bloc_h?: BlocH | null`

### 3.2 Composants UI partagés
Pour éviter la duplication entre la page d'offre et le panneau Kanban :
- **Nouveau composant** : `frontend/src/components/offers/OfferEvaluationExtras.tsx` (≤ 250 lignes) exportant :
  1. `EvidenceTierBadge` : badge discret pour `importance_evidence_tier` (`stated` = `"Explicite"`, `structural` = `"Structurelle"`, `inferred` = `"Déduite"`).
  2. `BlocGRiskSummary` : affiche `company_history_note` (encart historique entreprise si présent) et la table/liste `risk_summary` (`signal` + `status`).
  3. `BlocHDraftPanel` : affiché uniquement lorsque `bloc_h?.eligible` est `true` et qu'au moins une donnée est présente :
     - Réponses pré-rédigées (`bloc_h.answers`) avec bouton **Copier** individuel et feedback visuel temporaire (`"Copié"`).
     - Réalisations clés à valoriser (`key_achievements`), écarts à anticiper (`gaps_flagged`) et mots-clés JD (`jd_keywords`).
- **Intégration dans `frontend/src/app/offers/[id]/page.tsx`** :
  - Bloc B : affichage de `EvidenceTierBadge` sur chaque critère matché/manquant et bandeau discret quand `(evaluation.bloc_b.dropped_requirements_count ?? 0) > 0`.
  - Onglet Analyse (`analysis`) : rendu de `BlocGRiskSummary` dans la section viabilité et de `BlocHDraftPanel` juste en dessous.
- **Intégration dans `frontend/src/components/applications/ApplicationDetails.tsx`** :
  - Rappel de `evaluation.bloc_g?.company_history_note` dans le bandeau Bloc G.
  - Indicateur / accordéon compact `BlocHDraftPanel` si `evaluation.bloc_h?.eligible` est actif.

---

## 4. CV Adaptés (`/resumes`) — Score ATS & Export Texte/Markdown

### 4.1 Types & Client API
- **Fichier** : `frontend/src/types/resume.ts`
  - `AtsScoreBreakdown` : `{ text: number; sections: number; contact: number; layout: number; metrics_and_bullets: number; charset_and_markers: number }`
  - `AtsKeywordCoverage` : `{ matched: string[]; missing: string[]; coverage_pct: number }`
  - `ResumeAtsScoreResponse` : `{ resume_id: string; score: number; grade: "A" | "B" | "C" | "D"; breakdown: AtsScoreBreakdown; issues: string[]; invisible_markers: Record<string, number>; keyword_coverage: AtsKeywordCoverage | null }`
  - `ResumeExportTextResponse` : `{ resume_id: string; format: "markdown" | "txt"; filename: string; content: string }`
- **Fichier** : `frontend/src/lib/api.ts` (`resumeApi`)
  - `getAtsScore(id: string, offerId?: string): Promise<ResumeAtsScoreResponse>` → `GET /resumes/${id}/ats-score`
  - `exportText(id: string, format: "markdown" | "txt"): Promise<ResumeExportTextResponse>` → `GET /resumes/${id}/export-text?format=${format}`

### 4.2 Interface utilisateur
- **Nouveau composant** : `frontend/src/components/resumes/ResumeAtsTab.tsx` (≤ 260 lignes)
  - Chargement automatique de `getAtsScore` et `exportText("markdown")` à l'ouverture de l'onglet (avec bouton de rafraîchissement).
  - **Carte Score ATS** : badge note `score / 100` + grade (`A`, `B`, `C`, `D`), barres de progression pour chacun des 6 axes (`breakdown`), section couverture mots-clés de l'offre (`matched` en vert, `missing` en ambre), alerte s'il reste des marqueurs invisibles, et liste des recommandations (`issues`).
  - **Bloc Export ATS** : sélecteur de format (`Markdown` / `Texte brut`), aperçu monospace scrollable, bouton **Copier dans le presse-papiers** et bouton **Télécharger** (Blob `.md` ou `.txt` avec `filename` retourné par l'API).
- **Intégration dans `frontend/src/components/resumes/ResumePreviewModal.tsx`** :
  - Ajouter l'onglet `"ats"` (`Score ATS & Export`) dans la barre d'onglets existante aux côtés de l'aperçu PDF/HTML et de l'édition.
  - Déclencher un rafraîchissement des données ATS si le contenu du CV vient d'être sauvegardé.

---

## 5. Modales Analytics à la Demande (`/applications` & `/offers`)

### 5.1 Types & Client API (`frontend/src/lib/api.ts`)
- `ScoreCalibrationBucket` : `{ label: string; total_count: number; in_flight_count: number; resolved_count: number; interview_count: number; offer_count: number; sample_floor_met: boolean; interview_rate: number | null; offer_rate: number | null }`
- `ScoreCalibrationResponse` : `{ min_band_n: number; total_applications: number; matched_evaluations: number; unscored_count: number; total_resolved: number; total_in_flight: number; bands: Record<string, ScoreCalibrationBucket>; by_archetype: Record<string, ScoreCalibrationBucket>; warnings: string[] }`
- `SkillGapItem` : `{ skill: string; count: number; critical_or_high_count: number; archetypes: string[]; classification: "supported_by_resume" | "gap" }`
- `JdSkillGapsResponse` : `{ total_evaluations_analyzed: number; min_score: number; items: SkillGapItem[] }`
- `applicationApi.calibrateScores(minBandN = 5): Promise<ScoreCalibrationResponse>` → `GET /applications/pipeline/calibrate?min_band_n=${minBandN}`
- `jobOffersApi.getSkillGaps(minScore = 0): Promise<JdSkillGapsResponse>` → `GET /job-offers/analytics/skill-gaps?min_score=${minScore}`

### 5.2 Modale Calibration IA (`/applications`)
- **Nouveau composant** : `frontend/src/components/applications/CalibrationModal.tsx` (≤ 250 lignes)
  - Déclenchée par un bouton **"Calibration IA"** dans le header de `frontend/src/app/applications/page.tsx`.
  - Accessible (fermeture `Escape` / clic backdrop / bouton fermer, `role="dialog"`, `aria-modal="true"`).
  - Contenu :
    - KPIs de tête : candidatures évaluées, dossiers résolus (`total_resolved`), dossiers en cours exclus du dénominateur (`total_in_flight`), sélecteur `min_band_n` (`3`, `5`, `10`).
    - Alertes éventuelles (`warnings`, ex: calibration inversée ou échantillon insuffisant).
    - Tableau par tranche de score (`<3.5`, `3.5-3.9`, `4.0-4.4`, `>=4.5`) affichant dossiers résolus, en cours, taux d'entretien (`interview_rate` ou badge `"Échantillon < N"` si `!sample_floor_met`) et taux d'offre.
    - Tableau secondaire par archétype (`by_archetype`).

### 5.3 Modale Lacunes Compétences JD (`/offers`)
- **Nouveau composant** : `frontend/src/components/offers/SkillGapsModal.tsx` (≤ 230 lignes)
  - Déclenchée par un bouton **"Lacunes JD"** dans le header de `frontend/src/app/offers/page.tsx`.
  - Accessible (`role="dialog"`, `aria-modal="true"`, fermeture `Escape`).
  - Contenu :
    - Filtre `min_score` (`0` = Toutes, `3.5`, `4.0`) + compteur d'évaluations analysées.
    - Liste/tableau trié des compétences manquantes récurrentes avec badges :
      - Classification : `"Lacune réelle"` (rouge/ambre) vs `"Déjà dans le CV"` (`supported_by_resume`, bleu/émeraude, à mieux mettre en valeur).
      - Occurrences critiques/hautes vs totales (`critical_or_high_count` / `count`) et puces d'archétypes concernés.

---

## 6. Vérification & Déploiement

- Vérifier compilation TypeScript et build de production Next.js :
  - `cd frontend && npm run lint && npm run build`
- Tests unitaires ciblés si un runner frontend est configuré ou ajout de tests de type-check / utilitaires si pertinent.
- Déploiement optionnel (sur confirmation utilisateur) : commit + push sur `origin/main` + rebuild/redémarrage de `frontend` sur `sentinel-vps` (`docker compose -f docker-compose.prod.yml up -d --build frontend`).
