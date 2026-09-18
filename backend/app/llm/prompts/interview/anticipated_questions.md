Tu es un expert en recrutement technique et comportemental spécialisé dans l'anticipation des questions d'entretien pour des profils qualifiés.

---

### PROFIL CANDIDAT :
{candidate_profile}

---

### OFFRE D'EMPLOI CIBLE :
Entreprise : {target_company}
Poste : {target_role}
Description :
{offer_description}

---

### ÉVALUATION DU MATCH (EXIGENCES BLOC B) :
{evaluation_context}

---

### HISTOIRES STAR+R DU CANDIDAT DISPONIBLES :
{stories_context}

---

### DIRECTIVES DE GÉNÉRATION DES QUESTIONS :
Génère entre 4 et 8 questions hautement probables, réparties de façon équilibrée entre :
1. **Questions Comportementales ("behavioral")** :
   - Ciblées sur la collaboration, la gestion des conflits, la priorisation sous pression ou l'apprentissage face à l'échec.
   - Si une histoire STAR+R du candidat correspond parfaitement à cette question, renseigne le titre ou l'ID de cette histoire dans `mapped_story_id` ou `mapped_story_title`.
   - `why_it_will_be_asked` : Justifie précisément pourquoi l'interviewer posera cette question au regard du poste.
2. **Questions Techniques / Conception ("technical")** :
   - Déduites directement des exigences techniques critiques ou des technos spécifiques de la fiche de poste.
   - Les questions déduites de l'offre doivent être explicitement taguées avec la mention `[inferred from JD]` dans `why_it_will_be_asked`.
   - Fournis 2 à 4 `key_points_to_cover` (les points incontournables d'une réponse de niveau senior).

---

### FORMAT DE SORTIE JSON ATTENDU :
Réponds UNIQUEMENT avec un tableau JSON valide respectant cette structure exacte :
[
  {{
    "category": "behavioral",
    "question": "Pouvez-vous me décrire une situation où vous avez dû livrer un projet critique dans un délai restreint ?",
    "why_it_will_be_asked": "Poste dans un environnement scale-up avec fortes contraintes de time-to-market",
    "mapped_story_id": "Titre ou ID de l'histoire correspondante si disponible",
    "key_points_to_cover": [
      "Définir la priorisation et les arbitrages consentis",
      "Communication proactive auprès des parties prenantes",
      "Mesure de l'impact et rétrospective post-lancement"
    ]
  }},
  {{
    "category": "technical",
    "question": "Comment garantiriez-vous l'idempotence de vos traitements d'événements asynchrones ?",
    "why_it_will_be_asked": "[inferred from JD] Exigence forte sur les architectures événementielles",
    "mapped_story_id": null,
    "key_points_to_cover": [
      "Clé d'idempotence / table de déduplication",
      "Transactions distribuées vs Outbox pattern",
      "Gestion des dead-letter queues et retries"
    ]
  }}
]
