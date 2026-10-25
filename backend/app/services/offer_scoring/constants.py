"""Constantes du score de pertinence hybride (sémantique + règles déterministes).

Toute valeur numérique du score vit ici et nulle part ailleurs — voir
.superpowers/sdd/2026-10-25-score-pertinence-hybride/.
"""

SCORING_VERSION = "1"

# Embedding dédié au score sémantique (Task 2). Distinct de
# app.services.evaluation.domain_relevance.EMBEDDING_MODEL (text-embedding-3-small),
# qui reste utilisé par le pré-filtre de cohérence métier et n'est pas touché ici.
EMBEDDING_MODEL = "mistral/mistral-embed"
EMBED_BATCH = 16
DESCRIPTION_CHARS = 1000

# Bornes de similarité cosinus pour la composante sémantique : en dessous de
# COS_FLOOR, 0 point ; au-dessus de COS_CEIL, le maximum ; interpolation
# linéaire entre les deux.
COS_FLOOR = 0.73
COS_CEIL = 0.83

# Poids des composantes du score (somme = 100 quand toutes sont applicables).
W_SEMANTIC = 45
W_SKILLS = 30
W_SENIORITY = 10
W_SECTOR = 10
W_SIZE = 5

# Seuils de niveau et plafond appliqué quand une condition bloquante échoue
# (géographie, type de contrat...).
STRONG_THRESHOLD = 75
MEDIUM_THRESHOLD = 60
FLOOR = 20
CAP_SCORE = MEDIUM_THRESHOLD - 1
