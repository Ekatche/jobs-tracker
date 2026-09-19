import asyncio
import os
import re
import logging
from datetime import datetime, timezone
from app.services.job_offers import (
    get_urls,
    get_job_offers_from_query,
)
from app.database import get_database
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError
from app.services.normalization import (
    compute_unique_key,
    extract_company_from_url,
    clean_job_title_syntax,
    clean_html_entities_and_tags,
    normalize_offer_fields,
    normalize_city,
    extract_seniority,
    deduplicate_and_merge_offers,
    merge_multidiffusion_offers,
    are_offers_duplicates,
    normalize_company,
)
from app.services.role_normalizer import normalize_role
from app.services.relevance import (
    RELEVANCE_FILTER_ENABLED,
    is_off_domain_url,
)

# Borne par requête pour collect_offers_sync : jusqu'à 8 requêtes × 7 min = 56 min,
# sous l'execution_timeout de 60 min de la tâche Airflow. Sans cette borne,
# une requête qui pend consomme tout le budget et tue les autres.
COLLECT_QUERY_TIMEOUT = 420
MAX_QUERIES_PER_PROFILE = 3
MAX_TOTAL_QUERIES = 8

DEFAULT_QUERIES: list[str] = [
    "Je recherche un poste de data scientist proche de Lyon",
    "Je recherche un poste d'ingénieur IA (AI engineer) proche de Lyon",
    "Je recherche un poste de data engineer proche de Lyon",
    "Je recherche un poste de machine learning engineer proche de Lyon",
    "Je recherche un poste d'ingénieur MLOps proche de Lyon",
    "Je recherche un poste de LLM engineer / ingénieur IA générative proche de Lyon",
]


def setup_logger():
    """Configure le logger selon l'environnement"""
    env = os.getenv("ENVIRONMENT", "development")

    if env == "production":
        level = logging.WARNING
    elif env == "airflow":
        level = logging.INFO
    else:
        level = logging.DEBUG

    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    return logger


logger = setup_logger()


# ========================================
# ======== FONCTIONS SPÉCIALISÉES ========
# ========================================


async def get_urls_for_query(query: str) -> list:
    """Étape 1: Récupération des URLs"""
    logger.info(f"🔍 Recherche d'URLs pour: {query}")

    # Vérifications des variables d'environnement
    required_env_vars = ["OPENAI_API_KEY", "TAVILY_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        raise ValueError(f"Variables manquantes: {', '.join(missing_vars)}")

    try:
        urls = await get_urls(query)
        logger.info(f"✅ {len(urls)} URLs trouvées")

        if RELEVANCE_FILTER_ENABLED:
            kept_urls = []
            rejected_count = 0
            for url in urls:
                if is_off_domain_url(url):
                    logger.warning(
                        f"🚫 URL hors-domaine écartée: {url} (requête: '{query}')"
                    )
                    rejected_count += 1
                else:
                    kept_urls.append(url)
            logger.info(
                f"🚫 {rejected_count} URLs hors-domaine écartées, {len(kept_urls)} conservées"
            )
            urls = kept_urls

        return urls
    except Exception as e:
        logger.error(f"💥 Erreur récupération URLs: {e}")
        raise


async def summarize_ats_offer_description(
    raw_description: str,
    poste: str = "",
    entreprise: str = "",
) -> str:
    """Génère une synthèse structurée en 5 sections pour une offre extraite via Zero-Token.

    Si la description est déjà très courte ou si l'appel LLM échoue,
    retourne la description nettoyée en repli gracieux.
    """
    from app.services.ats.router import clean_html_to_text

    cleaned_desc = clean_html_to_text(raw_description)
    if not cleaned_desc or cleaned_desc == "Non spécifié" or len(cleaned_desc) < 120:
        return cleaned_desc

    model_name = os.getenv("SUMMARY_MODEL", "gpt-5-nano")
    prompt = f"""Tu es un expert en recrutement et analyse d'offres d'emploi.
À partir de la description brute ci-dessous pour le poste "{poste}" chez "{entreprise}", génère une synthèse structurée, riche et directement exploitable rédigée en français avec des puces Markdown, organisée en sections claires :

• Contexte & Enjeux : 1 à 2 phrases sur l'entreprise, l'équipe et la mission générale.
• Missions principales : 3 à 5 puces concrètes décrivant les responsabilités quotidiennes et les livrables attendus.
• Profil recherché : niveau d'expérience requis, formation et critères indispensables.
• Stack & Outils : technologies, frameworks, cloud et méthodologies utilisés.
• Avantages & Modalités : politique de télétravail, salaire ou package si mentionnés (sinon omettre ce point).

Règles impératives :
- N'inclus aucune balise HTML (ni <p>, ni <br>, ni <em>). Utilise uniquement du Markdown propre.
- Reste factuel et fidèle au texte d'origine. Ne spécule pas sur des technologies ou avantages non mentionnés.
- Si une section n'est pas mentionnée dans l'offre, omettre ou indiquer "Non spécifié".

Description brute :
{cleaned_desc[:4000]}
"""
    try:
        from litellm import acompletion

        extra_kwargs = {"drop_params": True}
        short = model_name.split("/")[-1].lower()
        if not any(short.startswith(p) for p in ("o1", "o3", "gpt-5", "gpt-o")):
            extra_kwargs["temperature"] = 0.2

        resp = await acompletion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            **extra_kwargs,
        )
        content = resp.choices[0].message.content or ""
        content = content.strip()
        if content:
            return content
        return cleaned_desc
    except Exception as e:
        logger.warning(
            f"Repli sur description brute (échec résumé LLM pour '{poste} - {entreprise}'): {e}"
        )
        return cleaned_desc


