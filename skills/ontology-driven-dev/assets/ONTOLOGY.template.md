---
domain: oil-gas
version: 1
governs:
  - "migrations/**"
  - "src/models/**"
  - "cypher/constraints.cypher"
---

# Oil & gas · Land and title

## Intent

A landman answers "who owns what, under which lease, and is title clear?"
without opening a spreadsheet. A drilling engineer sees the well, the lease,
and the owner on one page.

## Entities

One line each. The noun, what it is here, and the key that identifies it.

- **Operator** — the company that holds leases and drills wells. Key: `operator_id`.
- **Lease** — a mineral lease granting rights over one or more tracts. Key: `lease_id`.
- **Tract** — a surveyed parcel of land. Key: `tract_id`.
- **Well** — a wellbore drilled under one or more leases. Key: `api_number`.
- **MineralOwner** — a person or entity holding mineral rights in a tract. Key: `owner_id`.
- **TitleEvent** — a recorded change in ownership of a tract's minerals. Key: `event_id`.
- **Landman** — the person who verifies title. Key: `landman_id`.

## Relationships

Direction and cardinality matter. Write them as `(From)-[VERB]->(To)  cardinality`.

- `(Operator)-[OPERATES]->(Lease)`  1..*
- `(Lease)-[COVERS]->(Tract)`  1..*
- `(Lease)-[HAS]->(Well)`  1..*
- `(Tract)-[OWNED_BY]->(MineralOwner)`  1..*  (fractional interests allowed)
- `(TitleEvent)-[CHANGES]->(Tract)`  1
- `(Landman)-[CLEARS]->(Tract)`  0..*

## Invariants

What must always hold. Each one gets a gate, written in brackets after it.
An invariant with no gate is a wish.
Say each one in the domain's words; a code name goes in the gate note as `code: …`,
never as the subject of the sentence.

- Every Well has at least one Lease, and a Well–Lease pair is recorded once. [gate: `well_leases` PK `(api_number, lease_id)` + FKs; `test_well_has_lease`]
- Every Tract under a Lease has at least one MineralOwner of record. [gate: `test_tract_has_owner`]
- TitleEvent is append-only. Never UPDATE or DELETE a TitleEvent. [gate: DB trigger `title_event_immutable`; `test_title_event_append_only`]
- Ownership of a Tract is the traversal `Tract -[OWNED_BY]-> MineralOwner` as of the latest TitleEvent. It is never stored as a property on Well. [gate: `test_no_owner_column_on_well`]

## Vocabulary

What a word means here — and what it does not mean. The "not" is the part
the model needs most.

- **Lease** — a mineral lease. Never a surface lease, never a rental agreement.
- **Unit** — a set of pooled tracts treated as one for production. Not a unit of measurement.
- **Spud** — the date drilling began. Not the date the well was permitted.
- **Clear title** — every TitleEvent in the chain is recorded and uncontested. Not "the landman looked at it."

## Absence and silence

What a missing value means. The model's default is to ignore or interpolate; say otherwise here.

- A Tract with no MineralOwner is an error, not an unowned tract.
- A Well with no TitleEvent on its Tract has unverified title; it is not clear.

## Out of scope

What this system deliberately does not do. The section that stops scope creep.

- Production volumes and revenue. Not this system.
- Surface rights and surface leases.
- Permitting workflow with the state regulator.

## Changelog

One line per change to this file, newest first. Reference the commit or ticket.

- 2026-10-22 — Added `Ownership is a traversal` invariant after the owner-column mistake.
- 2026-10-01 — Initial ontology.
