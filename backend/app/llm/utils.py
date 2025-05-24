from job_crawler.crawler1 import get_filtered_markdown
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
import asyncio
import logging
import os

# Configuration du logging
logger = logging.getLogger(__name__)

# Appliquer nest_asyncio uniquement si ce n'est pas déjà un uvloop.Loop
try:
    import nest_asyncio

    loop = asyncio.get_event_loop()
    # Si la boucle est un uvloop, on ne patche pas
    if not loop.__class__.__module__.startswith("uvloop"):
        nest_asyncio.apply()
    else:
        logger.info("boucle uvloop détectée, nest_asyncio non appliqué")
except Exception as e:
    # Capture à la fois RuntimeError et tout autre problème
    logger.warning(f"nest_asyncio non appliqué : {e}")


async def fetch_documents(url: str):
    """
    Récupère le contenu rendu de la page via Crawl4ai.
    Renvoie mardown filtre au prealable.
    """
    if not url or not url.startswith(("http://", "https://")):
        logger.warning(f"URL invalide: {url}")
        return []

    try:
        logger.info(f"Chargement du contenu depuis: {url}")
        result = await get_filtered_markdown(url)
        if result.get("status") == "success" and result.get("filtered_markdown"):
            markdown_content = result["filtered_markdown"]
            metadata = result.get("metadata", {})

            logger.info(f"Contenu chargé: {markdown_content[:50]}...")

            doc = Document(
                page_content=markdown_content,
                metadata={
                    "source": url,
                    "title": metadata.get("title", ""),
                    "word_count": metadata.get("word_count", 0),
                    "timestamp": metadata.get("timestamp", ""),
                },
            )

            logger.info(
                f"Contenu récupéré: 1 document avec {metadata.get('word_count', 0)} mots"
            )
            return [doc]
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du contenu: {str(e)}")
        return []


def estimate_token_count(text):
    """
    Estimation simple du nombre de tokens basée sur les mots
    (approximation: 1 token ~= 0.75 mots)
    """
    return len(text.split()) * 1.33


def split_documents(docs, chunk_size: int = 2000, chunk_overlap: int = 200):
    """
    Découpe la liste de Document en chunks si nécessaire.
    - chunk_size : taille max d'un chunk en caractères
    - chunk_overlap : recouvrement entre chunks
    """
    # Si la liste est vide, retourner une liste vide
    if not docs:
        return []

    # Estimer la taille totale du contenu
    total_content = "\n\n".join([doc.page_content for doc in docs])

    # Si le contenu est déjà petit, pas besoin de découper
    if len(total_content) < chunk_size:
        logger.info(
            f"Contenu assez court ({len(total_content)} caractères), pas de découpage nécessaire"
        )
        return docs

    # Sinon, découper en morceaux
    logger.info(
        f"Découpage du contenu ({len(total_content)} caractères) en chunks de {chunk_size} caractères"
    )
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],  # Séparateurs hiérarchiques
        length_function=len,
    )
    chunks = splitter.split_documents(docs)
    logger.info(f"Contenu découpé en {len(chunks)} chunks")
    return chunks


async def summarize_chunks(chunks):
    """
    Traite le contenu des chunks et génère un résumé structuré de l'offre d'emploi.
    """

    # Vérifier si la clé API est disponible
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error(
            "OPENAI_API_KEY n'est pas définie dans les variables d'environnement"
        )
        return "La génération automatique de description nécessite une clé API OpenAI valide."

    # Combiner les chunks en un seul texte
    combined_text = "\n\n".join([chunk.page_content for chunk in chunks])

    # Vérifier la taille estimée du texte pour le LLM
    estimated_tokens = estimate_token_count(combined_text)
    logger.info(f"Taille estimée du texte: ~{estimated_tokens:.0f} tokens")

    # Si le texte est trop long, le tronquer
    max_tokens = 8000  # Limite conservative pour gpt-4o-mini
    if estimated_tokens > max_tokens:
        logger.warning(
            f"Texte trop long ({estimated_tokens:.0f} tokens), troncature appliquée"
        )
        words = combined_text.split()
        # On garde environ 75% de la limite max pour laisser de la place à la réponse
        safe_word_count = int(max_tokens * 0.75 / 1.33)
        combined_text = " ".join(words[:safe_word_count])
        logger.info(f"Texte tronqué à environ {safe_word_count} mots")

    prompt = PromptTemplate(
        input_variables=["text"],
        template="""
        Tu es un assistant spécialisé dans l'analyse d'offres d'emploi. Ta tâche est de résumer l'offre d'emploi suivante de manière structurée.

        Extrais et présente les informations suivantes:

        1. RÉSUMÉ: Un paragraphe concis décrivant l'offre (entreprise, poste, contexte)
        2. MISSIONS: Liste des principales responsabilités et tâches du poste
        3. COMPÉTENCES REQUISES: Liste des compétences techniques et soft skills demandées
        4. INFORMATIONS COMPLÉMENTAIRES: Tout élément notable (avantages, équipe, culture, télétravail)

        Sois précis et factuel, en te basant uniquement sur le contenu fourni.

        IMPORTANT: Si le contenu fourni ne contient pas suffisamment d'informations pour établir un résumé pertinent de l'offre d'emploi (par exemple, s'il s'agit d'une page d'accueil, d'une liste d'offres, ou de contenu non pertinent), réponds simplement par une chaîne vide "" sans aucune explication.

        Contenu de l'offre:
        {text}
        """,
    )

    try:
        # Utiliser l'API correcte pour initialiser le modèle
        model = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

        # Créer une chaîne de traitement en utilisant l'opérateur pipe
        chain = prompt | model

        logger.info("Envoi de la requête au LLM")
        # Traiter l'ensemble du texte en une seule fois
        result = await chain.ainvoke({"text": combined_text})

        # Extraire le contenu selon le format de sortie du modèle
        if hasattr(result, "content"):
            content = result.content
        else:
            content = str(result)

        logger.info(f"Résumé généré: {len(content)} caractères")
        return content

    except Exception as e:
        logger.error(f"Erreur lors de la génération du résumé: {str(e)}")
        return ""


# Fonction pratique qui combine toutes les étapes
async def generate_job_description_from_url(url):
    """
    Fonction utilitaire qui combine toutes les étapes pour générer une description
    à partir d'une URL d'offre d'emploi.
    """
    try:
        # Récupérer le contenu
        print(f"Début de génération de description pour URL: {url}")

        docs = await fetch_documents(url)
        if not docs:
            return "Impossible de récupérer le contenu de l'URL fournie."

        # Découper en chunks si nécessaire
        chunks = split_documents(docs)

        # Générer le résumé
        description = await summarize_chunks(chunks)

        return description
    except Exception as e:
        logger.error(f"Erreur lors de la génération de la description: {str(e)}")
        return f"Erreur: {str(e)}"
