# Bake-off CRAWL_LLM_MODEL — résumé

URLs testées : 8 (offres réelles tirées de la collection `job_offers` en base, 2026-09-16 : Indeed, Welcome to the Jungle, APEC, HelloWork, France Travail x2, LinkedIn x2).

## Bug découvert en cours de route

Le premier run donnait `gpt-5-nano` et `gpt-5.6-luna` à 0% succès / 0 token consommé — pas un signal de qualité, un crash silencieux. `_build_crawl_config` (comme `get_shared_crawl_config` en prod, `job_crawler/crawler1.py:111-118`) passe `max_tokens` + `reasoning_effort="minimal"` pour tout modèle `gpt-5*`. Vérifié en isolant l'appel litellm :

- `reasoning_effort` : `litellm.UnsupportedParamsError` (absent de `get_supported_openai_params("gpt-5-nano")` dans cette version de litellm).
- `max_tokens` : rejeté par l'API OpenAI elle-même (`Use 'max_completion_tokens' instead`).

`LLMExtractionStrategy.extract` avale l'exception (`except Exception` silencieux si `verbose=False`) et renvoie des blocs à champs `null` — exactement la signature que le commentaire de `crawler1.py` attribuait à tort à une "régression qualité" de gpt-5-nano. C'était un bug de paramètres, jamais un vrai appel au modèle.

Correctif appliqué **dans le script de bake-off uniquement** (`scripts/crawl_bakeoff.py`, pas en prod) : `max_completion_tokens=6000` + `drop_params=True`, sans `reasoning_effort` (de toute façon non honoré).

### Deuxième bug : Gemini crashait silencieusement dans crawl4ai (pas un problème de qualité)

Le premier run donnait aussi `gemini-3.8-flash` à 0/8 et `gemini-3.1-pro-preview` à 2/8, avec 75%/50% de "rejets ancrage" — ça ressemblait à une vraie faiblesse Gemini sur cette tâche. Vérifié en isolant l'appel litellm avec le prompt exact et une page réelle (HelloWork, où gpt-4o-mini réussit) : **ce n'est pas un problème de qualité, c'est un deuxième bug de crawl4ai.**

