# Import de CV

Route : `POST /profile/candidate/sources/cv` (`backend/app/routers/cover_letters.py`).

## Formats supportés

PDF uniquement. La route ne regarde ni le type MIME ni l'extension du fichier : elle lit les octets et exige la signature `%PDF` en tête (`_read_upload`). Un DOCX, une image ou tout autre contenu est refusé avec 400 `Le contenu du fichier n'est pas un PDF valide`, même renommé en `.pdf`. La taille est contrôlée avant la signature : un fichier de plus de 10 Mo reçoit 413 `Fichier trop volumineux (10 Mo maximum)`, quel que soit son format.

## Méthode par page

- Les 3 premières pages (`VLM_MAX_PAGES`) passent par le modèle de vision.
- Les pages suivantes sont complétées par le LLM texte, à partir de la couche texte du PDF.
- Si le visuel est indisponible, échoue ou ne renvoie rien, tout le PDF passe par le LLM texte.
- Garde PDF vierge : si les 3 premières pages (celles envoyées au modèle de vision), rendues à basse résolution, sont toutes unicolores, aucun appel au modèle de vision n'est fait ; la couche texte des pages suivantes passe par le LLM texte s'il y en a une, sinon 400 PDF vide.
- Une page scannée au-delà de la page 3 n'est pas couverte : elle n'a pas de couche texte et il n'y a pas d'OCR en production.
- Pas d'OCR en production.

Seules les clés du schéma de profil sont conservées de la sortie du modèle (liste blanche) ; toute autre clé est ignorée.

La réponse porte `import_report` : pages traitées par méthode, pages non couvertes, repli utilisé, erreurs partielles et page de provenance des expériences et formations. Il n'est jamais enregistré dans le profil.

## Erreurs

| Cas | Code | Message |
|---|---|---|
| PDF protégé | 400 | `Ce PDF est protégé par un mot de passe : exportez une version non protégée puis réessayez` |
| PDF illisible | 400 | `Ce PDF est illisible ou endommagé : exportez-le de nouveau puis réessayez` |
| PDF vide | 400 | `Aucun contenu exploitable n'a été trouvé dans ce PDF : vérifiez qu'il contient du texte ou une image lisible` |
| Analyse visuelle indisponible, sans texte exploitable | 503 | `L'analyse visuelle de ce PDF est momentanément indisponible. Réessayez dans quelques minutes.` |
| Erreur fournisseur identifiée (crédits 402, quota 429, clé 502, surcharge 503) | selon le cas | message du fournisseur (`app/llm/provider_errors.py`) |
| Profil dérivé invalide | 502 | `Le profil obtenu n'a pas pu être validé` |
| Autre échec du fournisseur | 502 | `Le CV n'a pas pu être analysé` |
| Échec partiel (ex. complément texte des pages au-delà de la page 3) | 200 | entrée dans `import_report.errors` ; le résultat du visuel est conservé |

Un import en échec n'enregistre ni coût ni source, sauf un profil dérivé invalide (502) : l'usage est alors déjà enregistré.

## Mesures

Banc : `backend/scripts/cv_reference_bench.py --method vlm|text|ocr`, sur 29 PDF synthétiques (57 pages, 10 catégories). Les colonnes « simulé » viennent d'un oracle parfait par construction : elles mesurent la couverture du pipeline (pages, repli, complément), pas la qualité d'un modèle. Elles ne sont pas des mesures réelles. L'OCR simulé reconstruit le texte de chaque page depuis la vérité du cas (une page sans élément de vérité reste vide dans le stub).

Les colonnes réelles se remplissent avec `--real --confirm` (registre `llm_budget`, part `parser` de 0,25 $). Estimations avant appel : vlm 0,0347 $ (29 cas), text 0,0334 $ (29 cas), ocr 0,0502 $ (10 cas). Mesures réelles du 8 au 9 novembre 2026 : vlm 0,0322 $, text 0,0129 $, ocr 0,0437 $, plus 0,0037 $ pour la vérification ciblée après correctif. Ces mesures portent sur un jeu synthétique, une seule passe par cas, et ne valent pas pour des CV réels.

Périmètre de l'OCR par défaut : catégories `scanned`, `mixed_scanned` et `two_columns` (10 cas, 19 pages). Ailleurs la couche texte est propre et l'OCR coûterait sans rien apporter.

Colonne simulé : « simulé : couverture du pipeline, pas qualité du modèle ».

### vlm (29 cas)

| Mesure | simulé : couverture du pipeline, pas qualité du modèle | réel |
|---|---|---|
| Rappel des expériences | 97 % | 97,3 % |
| Faits inventés | 0 | 5 avant correctif, 0 sur la vérification ciblée (4 cas) (voir ci-dessous) |
| Pages couvertes | 98 % | 98,1 % |
| Faux rejets | 0 | 0 |
| Durée moyenne par CV | 0,08 s | 7,2 s |
| Coût moyen par CV | 0,0008 $ (jetons de l'oracle simulé) | 0,0011 $ |

Catégorie `long`, pages 4 et suivantes : 6 faits critiques sur 6 retrouvés par le complément texte, 0 perdu (simulé).

Les 5 faits inventés de la mesure complète venaient de 2 cas. Sur le PDF vierge, le VLM inventait 3 entreprises. Sur un CV français, il traduisait 2 intitulés en anglais. Depuis le correctif (`fix(cv-parser): skip the VLM on blank PDFs…`), un PDF dont toutes les pages rendues sont unicolores n'est plus envoyé au VLM, et le prompt demande de recopier les libellés sans les traduire. Vérification réelle ciblée après correctif, sur ces 2 cas et sur les 2 scans : 0 fait inventé, rappel inchangé, PDF vierge rejeté comme vide sans coût.

### text (29 cas)

| Mesure | simulé : couverture du pipeline, pas qualité du modèle | réel |
|---|---|---|
| Rappel des expériences | 85 % (les 3 scans n'ont pas de couche texte) | 84,9 % |
| Faits inventés | 0 | 0 |
| Pages couvertes | 84 % | 83,7 % |
| Faux rejets | 3 (les scans) | 3 (les scans, en « analyse visuelle indisponible ») |
| Durée moyenne par CV | 0,01 s | 8,2 s |
| Coût moyen par CV | 0,0003 $ (jetons de l'oracle simulé) | 0,00045 $ |

Avant le correctif, le PDF vierge levait lui aussi « analyse visuelle indisponible » au lieu d'être rejeté comme vide. Vérification réelle après correctif : rejeté comme vide, sans coût.

### ocr (10 cas)

| Mesure | simulé : couverture du pipeline, pas qualité du modèle | réel |
|---|---|---|
| Rappel des expériences | 100 % | 100 % |
| Faits inventés | 0 | 0 |
| Pages couvertes | 97,5 % | 100 % |
| Faux rejets | 0 | 0 |
| Durée moyenne par CV | 0,005 s | 10,9 s |
| Coût moyen par CV | 0,0042 $ (jetons de l'oracle simulé, OCR compris) | 0,0044 $ (OCR compris) |

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
