---
domain: land-title
version: 1
governs:
  - "cypher/**"
  - "landtitle/**"
  - "tests/**"
declarations:
  - "Well: Well"
  - "Tract: Ownership"
  - "TitleEvent: TitleEvent"
parity:
  - "cypher/constraints.cypher <-> landtitle/model.py"
---

# Land and title

## Intent

A landman answers "who owns what, under which lease, and is title clear?"
without opening a spreadsheet. A drilling engineer sees the well, its lease,
and the owners of the tracts under it on one page.

## Entities

- **Operator** — the company that holds leases and drills wells. Key: `operator_id`.
- **Lease** — a mineral lease granting rights over one or more tracts. Key: `lease_id`.
- **Tract** — a surveyed parcel of land. Key: `tract_id`.
- **Well** — a wellbore drilled under a lease. Key: `api_number`.
- **MineralOwner** — a person or entity holding a fractional mineral interest in a tract. Key: `owner_id`.
- **TitleEvent** — a recorded instrument that changes who owns a tract's minerals. Key: `event_id`.

## Relationships

- `(Operator)-[OPERATES]->(Lease)`  1..*
- `(Lease)-[COVERS]->(Tract)`  1..*
- `(Lease)-[HAS]->(Well)`  1..*
- `(Tract)-[OWNED_BY]->(MineralOwner)`  1..*  (edge properties: `interest`, a fraction; `since`, the event_id that created the edge)
- `(TitleEvent)-[CHANGES]->(Tract)`  1

## Invariants

- Ownership of a Tract is the traversal `Tract -[OWNED_BY]-> MineralOwner` as of the latest TitleEvent on that Tract. It is never stored as a property on a Well, a Lease, or a Tract. [gate: `landtitle/queries.py:owner_of`; `landtitle/model.py:Well`; `cypher/seed.cypher`; `tests/test_queries.py:test_owner_of_returns_current_interests_by_owner`]
- A TitleEvent is recorded once: its `event_id` is never written twice. [gate: constraint `title_event_id` in `cypher/constraints.cypher`; `tests/test_title_events.py:test_title_event_append_only`]
- The title chain of a Tract is ordered by recording date, and ownership answers as of the last event in that order. [gate: `landtitle/queries.py:title_chain`; `tests/test_queries.py:test_title_chain_is_ordered_by_recording_date`; `tests/test_queries.py:test_owner_of_reports_the_latest_title_event`]
- Every entity key is unique. [gate: the six constraints in `cypher/constraints.cypher`]
- Every Well sits under at least one Lease.

## Vocabulary

- **Lease** — a mineral lease. Never a surface lease, never a rental.
- **Unit** — a set of pooled tracts treated as one for production. Not a unit of measurement.
- **Spud** — the date drilling began. Not the permit date.
- **Clear title** — every TitleEvent in the chain is recorded and uncontested. Not "a landman looked at it."

## Absence and silence

- A Tract with no MineralOwner is an error, not an unowned tract.
- A Tract whose TitleEvents do not reach the present has unverified title. It is not clear.
- There is no such thing as a Well with no Lease.

## Out of scope

- Production volumes and revenue. This system records ownership; it does not compute what anyone is paid.
- Surface rights and surface leases.
- The permitting workflow with the state regulator.

## Changelog

- 2026-10-27 — Initial ontology from the interview.
