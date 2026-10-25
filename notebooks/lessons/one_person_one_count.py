# %% [markdown]
# # 2. One person isn't one row
# **Context Is the Team — Michael Porter / Muddy Boots Code — ODSC AI West 2026**
#
# The question is: **How many people have a completed degree at North in this
# snapshot?** Write down what counts as one before asking an agent for a query.
#
# These institutions and records are synthetic. Run all cells offline with Python's
# standard library; no API key or real student data is involved.
# Suggested live walkthrough: 4–6 minutes. Agent comparison is optional take-home work.
# %%
from pprint import pprint

COMPLETIONS = [
    {"completion_id": "c1", "person_id": "ava", "institution_id": "north", "status": "completed"},
    {"completion_id": "c2", "person_id": "ava", "institution_id": "north", "status": "completed"},
    {"completion_id": "c3", "person_id": "ben", "institution_id": "north", "status": "completed"},
    {"completion_id": "c4", "person_id": "cy", "institution_id": "south", "status": "completed"},
    {"completion_id": "c5", "person_id": "dana", "institution_id": "north", "status": "in_progress"},
]
JOBS = [
    {"job_id": "j1", "person_id": "ava"},
    {"job_id": "j2", "person_id": "ava"},
    {"job_id": "j3", "person_id": "ben"},
    {"job_id": "j4", "person_id": "cy"},
]
pprint(COMPLETIONS)
pprint(JOBS)
# %% [markdown]
# ## Predict the answer
# Ava has two completed degrees at North and two jobs. Ben has one completed
# degree at North and one job. Cy completed a degree at South. Dana is still
# studying at North. How many **people** qualify at North?
#
# | Relationship | Cardinality | Consequence |
# |---|---|---|
# | Person → Completion | zero or more | One person may have multiple degrees |
# | Completion → Institution | exactly one | Institution is part of membership |
# | Person → Employment | zero or more | A profile join may multiply or omit people |
#
# The ontology below is embedded from the repository's canonical domain file.
# %% [ontology] higher_education.md
# %% [markdown]
# ## A plausible profile query answers the wrong question
# An inner join combines completions and jobs. Even after filtering the institution
# and completion status correctly, counting its rows does not count people.
# This is an authored counterexample, not a captured model mistake.
# %%
def profile_rows(completions, jobs, institution_id):
    return [{"person_id": completion["person_id"], "completion_id": completion["completion_id"],
             "job_id": job["job_id"]}
            for completion in completions
            if completion["institution_id"] == institution_id and completion["status"] == "completed"
            for job in jobs if job["person_id"] == completion["person_id"]]


def count_profile_rows(completions, jobs, institution_id):
    return len(profile_rows(completions, jobs, institution_id))


PROFILE_ROWS = profile_rows(COMPLETIONS, JOBS, "north")
pprint(PROFILE_ROWS)
print(f"Joined profile rows: {len(PROFILE_ROWS)}. People we identified by hand: 2.")
# %% [markdown]
# ## Counterexamples selected from the ontology
# Adding a job cannot create a graduate. Removing job information cannot erase
# one. Adding another degree to an existing graduate cannot create another person.
# These are consequences of identity, relationships and report scope.
# %%
def check_education_rules(candidate):
    extra_degree = {"completion_id": "c6", "person_id": "ava", "institution_id": "north", "status": "completed"}
    conflicting = [COMPLETIONS[0], dict(COMPLETIONS[0], person_id="ben")]
    cases = [
        ("EDU-01", "five joined rows, two people", COMPLETIONS, JOBS, "north", 2),
        ("EDU-01", "another degree, same person", COMPLETIONS + [extra_degree], JOBS, "north", 2),
        ("EDU-02", "other institution", COMPLETIONS, JOBS, "south", 1),
        ("EDU-02", "empty cohort", COMPLETIONS, JOBS, "empty", 0),
        ("EDU-02", "conflicting completion identity", conflicting, JOBS, "north", "ValueError"),
        ("EDU-03", "no employment records", COMPLETIONS, [], "north", 2),
        ("EDU-03", "repeated employment records", COMPLETIONS, JOBS * 2, "north", 2),
    ]
    failures = []
    for rule, case, completions, jobs, institution, expected in cases:
        try:
            actual = candidate(completions, jobs, institution)
        except Exception as exc:
            actual = type(exc).__name__
        if actual != expected:
            failures.append({"rule": rule, "case": case, "expected": expected, "actual": actual})
    return failures


