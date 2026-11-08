# CV adaptés et lettres de motivation — plan

**Statut :** proposé, à valider sur générations réelles.  
**Objectif :** relier les exigences centrales d'une offre aux preuves exactes du profil, sans invention, et ne jamais présenter comme prête une lettre qui viole encore un garde-fou.  
**Architecture :** corriger d'abord le statut de lettre, puis mesurer les sorties et améliorer la sélection des preuves et les garde-fous ; conserver les rendus et la correction par le candidat.  
**Technologies :** Python, Pydantic, modèles LLM configurés, FastAPI, React, pytest et PDF.

## Périmètre et contraintes

Examiner `backend/app/services/cv_tailor.py`, `cv_guards.py`, `letter_guards.py`, `backend/job_trackers/src/job_trackers/cover_letter_crew.py`, les prompts et les routes. Les changements de profil dépendent du [plan profil et matching](2026-11-08-profil-matching.md), qui fournit aussi le jeu commun et le registre de budget. Ne jamais assimiler une compétence transférable à une expérience directe, ni transférer une métrique ou technologie entre postes.

Le garde CV actuel ne contrôle pas les affirmations des puces ni les certifications générées, et le corpus de compétences est global plutôt que lié à un poste. Après épuisement des essais, `CVHonestyError` fait échouer toute la génération. Le rapport final de lettre peut rester bloquant alors que `_append_letter_version` attribue `ready` systématiquement. Le modèle limite les statuts à `pending`, `ready`, `failed` ; l'export PDF exige `ready`.

**Budget :** part de ce plan 2 $ sur le plafond commun de 2,50 $ (appels réels des scripts de mesure uniquement, ni tests ni production), consignée dans `backend/scripts/data/llm_budget.jsonl`. À environ 0,06 $ par lettre, procéder par paliers : pilote sur 10 couples avec la configuration actuelle (≈ 0,60 $) ; n'étendre à 30 couples ou comparer une seconde version de prompt que si le pilote montre un écart à mesurer. Réutiliser la sortie de l'analyste entre configurations, comme `letter_bakeoff.py` le fait déjà.

**Cibles proposées pour le pilote :** sur les couples annotés évalués (10 au pilote, 30 visés si le budget le permet), zéro affirmation critique inventée ou attribuée au mauvais poste dans les documents acceptés, au moins 90 % des exigences centrales couvertes lorsqu'une preuve existe, moins de 10 % de faux rejets, calculés comme affirmations annotées valides signalées par un garde-fou divisées par l'ensemble des affirmations annotées valides des documents générés ; zéro lettre bloquante marquée `ready` dans les tests. Rapporter les dénominateurs et résultats par métier.

**Ordre :** la tâche 0 ne dépend ni du jeu commun ni d'un appel réel et passe en premier. Les tâches 1 et 2 attendent le jeu commun ; les tests unitaires de la tâche 2 peuvent commencer avant.

## Tâche 0 — Statut de lettre (défaut confirmé)

- [ ] Écrire d'abord le test API rouge : rapport de garde encore bloquant après la seconde révision ; vérifier que le statut n'est pas `ready`, que texte, motifs (`guard_report`) et historique des versions restent accessibles.
- [ ] Ajouter `needs_review` au `Literal` de `CoverLetter.status` dans `backend/app/models.py` et le calcul de statut dans `_append_letter_version` (`backend/app/routers/applications.py`) : `needs_review` si `guard_report.is_blocking`, sinon `ready`.
- [ ] Relance de génération (`_generate_cover_letter_bg`) : une lettre `needs_review` n'est ni supprimée ni régénérée automatiquement ; seule une demande explicite de régénération la repasse à `pending`.
- [ ] Sortie de `needs_review` : après une réécriture de passage ou une modification manuelle, réévaluer `evaluate_letter_guards` (déterministe, sans appel LLM) et passer à `ready` si plus rien ne bloque ; sinon rester en `needs_review` avec le nouveau rapport.
- [ ] Export PDF (`backend/app/routers/cover_letters.py`, contrôle `status != "ready"`) : autoriser l'export d'une lettre `needs_review` après avertissement explicite côté interface, sans la marquer prête.
- [ ] Frontend : ajouter `needs_review` au type de `frontend/src/types/coverLetter.ts` ; dans `CoverLetterPanel.tsx`, arrêter le rafraîchissement automatique sur `needs_review` (il ne s'arrête aujourd'hui que sur `ready` ou `failed`) et afficher les motifs avec l'action de correction.
- [ ] Compatibilité : les lettres existantes `ready` restent `ready` ; pas de migration.
- [ ] Depuis `backend`, exécuter `uv run pytest tests/test_cover_letters_api.py tests/test_cover_letter_crew.py tests/test_cover_letter_status.py -v` et les tests frontend concernés.

## Tâche 1 — Jeu de référence et mesure

- [ ] Utiliser les profils et offres du jeu commun (`backend/scripts/reference/`, dont `letter_requirements.json`), avec notamment un profil séries temporelles sans expérience de capteurs industriels ; compléter les annotations d'exigences, preuves exactes, éléments transférables et lacunes.
- [ ] Étendre `backend/scripts/letter_bakeoff.py` pour comparer versions de prompts à modèle, paramètres et entrées constants ; ajouter si nécessaire un complément CV. Le script actuel appelle les modèles sans garde `--confirm` : ajouter un mode estimation par défaut, `--confirm` pour les appels réels et la vérification du registre de budget avant chaque appel. Mesurer fidélité, couverture, naturel, faux rejets, échecs complets `CVHonestyError`, part de lettres `needs_review`, coût et latence ; conserver les sorties privées sous `backend/scripts/data/`.
- [ ] Établir un résultat de référence ; séparer tests simulés et évaluation humaine des générations réelles.

## Tâche 2 — Sélection des preuves et CV

- [ ] Ajouter dans `backend/tests/test_cv_guards.py` et `test_cv_tailor.py` des cas de métrique attribuée au mauvais poste, technologie absente ou issue d'un autre poste, dates et certifications ; inclure une preuve transférable valide et un faux rejet à éviter.
- [ ] Créer des contrôles pour les puces, métriques, certifications et technologies par expérience dans `cv_guards.py` ; adapter la sélection dans `cv_tailor.py`. Préserver les preuves et distinguer les formulations non vérifiables des inventions confirmées.
- [ ] Depuis `backend`, exécuter `uv run pytest tests/test_cv_guards.py tests/test_cv_tailor.py -v` puis comparer les cas annotés avant/après.

## Tâche 3 — Qualité des lettres

- [ ] Tester dans `test_cover_letter_crew.py` et `test_letter_guards.py` le lien entre exigences et preuves, le transfert clairement formulé et l'attribution erronée. Adapter les prompts et la critique sans masquer les violations restantes ; une violation non résolue doit aboutir à `needs_review`, jamais à `ready`.
- [ ] Depuis `backend`, exécuter `uv run pytest tests/test_letter_guards.py tests/test_cover_letter_crew.py tests/test_cover_letters_api.py tests/test_cover_letter_status.py -v`.

## Tâche 4 — PDF et bilan

- [ ] Vérifier parcours courts et longs, pagination, accents, texte sélectionnable et correction avant export ; depuis `backend`, exécuter `uv run pytest tests/test_cv_pdf_renderer.py tests/test_cv_registry_parity.py tests/test_letter_pdf.py -v` et inspecter les PDF rendus.
- [ ] Comparer les générations réelles à modèle et entrées constants, documenter les jugements humains et coûts, puis décider si les garde-fous réduisent les inventions sans rejet excessif.
