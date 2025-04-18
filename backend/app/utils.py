from bson import ObjectId


def serialize_mongodb_doc(doc):
    """
    Convertit un document MongoDB en un document sérialisable pour JSON
    """
    if not doc:
        return None

    # Créer une copie du document pour éviter de modifier l'original
    serialized = dict(doc)

    # Convertir les ObjectId en str
    for key, value in serialized.items():
        if isinstance(value, ObjectId):
            serialized[key] = str(value)

    # S'assurer que location est bien inclus (même si None)
    if "location" not in serialized and isinstance(doc, dict):
        serialized["location"] = None

    return serialized


def capitalize_words(text):
    """
    Capitalise la première lettre de chaque mot dans une chaîne de caractères.
    """
    if not text:
        return text

    # Sépare les mots et capitalise chacun d'eux
    return " ".join(word.capitalize() for word in text.split())