candidate = count_profile_rows  # Replace with your implementation for the exercise.
failures = check_education_rules(candidate)
print(f"Candidate: {len(failures)} rule counterexamples failed")
pprint(failures)
# %% [markdown]
# ## Give your agent the domain before the repair
# Paste the ontology, records and counterexamples into a fresh conversation:
#
# > Implement `count_graduates(completions, institution_id)` for the supplied
# > snapshot. First identify the reporting unit, relationship cardinalities,
# > membership conditions and applicable rule IDs from this ontology.
# > Preserve the domain and expected outcomes. Use only the Python standard library.
# > Explain why adding or removing employment records cannot affect this report.
# > Do not change the question to counting degrees or employed graduates.
#
# Stop here to try it. Adapt the result to the three-argument check interface
# with `lambda completions, jobs, institution: count_graduates(completions, institution)`.
# Run `check_education_rules(your_adapter)` and keep the actual result.
# The next cell is the authored reference, not evidence of an agent run.
# %%
def qualifying_completions(completions, institution_id):
    """EDU-02: validate stable identities, then select the defined cohort."""
    if not isinstance(institution_id, str) or not institution_id.strip():
        raise ValueError("Selected institution_id must be a nonempty string")
    by_id = {}
    fields = ("completion_id", "person_id", "institution_id", "status")
    for row in completions:
        if any(not isinstance(row.get(key), str) or not row[key].strip() for key in fields):
            raise ValueError("Completion identity and status fields must be nonempty strings")
        if row["status"] not in ("completed", "in_progress", "withdrawn"):
            raise ValueError("Unsupported completion status")
        record = {key: row[key] for key in fields}
        previous = by_id.get(row["completion_id"])
        if previous is not None and previous != record:
            raise ValueError("Conflicting records for one completion_id")
        by_id[row["completion_id"]] = record
    return [row for row in by_id.values()
            if row["institution_id"] == institution_id and row["status"] == "completed"]


def count_graduates(completions, institution_id):
    # EDU-01: the person is the reporting unit.
    return len({row["person_id"] for row in qualifying_completions(completions, institution_id)})


def graduate_report(completions, jobs, institution_id):
    # EDU-03: common comparison interface; employment is deliberately irrelevant.
    return count_graduates(completions, institution_id)


print("People with a completed degree at North:", count_graduates(COMPLETIONS, "north"))
reference_failures = check_education_rules(graduate_report)
assert reference_failures == [], reference_failures
print("Reference repair: all graduate-report counterexamples passed")
# %% [markdown]
# ## Change the question, then change the reporting unit
# Now ask: **How many degrees were completed at North?** EDU-04 defines a separate
# completion report. Ava's two degrees legitimately contribute two here.
# We preserve the graduate function and its expectations.
# %%
def count_completions(completions, institution_id):
    # EDU-04: qualifying_completions already resolves identical completion IDs.
    return len(qualifying_completions(completions, institution_id))


print("Profile rows:", len(PROFILE_ROWS))
print("People:", count_graduates(COMPLETIONS, "north"))
print("Completed degrees:", count_completions(COMPLETIONS, "north"))
assert count_graduates(COMPLETIONS, "north") == 2
assert count_completions(COMPLETIONS, "north") == 3
assert count_completions(COMPLETIONS * 2, "north") == 3
print("EDU-04 passed: 2 people and 3 completed degrees answer different questions.")
# %% [markdown]
# ## Explain the ontology-driven part
# **Person → Completion → Institution**, together with the report definition,
# determines the membership filter and distinct-person count. **Person → Employment**
# explains both row multiplication and why an employment join is unnecessary here.
# The ontology chose the implementation and the counterexamples; tests checked them.
#
# - Point to EDU-01 in `count_graduates` and its repeated-degree counterexample.
# - Point to EDU-02 in `qualifying_completions` and its institution/status filter.
# - Point to EDU-03 in `graduate_report` and its no-employment counterexample.
# - Point to EDU-04 in `count_completions` and the separate expected answer of 3.
#
# A test pass establishes only these observed cases within the written scope.
# This notebook does not establish complete coverage, a required CI gate or a
# model-performance improvement.
#
# **Optional agent comparison:** run the same task in two fresh sessions with the
# same model/settings; supply the ontology to only one. Hold the acceptance checks
# fixed for both. Save prompts, implementations, explanations and all outcomes.
# An agent can get the right count without this ontology. The question is whether
# its explanation and behavior follow the intended domain, including counterexamples.
#
# **Take home:** choose one repeated correction from your work. Write its entity,
# relationship, rule, rationale, scope and one counterexample before changing code.