async def crawl_urls_for_offers(urls: list) -> list:
    """Étape 2: Crawling des URLs pour extraire les offres (Zero-Token ATS/JSON-LD prioritaire)."""
    logger.info(f"🕷️ Traitement de {len(urls)} URLs")

    if not urls:
        logger.warning("⚠️ Aucune URL à crawler")
        return []

    try:
        from app.services.ats.router import extract_ats_or_jsonld_offer
        import httpx

        ats_offers: list[dict] = []
        remaining_urls: list[str] = []

        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            for url in urls:
                try:
                    direct_offer = await extract_ats_or_jsonld_offer(url, client=client)
                    if direct_offer:
                        ats_offers.append(direct_offer)
                    else:
                        remaining_urls.append(url)
                except Exception as e:
                    logger.debug(f"Erreur extraction directe pour {url}: {e}")
                    remaining_urls.append(url)

        if ats_offers:
            logger.info(f"⚡ {len(ats_offers)} offres extraites via Zero-Token ATS / JSON-LD (0 token LLM)")
            logger.info(f"✨ Structuration et résumé LLM pour {len(ats_offers)} offres Zero-Token...")

            async def _summarize_single(offer: dict) -> dict:
                desc = offer.get("description", "")
                poste = offer.get("poste", "")
                entreprise = offer.get("entreprise", "")
                summary = await summarize_ats_offer_description(desc, poste=poste, entreprise=entreprise)
                offer["description"] = summary
                return offer

            ats_offers = list(await asyncio.gather(*[_summarize_single(o) for o in ats_offers]))

        crawled_offers = []
        if remaining_urls:
            logger.info(f"🕷️ Crawling de repli (Crawl4AI + LLM) pour {len(remaining_urls)} URLs restantes")
            raw_crawled = await get_job_offers_from_query(remaining_urls)
            if isinstance(raw_crawled, list):
                crawled_offers = raw_crawled

        total_offers = ats_offers + crawled_offers
        logger.info(
            f"📊 {len(total_offers)} offres brutes au total "
            f"({len(ats_offers)} Zero-Token, {len(crawled_offers)} Crawl4AI)"
        )
        return total_offers
    except Exception as e:
        logger.error(f"💥 Erreur crawling: {e}")
        raise


