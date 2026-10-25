"""Shared parsing for ontology/*.md files. Stdlib only.

An ontology file is markdown with optional YAML-ish front matter and a fixed
set of H2 sections. This module turns one into a dict without pulling in a
YAML or markdown dependency, so the hooks run anywhere Python 3 runs.
"""
from __future__ import annotations

import fnmatch
import os
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    "Intent",
    "Entities",
    "Relationships",
    "Invariants",
    "Vocabulary",
    "Out of scope",
]
OPTIONAL_SECTIONS = ["Absence and silence", "Changelog", "Gate backlog", "Disagreements", "Open questions"]
# D8: the three lists the validator reads, keyed as the state record names them.
NAMED_LISTS = {"Gate backlog": "gate_backlog", "Disagreements": "disagreements", "Open questions": "open_questions"}

ENTITY_RE = re.compile(r"^-\s+\*\*(?P<name>[^*]+)\*\*\s*[—-]\s*(?P<desc>.*)$")
REL_RE = re.compile(
    r"\(\s*(?P<from>[A-Za-z0-9_]+)\s*\)\s*-\[\s*(?P<verb>[A-Z0-9_]+)\s*\]->\s*\(\s*(?P<to>[A-Za-z0-9_]+)\s*\)"
)
GATE_RE = re.compile(r"\[gate:\s*(?P<gate>[^\]]+)\]")
CONFIRMED_RE = re.compile(r"\[confirmed:\s*(?P<by>[^\]]+)\]")
INFERRED_RE = re.compile(r"\(inferred\)")
TERM_RE = re.compile(r"^-\s+\*\*(?P<term>[^*]+)\*\*\s*[—-]\s*(?P<meaning>.*)$")


def find_repo_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    for candidate in [p, *p.parents]:
        if (candidate / "ontology").is_dir() or (candidate / ".git").exists():
            return candidate
    return p


def ontology_dir(root: Path | None = None) -> Path:
    return find_repo_root(root) / "ontology"


def list_ontology_files(root: Path | None = None) -> list[Path]:
    d = ontology_dir(root)
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.md") if p.name.lower() != "readme.md")


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Minimal front matter: `key: value` and `key:\n  - item` lists."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip("\n")
    body = text[end + 4 :]
    meta: dict = {}
    current_list_key = None
    for raw in block.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue  # a comment, even one with a colon, is not a key and does not end a list
        if line.lstrip().startswith("- ") and current_list_key:
            meta.setdefault(current_list_key, []).append(line.lstrip()[2:].strip().strip('"').strip("'"))
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "":
                current_list_key = key
                meta[key] = []
            else:
                current_list_key = None
                meta[key] = val.strip('"').strip("'")
    return meta, body


