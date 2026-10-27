"""Records the queries return. Plain data; the graph is the source of truth."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Well:
    api_number: str
    name: str
    spud: date


@dataclass(frozen=True)
class Ownership:
    """Who holds a tract right now, and the TitleEvent that makes it current."""

    tract_id: str
    owners: dict[str, float]  # owner_id -> fractional interest
    as_of: str  # event_id of the latest TitleEvent on the tract


@dataclass(frozen=True)
class TitleEvent:
    event_id: str
    recorded: date
    kind: str
    instrument: str
