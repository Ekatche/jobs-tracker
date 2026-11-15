from dataclasses import dataclass, field as dc_field
from typing import List, Optional, Tuple

from .constants import ATOMIC_FIELDS


@dataclass
class Finding:
    """Une affirmation du CV adapté, avec son emplacement (expérience, puce, champ)."""

    message: str
    field: str
    experience_index: Optional[int] = None
    group_index: Optional[int] = None
    item_index: Optional[int] = None

    @property
    def atomic(self) -> bool:
        return self.field in ATOMIC_FIELDS

    def __str__(self) -> str:
        return self.message


@dataclass
class CVAudit:
    """violations : inventions confirmées. unverifiable : formulations non vérifiables."""

    violations: List[Finding] = dc_field(default_factory=list)
    unverifiable: List[Finding] = dc_field(default_factory=list)


@dataclass(frozen=True)
class _Metric:
    raw: str
    canon: Tuple[str, float]
    mantissa: float
    context: str = ""
    noun: str = ""
