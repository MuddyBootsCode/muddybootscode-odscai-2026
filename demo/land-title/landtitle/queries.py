"""Read queries. Ownership is always derived by traversal; nothing stores it."""
from __future__ import annotations

from neo4j import Driver

from landtitle.model import Ownership, TitleEvent, Well


def owner_of(driver: Driver, tract_id: str) -> Ownership | None:
    """Current owners of a tract and the TitleEvent the answer is good as of.

    Walks Tract -[OWNED_BY]-> MineralOwner for the interests and
    TitleEvent -[CHANGES]-> Tract for the latest recorded event.
    """
    records, _, _ = driver.execute_query(
        """
        MATCH (t:Tract {tract_id: $tract_id})
        OPTIONAL MATCH (t)-[r:OWNED_BY]->(o:MineralOwner)
        WITH t, o.owner_id AS owner_id, sum(r.interest) AS interest
        WITH t, collect({owner_id: owner_id, interest: interest}) AS owners
        OPTIONAL MATCH (e:TitleEvent)-[:CHANGES]->(t)
        WITH owners, e ORDER BY e.recorded DESC LIMIT 1
        RETURN owners, e.event_id AS as_of
        """,
        tract_id=tract_id,
    )
    if not records:
        return None
    row = records[0]
    owners = {o["owner_id"]: o["interest"] for o in row["owners"] if o["owner_id"] is not None}
    return Ownership(tract_id=tract_id, owners=owners, as_of=row["as_of"])


def wells_under(driver: Driver, lease_id: str) -> list[Well]:
    records, _, _ = driver.execute_query(
        """
        MATCH (:Lease {lease_id: $lease_id})-[:HAS]->(w:Well)
        RETURN w.api_number AS api_number, w.name AS name, w.spud AS spud
        ORDER BY api_number
        """,
        lease_id=lease_id,
    )
    return [Well(r["api_number"], r["name"], r["spud"].to_native()) for r in records]


def title_chain(driver: Driver, tract_id: str) -> list[TitleEvent]:
    records, _, _ = driver.execute_query(
        """
        MATCH (e:TitleEvent)-[:CHANGES]->(:Tract {tract_id: $tract_id})
        RETURN e.event_id AS event_id, e.recorded AS recorded, e.kind AS kind, e.instrument AS instrument
        ORDER BY recorded, event_id
        """,
        tract_id=tract_id,
    )
    return [TitleEvent(r["event_id"], r["recorded"].to_native(), r["kind"], r["instrument"]) for r in records]
