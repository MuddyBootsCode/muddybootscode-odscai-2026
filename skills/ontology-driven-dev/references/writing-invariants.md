# Writing invariants the model can be held to

An invariant is a sentence the model could violate. If nothing the model does could break it, it's a description, not a rule — move it to Intent or delete it. Four shapes cover most domains.

## 1. Grain — "the load-bearing level"

The one level at which counts, sums, and uniqueness are defined. Every hierarchy has one; if the ontology doesn't name it, the model will aggregate at whatever level is convenient for the query.

- **Higher education:** The reporting grain is (institution, CIP4 program code, credential level). One row per grain per period. [gate: unique index on those three columns; `test_grain_uniqueness`]
- **Monitoring:** Thresholds belong to the Asset, not the Sensor. [gate: FK from threshold to asset; no `sensor_id` column on threshold]

Gate pattern: a uniqueness constraint at the grain plus a reconciliation test that row counts at the grain equal the distinct-key count in source.

## 2. Chain — "ownership is a path, not a property"

When the answer to "who owns / who is responsible / what applies" is a traversal, say so, and forbid the shortcut of copying the end of the path onto the start.

- **Land and title:** Ownership of a Tract is the traversal `Tract -[OWNED_BY]-> MineralOwner` as of the latest TitleEvent. It is never stored as a property on Well. [gate: schema has no `owner` column on wells; `test_no_owner_column_on_well`]
- **Any chain:** Every link in the chain exists. A Well has at least one Lease; every Tract under a Lease has an owner of record. [gate: junction PK + FKs; existence test]

Gate pattern: cardinality constraints on every hop, plus a schema test that the denormalized shortcut column does not exist.

## 3. Ordering and immutability

Append-only logs, time-ordered events, monotonic sequences.

- TitleEvent is append-only. Never UPDATE or DELETE. [gate: DB trigger or revoked privileges; `test_title_event_append_only`]
- Readings are time-ordered per Sensor. [gate: `test_reading_monotonic_per_sensor`]

Gate pattern: a trigger or permission at the database, and a test that writes an out-of-order or updated row and expects a failure.

## 4. Absence — "what silence means"

The model's default for a missing value is to interpolate, skip, or treat as null. If the domain disagrees, write it down; this is the rule most often missing from a first draft.

- **Monitoring:** A missed interval is itself a Reading (status = `missing`) and can raise an Alert. [gate: gap-filling step in the pipeline; `test_gap_becomes_reading`]
- **Title:** A Tract with no MineralOwner is an error, not an unowned tract. [gate: `test_tract_has_owner`]

Gate pattern: a data-quality assertion that the "absent" case is represented explicitly, not elided.

## Turning a bug into an invariant

When a gate misses, the ontology was thin. Write the missing rule in this form:

1. What was true in the data that nothing said must be true? ("A program's title and its code came from different authorities.")
2. State it as a rule. ("Program.title and Program.cip4_code are sourced from the same crosswalk.")
3. Derive the gate. (`test_title_matches_crosswalk`: every (code, title) pair appears in the crosswalk table; zero mismatches on full load.)
4. Add a Changelog line naming the incident.

The fix is never "more tests." It is one more edge in the graph, and the test follows from it.

## Smell test for a weak invariant

- Uses "should" or "usually" → it's a preference, not a rule. Either make it absolute or drop it.
- Mentions a function name or file path → implementation detail; it will rot. State the rule about the data.
- No gate and you can't think of one → it may not be checkable; ask whether it's really a rule or an intent.
- Two invariants that could both be true but contradict in practice → the ontology has a hidden assumption. Surface it.

## Reading rules out of repair code

Most domain rules are never written as a check. They are written as a fix: the code takes bad input and quietly makes it legal. Read the fix backwards to get the rule.

| The code does | The rule is |
| --- | --- |
| `start = Math.max(start, previous.end)` | A booking never starts before the previous booking for the same room ends. |
| `boxes.sort((a, b) => a.level - b.level)` then compares `prev.size > cur.size` | Nested boxes shrink: each inner box is smaller than the one around it. |
| `label.width = Math.min(label.width, panel.width)` | A label never extends past the panel it sits in. |
| `if (!accountOpenOn(date)) return null` in a statement renderer | A statement line belongs to an account open on that date. |
| `refund.amount = Math.min(refund.amount, charge.amount)` | A refund never exceeds the charge it refunds. |

Write the rule, not the fix. The fix is the gate: `[gate: bookings.ts:clampStart]`. If the same rule is repaired in the renderer and refused on the server, list both gates; when they disagree, that disagreement is a finding for the user, and the ontology records the rule the user chooses.

Expect a layout or pricing module to yield ten or more of these. A domain file that has fewer invariants than the codebase has clamps is a file the enforcement pass has not reached.

## One sentence, the way the domain says it

An invariant is a sentence a practitioner would say without looking at the code. Hold every line to this:

- One sentence, present tense, under about twenty words.
- No field names, no tolerances, no file paths. Those go in the gate note after it.
- A number only when the number is the rule ("a version tag is at most 50 characters"), never when it is the implementation's tolerance ("within 5 ft").
- If the sentence needs a second clause to stay true, the clause is the gate note, not the rule.
- If it still needs explaining after that, it is not one rule. Split it, or record it as an issue to explore with the user, not a rule to state.

| Harvested from the code | Written as the rule |
| --- | --- |
| The shift before a shift is the one that starts earlier and ends within 5 minutes of this start or after it. | A shift starts where the shift before it ends. `[gate: shifts.ts:findPrevious (5 min tolerance)]` |
| The shown price is the list price minus whichever promotion applies, raised to the floor price when it falls below it. | A shown price never drops below the floor price. `[gate: pricing.ts:shownPrice]` |
| A parcel's shipping rate comes from the carrier table by size and weight within 0.5 kg, else unset with a warning. | A parcel's shipping rate follows from its size and weight. `[gate: shipping.ts:lookupRate (carrier table, else warning)]` |

The enforcement pass produces the left column. Do not stop there: the file holds the right column, and the left column's detail survives only in the gate note.

## A code name is not a domain word

The code names a field or a list after one kind of thing and then stores every kind in it: a `customers` table that holds suppliers too, a `files` list that holds folders, a `user` column that holds service accounts. A rule that uses the code's name then says something false in the domain: "every party lives in customers" tells an accountant that a supplier is a customer, when it is only the table that holds both.

Hold every line to this:

- The sentence names the kind of thing in the domain's word (every trading party). The code's name for where it is stored goes in the gate note, or in parentheses as a name, never as the subject.
- A sentence must still be true with its backticks removed. Readers and panes strip markup; a code name that only made sense as code becomes a domain word, and the wrong one.
- When a code name and a domain word collide, **Vocabulary** records both sides: what the word means in the field, what the code calls it, and which is not a narrower category of the other. The entity line keeps the code's name after the domain word, as its declaration.

| The code says | The rule says |
| --- | --- |
| Every party lives in `customers`; `suppliers` is always empty. | Every trading party, customer or supplier, is stored in one table of parties; the legacy `suppliers` table is always empty. `[gate: … ; code: the `customers` table]` |
| Publishing moves `isLive`, never copies it. | Publishing moves the live mark to another version, never copies it. `[gate: … ; code: `isLive`]` |
| A discount applies where `order.total > tier.min && order.total < tier.max`. | A discount applies to orders strictly inside its range. `[gate: … ; code: strict bounds]` |

The test: read the sentence to the person who owns the domain with every code name spoken as an ordinary word. If they correct you, the code name was carrying the meaning, and the sentence has to carry it instead.
