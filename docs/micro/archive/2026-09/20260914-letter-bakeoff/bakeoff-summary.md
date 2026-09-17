# Bake-off — résumé

## Candidats
- openai/gpt-5.6-sol
- mistral/mistral-large-2407
- openai/gpt-5.6-terra

## Résultats par offre

### Offre 1 — Volvo Group

| Candidat | Violations garde-fous | Bloquant | Verdict critique | Score | Tokens | Coût USD | Durée (s) |
|---|---|---|---|---|---|---|---|
| Lettre-1 | 9 | Oui | approve | 8/10 | 3144 | 0.044064 | 25.82 |
| Lettre-2 | 7 | Oui | revise | 6/10 | 1700 | 0.00532 | 10.18 |
| Lettre-3 | 5 | Oui | approve | 8/10 | 3575 | 0.105368 | 46.18 |

## Prochaines étapes

1. Lire `bakeoff-report.json` — classer les lettres **sans** regarder `bakeoff-keys.json`.
2. Ouvrir `bakeoff-keys.json` pour lever l'anonymat.
3. Croiser classement, violations et coûts.
4. Mettre à jour `DEFAULT_MODELS["writer"]` dans `letter_llm.py` avec le modèle retenu.
5. Mettre à jour `validate_cross_provider` si le critique doit changer en conséquence.
6. Committer : `git commit -m "feat: bake-off du rédacteur et choix de modèle mesuré"`

> Prompt version utilisée : `02_style-v1`
> Candidats évalués : openai/gpt-5.6-sol, mistral/mistral-large-2407, openai/gpt-5.6-terra