async def enrich_offers(offers: list, query: str) -> list:
    """Étape 3: Enrichissement des offres avec métadonnées selon le modèle MongoDB"""
    logger.info(f"🔧 Enrichissement de {len(offers)} offres selon le modèle de données")

    if not offers:
        logger.warning("⚠️ Aucune offre à enrichir")
        return []

    try:
        enriched_offers = []
        invalid_count = 0
        current_time = datetime.now(timezone.utc)

        # Traitement par batch
        batch_size = 20
        for batch_start in range(0, len(offers), batch_size):
            batch = offers[batch_start : batch_start + batch_size]

            for index, offer in enumerate(batch, batch_start + 1):
                try:
                    # Validation des champs requis
                    if not all(key in offer for key in ["poste", "entreprise"]):
                        logger.warning(f"⚠️ Offre invalide (champs manquants): {offer}")
                        invalid_count += 1
                        continue

                    # Nettoyage des champs texte de base (entités HTML, balises, espaces insécables)
                    poste = clean_html_entities_and_tags(str(offer.get("poste", "")).strip())
                    entreprise = clean_html_entities_and_tags(str(offer.get("entreprise", "")).strip())
                    raw_description = str(offer.get("description", "")).strip()
                    if raw_description and ("<" in raw_description or "&" in raw_description):
                        from app.services.ats.router import clean_html_to_text
                        description = clean_html_to_text(raw_description) or "Non spécifié"
                    else:
                        description = clean_html_entities_and_tags(raw_description) or "Non spécifié"

                    localisation = clean_html_entities_and_tags(str(offer.get("localisation", "")).strip())
                    if localisation and localisation.lower() not in {"non spécifié", "inconnu", "none", "null"}:
                        localisation = normalize_city(localisation)

                    date = clean_html_entities_and_tags(str(offer.get("date", "")).strip())
                    type_contrat = clean_html_entities_and_tags(str(offer.get("type_contrat", "")).strip())
                    salaire = clean_html_entities_and_tags(str(offer.get("salaire", "")).strip())
                    mode_travail = clean_html_entities_and_tags(str(offer.get("mode_travail", "")).strip())
                    competences_cles = offer.get("competences_cles", [])
                    if isinstance(competences_cles, str):
                        competences_cles = [clean_html_entities_and_tags(c.strip()) for c in competences_cles.split(",") if c.strip()]
                    elif isinstance(competences_cles, list):
                        competences_cles = [clean_html_entities_and_tags(str(c).strip()) for c in competences_cles if str(c).strip()]
                    else:
                        competences_cles = []

                    url = str(offer.get("url", "")).strip() or None
                    source_url = str(offer.get("source_url", "")).strip() or None
                    ats_platform = offer.get("ats_platform")

                    # Fallback nom d'entreprise depuis l'URL si manquant ou non spécifié
                    invalid_placeholders = {"non spécifié", "non disponible", "inconnu", "none", "null", "undefined", ""}
                    if (not entreprise or entreprise.lower() in invalid_placeholders) and (url or source_url):
                        fallback_company = extract_company_from_url(url or source_url)
                        if fallback_company:
                            logger.info(
                                f"🏢 Entreprise enrichie via fallback URL: '{fallback_company}' (était '{entreprise}')"
                            )
                            entreprise = fallback_company

                    # Rejet strict des offres avec champs obligatoires vides ou factices ("Non spécifié", 404, etc.)
                    if (
                        not poste
                        or not entreprise
                        or poste.lower() in invalid_placeholders
                        or entreprise.lower() in invalid_placeholders
                    ):
                        logger.warning(
                            f"⚠️ Offre rejetée (poste ou entreprise invalide/non spécifié): poste='{poste}', entreprise='{entreprise}'"
                        )
                        invalid_count += 1
                        continue

                    # Nettoyage Couche 1 & Extraction Couche 2
                    clean_poste = clean_job_title_syntax(poste)
                    seniority_level = extract_seniority(poste, description)
                    try:
                        canonical_title = await normalize_role(clean_poste)
                    except Exception:
                        canonical_title = clean_poste

                    # Clé d'unicité normalisée avec intitulé nettoyé
                    unique_key = compute_unique_key(
                        company=entreprise,
                        position=clean_poste,
                        location=localisation,
                        url=url,
                    )

                    # ✅ Enrichissement selon le modèle MongoDB complet
                    enriched_offer = {
                        # ===== CHAMPS PRINCIPAUX =====
                        "poste": clean_poste,
                        "raw_poste": poste,
                        "canonical_title": canonical_title,
                        "seniority_level": seniority_level,
                        "entreprise": entreprise,
                        "description": description,
                        "localisation": (
                            localisation if localisation else "Non spécifié"
                        ),
                        "date": date if date else "Non spécifié",
                        "type_contrat": type_contrat if type_contrat else "Non spécifié",
                        "salaire": salaire if salaire else "Non spécifié",
                        "mode_travail": mode_travail if mode_travail else "Non spécifié",
                        "competences_cles": competences_cles,
                        "url": url,
                        "alternative_urls": offer.get("alternative_urls") or [],
                        "source_url": source_url,
                        "ats_platform": ats_platform,
                        "unique_key": unique_key,
                        # ===== MÉTADONNÉES DE COLLECTE =====
                        "source_query": query,
                        "created_at": current_time,
                        "updated_at": current_time,
                        # ===== CHAMPS DE GESTION & ÉTATS =====
                        "pipeline_stage": offer.get("pipeline_stage") or "discovered",
                        "is_deleted": False,  # Nouveau champ pour soft delete
                        "deleted_date": None,  # Date de suppression (None par défaut)
                        # ===== RAW DATA (données originales) =====
                        "raw_data": offer,
                    }

                    enriched_offers.append(enriched_offer)

                    # Log détaillé pour les premières offres (debug)
                    if index <= 3:
                        logger.debug(
                            f"🔍 Offre {index} enrichie: {enriched_offer['poste']} chez {enriched_offer['entreprise']}"
                        )

                except Exception as e:
                    logger.warning(f"⚠️ Erreur enrichissement offre {index}: {e}")
                    logger.debug(f"Offre problématique: {offer}")
                    invalid_count += 1
                    continue

        logger.info(
            f"✅ {len(enriched_offers)} offres enrichies selon le modèle MongoDB "
            f"({invalid_count} invalides)"
        )

        return enriched_offers

    except Exception as e:
        logger.error(f"💥 Erreur enrichissement: {e}")
        raise


