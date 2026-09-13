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
    Renvoie markdown filtré au préalable.
    """
    if not url or not url.startswith(("http://", "https://")):
        logger.warning(f"URL invalide: {url}")
        return []

    try:
        logger.info(f"Chargement du contenu depuis: {url}")
        result = await get_filtered_markdown(url)

        if result.get("status") == "success":
            filtered_markdown = result.get("filtered_markdown")
            metadata = result.get("metadata", {})

            # ✅ Gestion correcte selon le type de retour
            if metadata.get("fallback_used", False):
                # Cas fallback : filtered_markdown est un CrawlResultContainer
                logger.info("Utilisation du contenu brut (fallback activé)")

                # Extraire le premier résultat du container
                if (
                    hasattr(filtered_markdown, "__getitem__")
                    and len(filtered_markdown) > 0
                ):
                    crawl_result = filtered_markdown[0]  # Premier élément du container

                    # Essayer différentes sources de contenu, par ordre de préférence
                    if hasattr(crawl_result, "html") and crawl_result.html:
                        content = crawl_result.html
                        content_type = "html"
                    elif (
                        hasattr(crawl_result, "cleaned_html")
                        and crawl_result.cleaned_html
                    ):
                        content = crawl_result.cleaned_html
                        content_type = "cleaned_html"
                    elif hasattr(crawl_result, "markdown") and crawl_result.markdown:
                        content = crawl_result.markdown
                        content_type = "markdown"
                    else:
                        logger.warning("Aucun contenu exploitable dans le CrawlResult")
                        return []

                    # Titre depuis le CrawlResult
                    title = getattr(crawl_result, "title", None) or metadata.get(
                        "title", ""
                    )

                else:
                    logger.warning("CrawlResultContainer vide ou format inattendu")
                    return []

            else:
                # Cas normal : filtered_markdown est une chaîne de markdown
                logger.info("Utilisation du markdown filtré")
                content = (
                    filtered_markdown if isinstance(filtered_markdown, str) else ""
                )
                title = metadata.get("title", "")
                content_type = "filtered_markdown"

            # ✅ Vérification que le contenu n'est pas vide
            if not content or len(content.strip()) < 10:
                logger.warning("Contenu vide ou trop court après extraction")
                return []

            logger.info(f"Contenu chargé: {len(content)} caractères ({content_type})")

            doc = Document(
                page_content=content,
                metadata={
                    "source": url,
                    "title": title,
                    "word_count": len(content.split()) if content else 0,
                    "timestamp": metadata.get("timestamp", ""),
                    "fallback_used": metadata.get("fallback_used", False),
                    "content_type": content_type,
                },
            )

            logger.info(
                f"Contenu récupéré: 1 document avec {doc.metadata.get('word_count', 0)} mots ({content_type})"
            )
            return [doc]

        elif result.get("status") == "failed":
            logger.error(f"Échec du crawl: {result.get('error')}")
            return []
        else:
            logger.error(
                f"Statut d'erreur: {result.get('status')} - {result.get('error')}"
            )
            return []

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
    max_tokens = 8000  # Limite conservative pour le modèle de résumé
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
        Tu es un expert en recrutement et analyse d'offres d'emploi. Ta tâche est d'analyser le contenu de l'offre situé dans la balise <job_content> et d'en générer une synthèse claire et structurée.

        RÈGLE PRIORITAIRE : si le contenu ne contient pas d'offre d'emploi identifiable (page d'erreur, offre supprimée ou expirée, simple menu, page d'accueil, bandeau cookies), réponds UNIQUEMENT par le mot AUCUNE_OFFRE et rien d'autre. N'invente jamais de synthèse dans ce cas.

        <job_content>
        {text}
        </job_content>

        Présente les informations selon cette structure :
        1. RÉSUMÉ : Présentation synthétique de l'entreprise, de l'intitulé du poste et du contexte global.
        2. MISSIONS : Liste à puces des responsabilités et tâches principales confiées au candidat.
        3. COMPÉTENCES REQUISES : Compétences techniques (hard skills), niveau d'expérience, formation et qualités personnelles (soft skills).
        4. CONDITIONS & AVANTAGES : Type de contrat, localisation, télétravail/présentiel, salaire et avantages notables.

        Règles d'extraction :
        - Sois précis et factuel, en te basant exclusivement sur le texte fourni dans <job_content>.
        """,
    )

    try:
        # Utiliser l'API correcte pour initialiser le modèle
        # Les modèles gpt-5 n'acceptent que temperature=1 : on ne la passe pas
        # et on désactive le raisonnement, inutile pour un résumé structuré.
        model_name = os.getenv("SUMMARY_MODEL", "gpt-5-nano")
        if model_name.startswith("gpt-5"):
            model = ChatOpenAI(model=model_name, reasoning_effort="minimal")
        else:
            model = ChatOpenAI(model=model_name, temperature=0.2)

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

        content = content.strip()

        # Page sans offre exploitable : sentinelle ou chaîne vide littérale
        if content.upper().startswith("AUCUNE_OFFRE") or content in ('""', "''"):
            logger.info("Aucune offre identifiable dans le contenu, résumé vide")
            return ""

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
