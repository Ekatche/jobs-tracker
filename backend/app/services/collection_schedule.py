"""Créneaux du DAG de collecte `collect_job_offers_granular`.

Airflow tourne en UTC (`core.default_timezone = utc`, `start_date` naïve) : le
cron `0 7,16 * * 1-5` déclenche à 07:00 et 16:00 UTC, du lundi au vendredi.
Un test vérifie que COLLECTION_CRON suit le cron du DAG.
"""

from datetime import datetime, time, timedelta, timezone

COLLECTION_CRON = "0 7,16 * * 1-5"
_HOURS_UTC = (7, 16)
_WEEKDAYS = range(0, 5)  # lundi..vendredi


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _slots(day: datetime):
    if day.weekday() in _WEEKDAYS:
        for hour in _HOURS_UTC:
            yield datetime.combine(day.date(), time(hour), tzinfo=timezone.utc)


def next_collection_at(now: datetime) -> datetime:
    """Prochain créneau strictement après `now` (naïf = UTC)."""
    now = _as_utc(now)
    for offset in range(8):
        for slot in _slots(now + timedelta(days=offset)):
            if slot > now:
                return slot
    raise AssertionError("aucun créneau de collecte sur 8 jours")


def previous_collection_at(now: datetime) -> datetime:
    """Dernier créneau à `now` ou avant (naïf = UTC)."""
    now = _as_utc(now)
    for offset in range(8):
        for slot in reversed(list(_slots(now - timedelta(days=offset)))):
            if slot <= now:
                return slot
    raise AssertionError("aucun créneau de collecte sur 8 jours")
