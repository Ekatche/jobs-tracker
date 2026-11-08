"""Pipeline de liste des offres : structure du $lookup de pertinence (pur, sans Mongo)."""
from app.routers.job_offers import _build_list_pipeline, relevance_lookup_stages
from tests.job_offers_relevance.relevance_fixtures import USER_A_ID, _make_user


def test_relevance_lookup_filters_by_current_user():
    """Pure : le sous-pipeline du $lookup filtre bien sur l'utilisateur courant."""
    stages = relevance_lookup_stages("u1")
    lookup_stage = next(s for s in stages if "$lookup" in s)
    assert lookup_stage["$lookup"]["from"] == "offer_relevance"
    sub_pipeline = lookup_stage["$lookup"]["pipeline"]
    match_stage = next(s for s in sub_pipeline if "$match" in s)
    assert match_stage["$match"] == {"user_id": "u1"}


def test_build_list_pipeline_recent_sort_places_lookup_after_limit():
    """M2 (structurel) : en tri `recent`, le lookup de pertinence n'est pas requis
    par le tri final, il peut donc être reporté après `$skip`/`$limit`."""
    pipeline = _build_list_pipeline(
        {}, sort="recent", current_user=_make_user(USER_A_ID), skip=0, limit=10
    )
    limit_index = next(i for i, stage in enumerate(pipeline) if "$limit" in stage)
    lookup_index = next(i for i, stage in enumerate(pipeline) if "$lookup" in stage)
    assert lookup_index > limit_index


def test_build_list_pipeline_relevance_sort_places_lookup_before_sort():
    """M2 : en tri `relevance`, `_score_sort` dépend du lookup, qui doit donc le
    précéder."""
    pipeline = _build_list_pipeline(
        {}, sort="relevance", current_user=_make_user(USER_A_ID), skip=0, limit=10
    )
    sort_on_score_index = next(
        i
        for i, stage in enumerate(pipeline)
        if "$sort" in stage and "_score_sort" in stage["$sort"]
    )
    lookup_index = next(i for i, stage in enumerate(pipeline) if "$lookup" in stage)
    assert lookup_index < sort_on_score_index


def test_build_list_pipeline_ends_with_unset_of_internal_fields():
    """M21 : preuve structurelle, sur le pipeline construit et pas sur la réponse,
    que les champs internes du lookup ne survivent jamais à la construction."""
    pipeline = _build_list_pipeline(
        {}, sort="relevance", current_user=_make_user(USER_A_ID), skip=0, limit=10
    )
    assert pipeline[-1] == {"$unset": ["_relevance", "_oid_str", "_score_sort"]}
