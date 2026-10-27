# Interview crib sheet

Phase 1b of the skill asks five questions. Type these answers. They are short
on purpose: an ontology the model reads in thirty seconds beats a complete one
it skims. The resulting `ontology/land-title.md` should carry each line below,
and `PROMPTS.md` and `OFFLINE.md` assume it does.

## 1. Intent

> A landman answers "who owns what, under which lease, and is title clear?"
> without opening a spreadsheet. A drilling engineer sees the well, its lease,
> and the owners of the tracts under it on one page.

## 2. The load-bearing level

> The title chain. Every tract has an ordered chain of TitleEvents, and
> ownership is whatever the chain says as of its latest event. Nothing stores
> an owner on a well or a lease; you walk Tract to MineralOwner. If that chain
> is wrong or out of order, every answer above it is wrong.

## 3. Vocabulary collisions

> "Lease" is a mineral lease, never a surface lease or a rental.
> "Unit" is a set of pooled tracts treated as one for production, not a unit
> of measurement. "Spud" is the date drilling began, not the permit date.
> "Clear title" means every TitleEvent in the chain is recorded and
> uncontested, not that a landman looked at it.

## 4. Out of scope

> Production volumes and revenue. Surface rights and surface leases.
> The permitting workflow with the state regulator. This system records
> ownership; it does not compute what anyone is paid.

## 5. Silence and absence

> A tract with no owner is an error, not an unowned tract. A tract whose
> TitleEvents don't reach the present has unverified title; it is not clear.
> There is no such thing as a well with no lease.

## Governed paths

When the skill asks what the ontology governs, or drafts the list, confirm:

```yaml
governs:
  - "cypher/**"
  - "landtitle/**"
  - "tests/**"
```

`tests/**` is in the list because the tests are the gates, and each gate line
names its test file (`tests/test_queries.py:test_...`). The checker matches
gate files by name, so that is what makes a weakened test block the edit.