`PROMPT_EXTRACT_SCHEMA_WITH_INSTRUCTION` (le prompt d'extraction de crawl4ai) demande à l'LLM d'envelopper sa réponse JSON dans une balise `<blocks>...</blocks>`. GPT-4o-mini/gpt-5 la respectent. **Gemini ne la respecte jamais** — il répond en bloc ```json``` nu, sans balise `<blocks>`. Chaîne de pannes :

1. `extract_xml_data(["blocks"], réponse)` ne trouve rien → chaîne vide.
2. `json.loads('')` lève `Expecting value: line 1 column 1`.
3. Le bloc `except` de crawl4ai retente `response.choices[0].message.content` — mais `response` a déjà été réécrasé par une string plus haut dans le même `try` → crash `'str' object has no attribute 'choices'`, un vrai bug de la librairie, indépendant du modèle.
4. `extract()` avale cette exception silencieusement (`verbose=False`) et renvoie un bloc d'erreur, transformé en aval en offre `poste: null, entreprise: null` → rejetée par le contrôle d'ancrage.

Reproduction directe confirmée : le contenu brut renvoyé par Gemini pour l'offre HelloWork était en fait correct et bien structuré (bon poste, bonne entreprise, description propre) — juste illisible pour crawl4ai à cause du format de balise.

Correctif appliqué **dans le script de bake-off uniquement** : `RobustLLMExtractionStrategy` (sous-classe de `LLMExtractionStrategy` dans `crawl_bakeoff.py`) — repli sur extraction du JSON depuis le fence ```json``` quand `<blocks>` est absent, sans réutiliser `response` après réassignation. Les deux modèles Gemini ont été rejoués sur les 8 mêmes URLs avec ce correctif.

## Résultats lot 1 (8 URLs initiales, tous les bugs de parsing corrigés dans le script)

| Modèle | Succès | Rejets ancrage | Autres échecs | Tokens | Coût USD | Durée (s) |
|---|---|---|---|---|---|---|
| openai/gpt-4o-mini | 4/8 (50%) | 2 | 2 | 30208 | 0.0072 | 59.2 |
| openai/gpt-5-nano | 4/8 (50%) | 2 | 2 | 64610 | 0.0681 | 283.6 |
| openai/gpt-5.6-luna | 5/8 (62%) | 1 | 2 | 39595 | 0.1215 | 93.2 |
| gemini/gemini-3.8-flash | 5/8 (62%) | 1 | 2 | 43139 | 0.0697 | 56.5 |
| gemini/gemini-3.7-flash | 5/8 (62%) | 1 | 2 | 40677 | 0.0611 | 48.5 |
| gemini/gemini-3.6-flash | 5/8 (62%) | 1 | 2 | 46239 | 0.0822 | 84.2 |
| gemini/gemini-3.5-flash-lite | 4/8 (50%) | 1 | 3 | 31205 | 0.0226 | 47.9 |
| gemini/gemini-3.1-pro-preview | 3/8 (38%) | 2 | 3 | 48767 | 0.2810 | 144.3 |

Détail des succès par URL (tous les candidats partagent les mêmes échecs structurels sur Indeed — timeout anti-bot, intermittent aussi sur LinkedIn — et WTTJ — extraction vide sur tous les modèles, donc pas un signal LLM) :

- **gpt-4o-mini** et **gpt-5-nano** réussissent sur exactement le même sous-ensemble (LinkedIn Scaleway, HelloWork, France Travail x2).
- **gpt-5.6-luna, gemini-3.8-flash, gemini-3.7-flash, gemini-3.6-flash** réussissent en plus sur LinkedIn Néosoft, et échouent tous sur APEC (ancrage) — 5/8 strictement identique entre les trois générations Gemini flash testées.
- **gemini-3.5-flash-lite** retombe à 4/8 (50%, comme gpt-4o-mini) mais coûte ~3x plus cher que gpt-4o-mini pour le même score.
- **gemini-3.1-pro-preview** échoue sur LinkedIn Scaleway (extraction vide) et France Travail 209VCCG (ancrage), deux URLs où les flash Gemini réussissent.

Note méthodo : `gemini-3.5-flash-lite` a d'abord été testé juste après 3 autres candidats dans la même session crawl4ai/Playwright et a produit 5/8 `empty_crawl` avec `BrowserContext has been closed` — panne d'infra, pas un signal LLM. Rejoué seul et à froid : 4/8, chiffre retenu ci-dessus.

## Résultats lot 2 (8 URLs fraîches, aucun recoupement avec le lot 1)

Demandé explicitement pour vérifier si le classement du lot 1 tenait sur un échantillon différent — 2 LinkedIn, 2 HelloWork, 2 Welcome to the Jungle, 1 France Travail, 1 Free-Work (offre agrégateur multi-postes).

| Modèle | Succès | Rejets ancrage | Autres échecs | Coût USD | Durée (s) |
|---|---|---|---|---|---|
| openai/gpt-4o-mini | **8/8 (100%)** | 0 | 0 | 0.0098 | 48.1 |
| gemini/gemini-3.5-flash-lite | 7/8 (88%) | 0 | 1 | 0.0361 | 35.3 |
| openai/gpt-5.6-luna | 6/8 (75%) | 0 | 2 | 0.1469 | 84.8 |
| gemini/gemini-3.8-flash | 6/8 (75%) | 0 | 2 | 0.0913 | 71.1 |
| gemini/gemini-3.7-flash | 6/8 (75%) | 0 | 2 | 0.0817 | 46.7 |
| gemini/gemini-3.6-flash | 5/8 (62%) | 1 | 2 | 0.1145 | 114.8 |
| gemini/gemini-3.1-pro-preview | 4/8 (50%) | 2 | 2 | 0.3662 | 151.8 |
| openai/gpt-5-nano | 3/8 (38%) | 3 | 2 | 0.0880 | 292.3 |

**Le classement s'inverse presque complètement.** `gpt-4o-mini` passe de 50% à 100% ; `gpt-5-nano` chute de 50% à 38% ; `gemini-3.5-flash-lite` bondit de 50% à 88%. Ça confirme ce qui était déjà signalé comme réserve sur le lot 1 : n=8 est trop petit, le classement dépend fortement des URLs tirées, pas seulement du modèle.

## Résultats combinés (16 URLs, les deux lots)

| Modèle | Succès combiné | Coût combiné (16 URLs) |
|---|---|---|
| **openai/gpt-4o-mini** | **12/16 (75%)** | **$0.0170** |
| openai/gpt-5.6-luna | 11/16 (69%) | $0.2684 |
| gemini/gemini-3.8-flash | 11/16 (69%) | $0.1610 |
| gemini/gemini-3.7-flash | 11/16 (69%) | $0.1428 |
| gemini/gemini-3.5-flash-lite | 11/16 (69%) | $0.0587 |
| gemini/gemini-3.6-flash | 10/16 (62%) | $0.1967 |
| gpt-5-nano | 7/16 (44%) | $0.1561 |
| gemini/gemini-3.1-pro-preview | 7/16 (44%) | $0.6472 |

Sur l'échantillon élargi, `gpt-4o-mini` reprend la première place en qualité **et** reste le moins cher de loin (17x moins cher que gpt-5.6-luna, 9x moins cher que gemini-3.8-flash). L'avantage de `gemini-3.7-flash`/`gpt-5.6-luna` observé sur le lot 1 seul ne se confirme pas — c'était du bruit d'échantillon (une poignée d'URLs faciles/difficiles réparties par hasard), pas un vrai écart de qualité entre modèles.

## Recommandation

**Garder `openai/gpt-4o-mini`.** Sur l'échantillon combiné (16 URLs réelles, deux lots indépendants), il est premier en qualité (75%) et de très loin le moins cher. Les deux bugs de parsing découverts en cours de route (gpt-5* et Gemini `<blocks>`) sont réels et valaient la peine d'être corrigés pour ne pas enterrer ces modèles sur un faux signal — mais une fois corrigés et testés sur un échantillon plus large, aucun candidat ne bat gpt-4o-mini ici.

- gpt-5-nano et gemini-3.1-pro-preview sont les deux pires candidats sur l'échantillon combiné (44%) pour un coût 9x à 38x supérieur — à écarter clairement.
- gpt-5.6-luna, gemini-3.8-flash, gemini-3.7-flash, gemini-3.5-flash-lite sont à égalité (69%) mais tous en dessous de gpt-4o-mini et tous plus chers (de 3,5x à 16x) — aucun d'eux ne justifie une migration.
- gemini-3.6-flash est le seul Gemini flash nettement en retrait (62%) — pas d'intérêt particulier.

Aucun changement appliqué à `docker-compose.yml` ni `crawler1.py` — décision manuelle, conforme à la philosophie du script.

## Reste à faire si vous voulez trancher différemment

1. Si vous voulez challenger `gpt-4o-mini` davantage, il faudrait un troisième lot (16-24 URLs) pour départager le groupe à 69% — sur 16 URLs l'écart avec gpt-4o-mini (75% vs 69%) reste faible.
2. Si un modèle Gemini est un jour retenu malgré ces résultats : porter `RobustLLMExtractionStrategy` (ou un correctif équivalent) dans `job_crawler/crawler1.py::get_shared_crawl_config`, sinon la prod reproduira le 0% succès du tout premier run bugué.
3. `crawler1.py:97-98` a un commentaire qui attribue à tort le null-fields de gpt-5-nano à une "régression qualité" — en réalité un bug de paramètres litellm (voir plus haut). Corriger le commentaire et `crawler1.py:111-118` (mêmes `extra_args` cassés) pour que le code reflète la réalité si `CRAWL_LLM_MODEL=openai/gpt-5-nano` est un jour activé.
4. `gemini-3.5-flash-lite` a montré des `BrowserContext has been closed` en série quand testé juste après 3 autres runs dans la même session (lot 1) — si des runs de bake-off futurs enchaînent beaucoup de candidats, envisager un redémarrage de `AsyncWebCrawler` entre chaque modèle pour éviter ce faux signal.

> Candidats évalués : openai/gpt-4o-mini, openai/gpt-5-nano, openai/gpt-5.6-luna, gemini/gemini-3.8-flash, gemini/gemini-3.7-flash, gemini/gemini-3.6-flash, gemini/gemini-3.5-flash-lite, gemini/gemini-3.1-pro-preview
> Rapports bruts : `crawl-bakeoff-report.json` (run initial, gpt-4o-mini/gemini valides, gpt-5* cassés) + `crawl-bakeoff-report-gpt5-fixed.json` (gpt-5* avec extra_args corrigés) + `crawl-bakeoff-report-gemini-3.1-pro.json` (run initial gemini-3.1-pro, encore buggé côté `<blocks>`) + `crawl-bakeoff-report-gemini-fixed.json` (3.8-flash et 3.1-pro-preview avec le parsing `<blocks>` corrigé) + `crawl-bakeoff-report-gemini-more-flash.json` (3.7-flash, 3.6-flash, 3.5-flash-lite — flash-lite buggé par panne d'infra) + `crawl-bakeoff-report-gemini-flash-lite-clean.json` (3.5-flash-lite rejoué seul, chiffres retenus) + `crawl-bakeoff-report-fresh-urls.json` (lot 2, les 8 candidats sur 8 URLs fraîches)
