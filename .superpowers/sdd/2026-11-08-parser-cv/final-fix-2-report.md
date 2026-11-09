# final-fix-2 : rapport

BASE = d49d5c9.

## Traitement
- R1 : `backend/app/services/cv_parser.py:196-217` `pdf_pages_all_blank(pdf_path, max_pages=VLM_MAX_PAGES, dpi=15)` : boucle bornée à `max_pages`, retour faux au premier rendu non vierge ; appelant l. ~686 inchangé (défauts).
- `docs/cv-import.md:14` : garde sur les 3 premières pages, basse résolution.
- m-A : `backend/scripts/cv_reference_bench.py:147-151` `rfind("<cv_text>")` ; `backend/tests/cv_reference/test_bench.py` (test_methods_run_offline_on_a_scanned_case) : assertion sur le vrai prompt de `parse_cv_with_llm` (acompletion patché), 2 occurrences de la balise, texte extrait == texte fourni.
- Limite connue acceptée : pages 1-3 blanches + page 4+ scannée => traité comme vierge (400 EMPTY).

## Verdicts blancs, 29 cas synthétiques (max_pages=3)
Script : scratchpad/blank_check.py. 15 / 30 / 50 / 150 dpi : verdicts identiques sur les 29 cas (0 différence). Seul `em_blank` est vrai ; `un_corrupt` (illisible) faux ; `pr_p02` (protégé) faux.
Durée totale (29 PDF) : 15 dpi 0,17 s ; 30 dpi 0,24 s ; 50 dpi 0,51 s ; 150 dpi 3,92 s. 15 dpi conservé.

## Mutation m-A
`find` au lieu de `rfind` : le test échoue (texte extrait commence par la consigne). Annulé.

## Chiffres
Collectés avant/après : 1649 / 1649 (comptage via `pytest.main` : `rtk pytest --collect-only` affiche « No tests collected »).
Ciblés : 71 passed. Suite complète : 1649 passed. Aucun test instable relancé.
Ruff : seul E741 préexistant (cv_parser.py:278, ligne décalée par l'édition).