async def clean_duplicate_offers(offers: list) -> list:
    """Étape 4: Nettoyage des doublons et fusion multi-sources (Couche 3 & 4)"""
    logger.info(f"🧹 Nettoyage des doublons sur {len(offers)} offres")

    if not offers:
        logger.warning("⚠️ Aucune offre à nettoyer")
        return []

    try:
        cleaned_offers = deduplicate_and_merge_offers(offers)

        removed_count = len(offers) - len(cleaned_offers)
        logger.info(
            f"✅ Nettoyage terminé: {removed_count} doublons fusionnés/supprimés, {len(cleaned_offers)} offres conservées"
        )
        return cleaned_offers

    except Exception as e:
        logger.error(f"💥 Erreur nettoyage doublons: {e}")
        raise


async def save_offers_to_database(offers: list) -> dict:
    """Étape 6: Sauvegarde en base de données avec réconciliation cross-sources et fusion intelligente"""
    logger.info(f"💾 Sauvegarde de {len(offers)} offres")

    if not offers:
        logger.warning("⚠️ Aucune offre à sauvegarder")
        return {"saved": 0, "updated": 0}

    try:
        db = await get_database()
        collection = db["job_offers"]

        # 1. Déduplication multi-critères en mémoire sur le lot entrant
        consolidated_offers = deduplicate_and_merge_offers(offers)

        saved_count = 0
        updated_count = 0
        error_count = 0

        for offer in consolidated_offers:
            try:
                offer_url = (offer.get("url") or "").strip()
                company = offer.get("entreprise", "")
                position = offer.get("poste", "")
                location = offer.get("localisation")

                unique_key = offer.get("unique_key") or compute_unique_key(
                    company=company,
                    position=position,
                    location=location,
                    url=offer_url,
                )
                offer["unique_key"] = unique_key

                # Recherche directe en base par clé unique ou URL (principale ou alternative)
                query_conditions = [{"unique_key": unique_key}]
                if offer_url:
                    query_conditions.append({"url": offer_url})
                    query_conditions.append({"alternative_urls": offer_url})
                if offer.get("alternative_urls"):
                    query_conditions.append({"url": {"$in": offer["alternative_urls"]}})

                existing_doc = await collection.find_one({"$or": query_conditions})

                # Si non trouvé directement, recherche sémantique parmi les offres de la même entreprise
                if not existing_doc and company:
                    norm_comp = normalize_company(company).lower()
                    if norm_comp and norm_comp != "non spécifié":
                        company_candidates = await collection.find(
                            {"entreprise": {"$regex": f"^{re.escape(norm_comp)}$", "$options": "i"}}
                        ).to_list(20)
                        for candidate in company_candidates:
                            if are_offers_duplicates(candidate, offer):
                                existing_doc = candidate
                                break

                if existing_doc:
                    # Fusion des offres avec conservation de la source prioritaire et des métadonnées
                    merged = merge_multidiffusion_offers(existing_doc, offer)
                    update_fields = {
                        k: v for k, v in merged.items()
                        if k not in {"_id", "created_at", "date_creation"}
                    }
                    update_fields["unique_key"] = unique_key
                    update_fields["updated_at"] = datetime.now(timezone.utc)

                    await collection.update_one(
                        {"_id": existing_doc["_id"]},
                        {"$set": update_fields}
                    )
                    updated_count += 1
                else:
                    # Nouvelle offre
                    new_doc = dict(offer)
                    new_doc["unique_key"] = unique_key
                    new_doc["created_at"] = offer.get("created_at") or datetime.now(timezone.utc)
                    new_doc["updated_at"] = datetime.now(timezone.utc)
                    try:
                        await collection.insert_one(new_doc)
                        saved_count += 1
                    except Exception as ins_err:
                        # En cas de conflit rare d'index unique (ex: course concurrente), repli sur mise à jour
                        logger.warning(f"⚠️ Conflit d'insertion pour {unique_key}, repli sur update: {ins_err}")
                        fallback_filter = {"unique_key": unique_key}
                        if offer_url:
                            fallback_filter = {"$or": [{"url": offer_url}, {"unique_key": unique_key}]}
                        await collection.update_one(
                            fallback_filter,
                            {"$set": {k: v for k, v in new_doc.items() if k != "_id"}},
                            upsert=True,
                        )
                        updated_count += 1

            except Exception as e:
                logger.warning(f"⚠️ Erreur traitement offre {offer.get('poste')}: {e}")
                error_count += 1
                continue

        logger.info(
            f"✅ Sauvegarde terminée: {saved_count} créées, {updated_count} mises à jour"
        )

        if error_count > 0:
            logger.warning(f"⚠️ {error_count} erreurs lors de la sauvegarde")
            if saved_count == 0 and updated_count == 0:
                raise RuntimeError(
                    f"Sauvegarde totalement échouée: {error_count}/{len(offers)} offres perdues"
                )

        return {"saved": saved_count, "updated": updated_count}

    except Exception as e:
        logger.error(f"💥 Erreur sauvegarde: {e}")
        raise


