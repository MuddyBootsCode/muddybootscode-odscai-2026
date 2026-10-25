#!/usr/bin/env python3
"""Query surface for ontology/*.md — what the model runs before and during a task.

Usage:
  ontology_query.py summary
  ontology_query.py [--domain D] entity <Name>
  ontology_query.py [--domain D] term <word>
  ontology_query.py [--domain D] invariants
  ontology_query.py [--domain D] scope
  ontology_query.py [--domain D] section "<Heading>"
  ontology_query.py [--domain D] all

Output is plain text, sized to drop straight into a model's context.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ontology_lib import named_list_counts, load_all, ontology_dir  # noqa: E402


def cmd_summary(onts):
    for o in onts:
        print(f"== {o['title']}  [{o['domain']}]  ({o['path'].name})")
        intent = o["sections"].get("Intent", "").strip()
        if intent:
            print("Intent: " + " ".join(intent.split()))
        print(f"Entities ({len(o['entities'])}): " + ", ".join(o["entities"]) )
        missing = sum(1 for i in o["invariants"] if not i["gate"])
        unconfirmed = sum(1 for i in o["invariants"] if i.get("status") != "confirmed")
        lists = named_list_counts(o)
        print(f"Invariants: {len(o['invariants'])}"
              + (f"  ({missing} without a gate" + (f", {unconfirmed} unconfirmed)" if unconfirmed else ")") if missing
                 else (f"  ({unconfirmed} unconfirmed)" if unconfirmed else "")))
        extra = [f"{h}: {lists[k]}" for h, k in (("Gate backlog", "gate_backlog"), ("Disagreements", "disagreements"), ("Open questions", "open_questions")) if lists[k]]
        if extra:
            print("  ".join(extra))
        scope = o["sections"].get("Out of scope", "").strip()
        if scope:
            lines = [l.strip()[2:] for l in scope.splitlines() if l.strip().startswith("- ")]
            print("Out of scope: " + "; ".join(lines))
        if o["governs"]:
            print("Governs: " + ", ".join(o["governs"]))
        print()
    print("Read the full file for a domain before changing its schema: ontology/<domain>.md")


def cmd_entity(onts, name):
    key = name.lower()
    found = False
    for o in onts:
        for ent, desc in o["entities"].items():
            if ent.lower() == key:
                found = True
                print(f"[{o['domain']}] {ent} — {desc}")
                rels = [r for r in o["relationships"] if key in (r["from"].lower(), r["to"].lower())]
                if rels:
                    print("  Relationships:")
                    for r in rels:
                        print(f"    {r['raw']}")
                invs = [i for i in o["invariants"] if key in i["text"].lower()]
                if invs:
                    print("  Invariants mentioning it:")
                    for i in invs:
                        print(f"    - {i['text']}" + (f"  [gate: {i['gate']}]" if i["gate"] else "  [NO GATE]"))
    if not found:
        print(f"No entity named '{name}'. Known: " + ", ".join(sorted({e for o in onts for e in o['entities']})))
        print("If this is a real concept, it belongs in the ontology before it goes in the code.")
        sys.exit(1)


def cmd_term(onts, word):
    key = word.lower()
    found = False
    for o in onts:
        for term, meaning in o["vocabulary"].items():
            if key == term.lower() or key in term.lower():
                found = True
                print(f"[{o['domain']}] {term} — {meaning}")
    if not found:
        print(f"'{word}' is not defined in the vocabulary. If it has a domain-specific meaning, add it.")
        sys.exit(1)


def cmd_invariants(onts):
    for o in onts:
        print(f"== {o['domain']}")
        for i in o["invariants"]:
            st = i.get("status", "unmarked")
            agree = (f"[confirmed: {i['confirmed_by']}]" if st == "confirmed"
                     else "(inferred)" if st == "inferred" else "[UNCONFIRMED]")
            tag = f"[gate: {i['gate']}]" if i["gate"] else "[MISSING GATE]"
            print(f"- {i['text']}  {agree} {tag}")
        print()


def cmd_section(onts, heading):
    hk = heading.lower()
    for o in onts:
        for h, body in o["sections"].items():
            if h.lower() == hk:
                print(f"== {o['domain']} · {h}")
                print(body)
                print()


def cmd_all(onts):
    for o in onts:
        print(o["path"].read_text(encoding="utf-8"))
        print("\n" + "=" * 72 + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--domain", help="restrict to one ontology file (domain name or file stem)")
    ap.add_argument("command", choices=["summary", "entity", "term", "invariants", "scope", "section", "all"])
    ap.add_argument("arg", nargs="?")
    a = ap.parse_args()

    onts = load_all(domain=a.domain)
    if not onts:
        print(f"No ontology files found in {ontology_dir()}. Run the ontology-driven-dev skill, Phase 1.")
        sys.exit(2)

    if a.command == "summary":
        cmd_summary(onts)
    elif a.command == "entity":
        if not a.arg:
            ap.error("entity needs a name")
        cmd_entity(onts, a.arg)
    elif a.command == "term":
        if not a.arg:
            ap.error("term needs a word")
        cmd_term(onts, a.arg)
    elif a.command == "invariants":
        cmd_invariants(onts)
    elif a.command == "scope":
        cmd_section(onts, "Out of scope")
    elif a.command == "section":
        if not a.arg:
            ap.error("section needs a heading")
        cmd_section(onts, a.arg)
    elif a.command == "all":
        cmd_all(onts)


if __name__ == "__main__":
    main()
