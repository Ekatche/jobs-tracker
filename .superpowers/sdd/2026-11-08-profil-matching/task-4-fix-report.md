# Tâche 4 : tour de correction 1, rapport

BASE = 373def1. Doc seule : `backend/scripts/reference/README.md`.

- I1 : lignes « sous le plancher » renommées en « détachées (filtre dur ou sous le plancher) » (texte avant tableau l. ~180, lignes du tableau 194-195) ; paragraphe « Motifs de détachement » ajouté avant « Limites » (48 = 33 géo / 12 métier / 2 contrat / 1 mot exclu / 0 plancher ; candidatures 1 métier + 1 contrat ; interactions 6 métier + 1 contrat ; min 38,3 pour FLOOR 35 ; faux négatif écarté par la garde métier) ; « l'export ne l'exerce pas » remplacé (garde métier exercée sur 12 paires, mêmes verdicts ; chemins nouveaux non exercés, profil sans terme juridique, fait vérifié). Chiffres repris de la relecture, aucun recomptage.
- m1 : esquisse corrigée (`load_export`, `assessed[alias][offer_id]`), avertissement qu'un `json.load` simple rend 0 paire sans erreur.
- m2 : « (30, dont les 20 candidatures) ».
- m4 : nuance prod (`rematch_user` n'évalue pas les paires à vecteur périmé, le banc les score avec `cos=None`).
- m3 : mis de côté. `task-4-report.md` non modifié ; son libellé l. 20-21 (« sous le plancher ») est corrigé par ce tour dans le README seulement.
- Tests : `uv run pytest tests/test_offer_profile_matcher.py -q` : 23 passed.