def split_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def parse_ontology(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(text)
    sections = split_sections(body)
    title_m = re.search(r"^#\s+(.+?)\s*$", body, re.M)

    entities = {}
    for line in sections.get("Entities", "").splitlines():
        m = ENTITY_RE.match(line.strip())
        if m:
            entities[m.group("name").strip()] = m.group("desc").strip()

    relationships = []
    for line in sections.get("Relationships", "").splitlines():
        if not line.strip().startswith("- "):
            continue  # prose lines in the section are guidance, not edges
        for m in REL_RE.finditer(line):
            relationships.append(
                {"from": m.group("from"), "verb": m.group("verb"), "to": m.group("to"), "raw": line.strip()}
            )

    invariants = []
    for line in sections.get("Invariants", "").splitlines():
        s = line.strip()
        if not s.startswith("- "):
            continue
        g = GATE_RE.search(s)
        c = CONFIRMED_RE.search(s)
        # Two statuses, kept apart: domain agreement (confirmed / inferred / unmarked) and
        # enforcement coverage (gate or none). D7.
        status = "confirmed" if c else "inferred" if INFERRED_RE.search(s) else "unmarked"
        text = INFERRED_RE.sub("", CONFIRMED_RE.sub("", GATE_RE.sub("", s[2:]))).strip()
        invariants.append({
            "text": re.sub(r"\s{2,}", " ", text),
            "gate": g.group("gate").strip() if g else None,
            "status": status,
            "confirmed_by": c.group("by").strip() if c else None,
        })

    vocabulary = {}
    for line in sections.get("Vocabulary", "").splitlines():
        m = TERM_RE.match(line.strip())
        if m:
            vocabulary[m.group("term").strip()] = m.group("meaning").strip()

    # front matter `declarations:` — "- \"Entity: CodeName, CodeName\"" → {CodeName: Entity}
    declarations: dict[str, str] = {}
    for item in meta.get("declarations", []) if isinstance(meta.get("declarations"), list) else []:
        entity, _, names = item.partition(":")
        for n in names.split(","):
            if n.strip():
                declarations[n.strip()] = entity.strip()
    # front matter `parity:` — "- \"path/a <-> path/b\"" → [(a, b)]
    parity: list[tuple[str, str]] = []
    for item in meta.get("parity", []) if isinstance(meta.get("parity"), list) else []:
        a, sep, b = item.partition("<->")
        if sep and a.strip() and b.strip():
            parity.append((a.strip(), b.strip()))

    return {
        "path": path,
        "domain": meta.get("domain") or path.stem,
        "declarations": declarations,
        "parity": parity,
        "title": title_m.group(1) if title_m else path.stem,
        "meta": meta,
        "governs": meta.get("governs", []) if isinstance(meta.get("governs"), list) else [],
        "sections": sections,
        "entities": entities,
        "relationships": relationships,
        "invariants": invariants,
        "vocabulary": vocabulary,
    }


def load_all(root: Path | None = None, domain: str | None = None) -> list[dict]:
    out = []
    for p in list_ontology_files(root):
        o = parse_ontology(p)
        if domain and o["domain"] != domain and p.stem != domain:
            continue
        out.append(o)
    return out


def path_governed_by(rel_path: str, ontologies: list[dict]) -> list[tuple[dict, str]]:
    """Return (ontology, glob) pairs whose governs list matches rel_path."""
    hits = []
    norm = rel_path.replace(os.sep, "/")
    for o in ontologies:
        for g in o["governs"]:
            if _glob_match(norm, g):
                hits.append((o, g))
    return hits


def _glob_match(path: str, pattern: str) -> bool:
    # fnmatch doesn't treat ** specially; emulate: "a/**" matches a/ and anything under it.
    if pattern.endswith("/**"):
        base = pattern[:-3]
        return path == base or path.startswith(base + "/")
    if "**/" in pattern:
        head, _, tail = pattern.partition("**/")
        if not path.startswith(head):
            return False
        rest = path[len(head):]
        return any(fnmatch.fnmatch(rest[i:], tail) for i in range(len(rest) + 1) if i == 0 or rest[i - 1] == "/")
    return fnmatch.fnmatch(path, pattern)


def eprint(*a, **k):
    print(*a, file=sys.stderr, **k)


def invariant_counts(onts: list[dict]) -> dict[str, int]:
    """The four numbers of D7: agreement x coverage. 'unconfirmed' is inferred or unmarked."""
    c = {"confirmed_gated": 0, "confirmed_ungated": 0, "unconfirmed_gated": 0, "unconfirmed_ungated": 0}
    for o in onts:
        for i in o["invariants"]:
            a = "confirmed" if i.get("status") == "confirmed" else "unconfirmed"
            c[f"{a}_{'gated' if i['gate'] else 'ungated'}"] += 1
    return c


def section_items(o: dict, heading: str) -> list[str]:
    """The `- ` bullets of one section, text only."""
    body = o["sections"].get(heading, "")
    return [l.strip()[2:].strip() for l in body.splitlines() if l.strip().startswith("- ")]


def named_list_counts(o: dict) -> dict[str, int]:
    return {key: len(section_items(o, heading)) for heading, key in NAMED_LISTS.items()}


def invariants_naming(onts: list[dict], entity: str) -> list[str]:
    """D9: the invariant sentences that name an entity (whole word, case-insensitive)."""
    pat = re.compile(rf"\b{re.escape(entity)}\b", re.I)
    return [i["text"] for o in onts for i in o["invariants"] if pat.search(i["text"])]