async def cleanup_resources():
    """Étape 7: Nettoyage des ressources"""
    logger.info("🧹 Nettoyage des ressources")

    try:
        from app.services.job_offers import cleanup_shared_configs

        await cleanup_shared_configs()
        logger.info("✅ Ressources nettoyées")
    except Exception as e:
        logger.warning(f"⚠️ Erreur nettoyage: {e}")


# ========================================
# ======== FONCTIONS SYNC POUR AIRFLOW ===
# ========================================




def enrich_offers_sync(offers: list, query: str) -> list:
    """Version sync pour Airflow - Étape 3"""
    os.environ.setdefault("ENVIRONMENT", "airflow")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(
            asyncio.wait_for(enrich_offers(offers, query), timeout=300)
        )
    finally:
        loop.close()




async def collect_and_save_offers(query: str) -> dict:
    """Version asynchrone complète pour collecter, nettoyer et enregistrer les offres"""
    logger.info(f"🚀 Collecte async démarrée: {query}")
    try:
        urls = await get_urls_for_query(query)
        offers = await crawl_urls_for_offers(urls)
        enriched = await enrich_offers(offers, query)
        cleaned = await clean_duplicate_offers(enriched)
        return await save_offers_to_database(cleaned)
    finally:
        await cleanup_resources()


def collect_offers_sync(query: str) -> dict:
    """Version sync pour Airflow — une seule boucle d'événements par requête."""
    os.environ.setdefault("ENVIRONMENT", "airflow")
    try:
        logger.info(f"🚀 Collecte complète démarrée: {query}")
        # jusqu'à 8 requêtes × 7 min = 56 min, sous l'execution_timeout de 60 min du DAG.
        # Sans cette borne, une requête qui pend consomme tout le budget de la tâche.
        result = asyncio.run(
            asyncio.wait_for(collect_and_save_offers(query), timeout=COLLECT_QUERY_TIMEOUT)
        )
        logger.info(f"🎯 Collecte terminée: {result}")
        return result
    except Exception as e:
        logger.error(f"💥 Erreur collecte complète: {e}")
        raise


