# Import de CV

Route : `POST /profile/candidate/sources/cv` (`backend/app/routers/cover_letters.py`).

## Formats supportés

PDF uniquement. La route ne regarde ni le type MIME ni l'extension du fichier : elle lit les octets et exige la signature `%PDF` en tête (`_read_upload`). Un DOCX, une image ou tout autre contenu est refusé avec 400 `Le contenu du fichier n'est pas un PDF valide`, même renommé en `.pdf`. Un PDF d'au plus 10 Mo est accepté, au-delà la réponse est 413 `Fichier trop volumineux (10 Mo maximum)`.

## Méthode par page

- Les 3 premières pages (`VLM_MAX_PAGES`) passent par le modèle de vision.
- Les pages suivantes sont complétées par le LLM texte, à partir de la couche texte du PDF.
- Si le visuel est indisponible, échoue ou ne renvoie rien, tout le PDF passe par le LLM texte.
- Pas d'OCR en production.

La réponse porte `import_report` : pages traitées par méthode, pages non couvertes, repli utilisé, erreurs partielles et page de provenance des expériences et formations. Il n'est jamais enregistré dans le profil.

## Erreurs

| Cas | Code | Message |
|---|---|---|
| PDF protégé | 400 | `Ce PDF est protégé par un mot de passe : exportez une version non protégée puis réessayez` |
| PDF illisible | 400 | `Ce PDF est illisible ou endommagé : exportez-le de nouveau puis réessayez` |
| PDF vide | 400 | `Aucun contenu exploitable n'a été trouvé dans ce PDF : vérifiez qu'il contient du texte ou une image lisible` |
| Analyse visuelle indisponible, sans texte exploitable | 503 | `L'analyse visuelle de ce PDF est momentanément indisponible. Réessayez dans quelques minutes.` |
| Erreur fournisseur identifiée (crédits 402, quota 429, clé 502, surcharge 503) | selon le cas | message du fournisseur (`app/llm/provider_errors.py`) |
| Autre échec du fournisseur | 502 | `Le CV n'a pas pu être analysé` |
| Échec partiel (ex. complément texte des pages au-delà de la page 3) | 200 | entrée dans `import_report.errors` ; le résultat du visuel est conservé |

Un import en échec n'enregistre aucun coût ni source.

## Mesures

Banc : `backend/scripts/cv_reference_bench.py --method vlm|text|ocr`, sur 29 PDF synthétiques (57 pages, 10 catégories). Les colonnes « simulé » viennent d'un oracle parfait par construction : elles mesurent la couverture du pipeline (pages, repli, complément), pas la qualité d'un modèle. Elles ne sont pas des mesures réelles. L'OCR simulé reconstruit le texte de chaque page depuis la vérité du cas.

Les colonnes réelles se remplissent avec `--real --confirm` (registre `llm_budget`, part `parser` de 0,25 $). Estimations avant appel : vlm 0,0347 $ (29 cas), text 0,0334 $ (29 cas), ocr 0,0502 $ (10 cas).

Périmètre de l'OCR par défaut : catégories `scanned`, `mixed_scanned` et `two_columns` (10 cas, 19 pages). Ailleurs la couche texte est propre et l'OCR coûterait sans rien apporter.

Colonne simulé : « simulé : couverture du pipeline, pas qualité du modèle ».

### vlm (29 cas)

| Mesure | simulé : couverture du pipeline, pas qualité du modèle | réel |
|---|---|---|
| Rappel des expériences | 97 % | à mesurer (contrôleur, `--real --confirm`) |
| Faits inventés | 0 | à mesurer (contrôleur, `--real --confirm`) |
| Pages couvertes | 94 % | à mesurer (contrôleur, `--real --confirm`) |
| Faux rejets | 0 | à mesurer (contrôleur, `--real --confirm`) |
| Durée moyenne par CV | 0,07 s | à mesurer (contrôleur, `--real --confirm`) |
| Coût moyen par CV | 0,0008 $ (estimé) | à mesurer (contrôleur, `--real --confirm`) |

Catégorie `long`, pages 4 et suivantes : 6 faits critiques sur 6 retrouvés par le complément texte, 0 perdu (simulé).

### text (29 cas)

| Mesure | simulé : couverture du pipeline, pas qualité du modèle | réel |
|---|---|---|
| Rappel des expériences | 85 % (les 3 scans n'ont pas de couche texte) | à mesurer (contrôleur, `--real --confirm`) |
| Faits inventés | 0 | à mesurer (contrôleur, `--real --confirm`) |
| Pages couvertes | 95 % | à mesurer (contrôleur, `--real --confirm`) |
| Faux rejets | 3 (les scans) | à mesurer (contrôleur, `--real --confirm`) |
| Durée moyenne par CV | 0,01 s | à mesurer (contrôleur, `--real --confirm`) |
| Coût moyen par CV | 0,0003 $ (estimé) | à mesurer (contrôleur, `--real --confirm`) |

### ocr (10 cas)

| Mesure | simulé : couverture du pipeline, pas qualité du modèle | réel |
|---|---|---|
| Rappel des expériences | 100 % | à mesurer (contrôleur, `--real --confirm`) |
| Faits inventés | 0 | à mesurer (contrôleur, `--real --confirm`) |
| Pages couvertes | 98 % | à mesurer (contrôleur, `--real --confirm`) |
| Faux rejets | 0 | à mesurer (contrôleur, `--real --confirm`) |
| Durée moyenne par CV | 0,003 s | à mesurer (contrôleur, `--real --confirm`) |
| Coût moyen par CV | 0,0042 $ (estimé, OCR compris) | à mesurer (contrôleur, `--real --confirm`) |

Le jeu simulé de l'OCR ne couvre que 10 cas : ses moyennes ne se comparent pas telles quelles à celles des deux autres méthodes.

## Hors périmètre

- DOCX et images : à étudier dans un plan ultérieur.
- OCR en production : seulement après choix documenté et validation des dépendances. Le banc l'appelle par `httpx` (`backend/scripts/cv_ocr.py`), sans dépendance nouvelle.
- Limite de pages du visuel (`VLM_MAX_PAGES = 3`) : inchangée, à réévaluer sur les mesures réelles.

## Modèles et prix

Relevé du 2026-11-08.

| Usage | Modèle | Prix | Source |
|---|---|---|---|
| Visuel (défaut) | `mistral/ministral-14b-2512` | 0,20 $ / M tokens en entrée et en sortie | docs.mistral.ai/models/ministral-3-14b-25-12 |
| Texte (défaut) | `openai/gpt-4o-mini` | 0,15 $ en entrée, 0,60 $ en sortie, par M tokens | tarif OpenAI |
| OCR (banc seulement) | `mistral-ocr-2512` (OCR 3) | 2 $ / 1 000 pages, endpoint `/v1/ocr` | docs.mistral.ai/models/ocr-3-25-12 |
| OCR, version suivante | `mistral-ocr-4-1` (alias `mistral-ocr-latest`) | 4 $ / 1 000 pages | docs.mistral.ai/models/ocr-4-1 |