async def build_search_queries() -> list[str]:
    """Génère dynamiquement les requêtes de recherche depuis les préférences des candidats.

    Interroge la collection candidate_profile, combine rôles cibles et localisations,
    déduplique entre candidats, assure une sélection équitable en round-robin plafonnée
    à MAX_TOTAL_QUERIES, et bascule sur DEFAULT_QUERIES en cas d'erreur ou d'absence de données.
    """
    try:
        db = await get_database()
        cursor = db["candidate_profile"].find({})
        profiles = await cursor.to_list(length=100)

        from app.services.role_normalizer import normalize_role

        memo_normalized: dict[str, str] = {}
        profiles_queries_list: list[list[str]] = []

        for profile in profiles:
            prefs = profile.get("preferences") or {}
            raw_target_roles = [
                r.strip() for r in (prefs.get("target_roles") or []) if isinstance(r, str) and r.strip()
            ]
            if not raw_target_roles:
                continue

            target_roles: list[str] = []
            seen_profile_roles: set[str] = set()
            for r in raw_target_roles:
                cleaned_r = clean_job_title_syntax(r)
                if not cleaned_r or cleaned_r == "Non spécifié":
                    cleaned_r = r
                r_key = cleaned_r.lower()
                if r_key in memo_normalized:
                    norm_role = memo_normalized[r_key]
                else:
                    norm_role = await normalize_role(cleaned_r, db=db)
                    memo_normalized[r_key] = norm_role

                norm_key = norm_role.lower()
                if norm_key not in seen_profile_roles:
                    seen_profile_roles.add(norm_key)
                    target_roles.append(norm_role)

            if not target_roles:
                continue

            locations = [
                loc.strip() for loc in (prefs.get("locations") or []) if isinstance(loc, str) and loc.strip()
            ]
            remote_policy = prefs.get("remote_policy")
            is_full_remote = str(remote_policy).lower() in ("full_remote", "remotepolicy.full_remote")
            contract_types = prefs.get("contract_types") or []
            contract_suffix = f" ({contract_types[0]})" if contract_types else ""

            candidate_queries: list[str] = []
            if locations:
                for role in target_roles:
                    for loc in locations:
                        candidate_queries.append(
                            f"Je recherche un poste de {role} proche de {loc}{contract_suffix}"
                        )
            elif is_full_remote:
                for role in target_roles:
                    candidate_queries.append(
                        f"Je recherche un poste de {role} en télétravail{contract_suffix}"
                    )
            else:
                for role in target_roles:
                    candidate_queries.append(
                        f"Je recherche un poste de {role}{contract_suffix}"
                    )

            if candidate_queries:
                profiles_queries_list.append(candidate_queries[:MAX_QUERIES_PER_PROFILE])

        if not profiles_queries_list:
            logger.info("ℹ️ Aucun profil candidat avec rôles cibles trouvé, utilisation de DEFAULT_QUERIES")
            return list(DEFAULT_QUERIES)

        # Sélection en Round-Robin équitable entre profils avec déduplication normalisée
        selected_queries: list[str] = []
        seen_keys: set[str] = set()

        round_idx = 0
        while len(selected_queries) < MAX_TOTAL_QUERIES:
            added_in_round = False
            for p_queries in profiles_queries_list:
                if round_idx < len(p_queries):
                    query = p_queries[round_idx].strip()
                    dedup_key = query.lower()
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        selected_queries.append(query)
                        if len(selected_queries) >= MAX_TOTAL_QUERIES:
                            break
                    added_in_round = True
            if not added_in_round:
                break
            round_idx += 1

        if not selected_queries:
            return list(DEFAULT_QUERIES)

        logger.info(f"✅ {len(selected_queries)} requêtes de recherche dynamiques générées: {selected_queries}")
        return selected_queries

    except Exception as e:
        logger.warning(
            f"⚠️ Erreur lors de la génération dynamique des requêtes: {e}, utilisation du fallback DEFAULT_QUERIES"
        )
        return list(DEFAULT_QUERIES)


def build_search_queries_sync() -> list[str]:
    """Version synchrone pour Airflow avec boucle d'événements dédiée et résilience."""
    os.environ.setdefault("ENVIRONMENT", "airflow")
    try:
        return asyncio.run(build_search_queries())
    except Exception as e:
        logger.warning(
            f"⚠️ Erreur execution sync build_search_queries: {e}, utilisation du fallback DEFAULT_QUERIES"
        )
        return list(DEFAULT_QUERIES)

