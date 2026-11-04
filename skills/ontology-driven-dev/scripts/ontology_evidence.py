"""Local evidence for explicitly selected acceptance commands, never domain authority."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess


def state_path(root: Path) -> Path:
    return Path(os.environ.get('ONTOLOGY_STATE', str(root / '.claude/ontology-state.jsonl'))).resolve()


def evidence_dir(root: Path) -> Path:
    return state_path(root).with_suffix('.evidence')


def snapshot(root: Path) -> str:
    """Hash HEAD and tracked/nonignored files; exclude only this checker's runtime output.

    Ignored dependencies and external systems are not covered by this fingerprint.
    """
    from ontology_check import required_git
    head = required_git(root, 'rev-parse', '--verify', 'HEAD').strip()
    paths = required_git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard')
    digest = hashlib.sha256(head.encode())
    runtime = evidence_dir(root)
    state = state_path(root)
    for rel in sorted(set(filter(None, paths.split('\0')))):
        path = root / rel
        absolute = path.absolute()
        if absolute == state or absolute == runtime or runtime in absolute.parents:
            continue
        digest.update(rel.encode() + b'\0')
        if path.is_symlink():
            raise ValueError(f'Cannot fingerprint symlink source: {rel}; use a regular-file checkout.')
        elif path.is_file():
            data = path.read_bytes()
        elif path.is_dir():
            # Submodules need their own explicit acceptance checks.
            raise ValueError(f'Cannot fingerprint directory/submodule: {rel}')
        else:
            data = b'missing'
        digest.update(hashlib.sha256(data).digest())
        if path.exists():
            digest.update(str(path.lstat().st_mode).encode())
    return digest.hexdigest()


def rule_key(domain: str, rule: dict) -> str:
    return hashlib.sha256(json.dumps([domain, rule['text'], rule['gate']], sort_keys=True).encode()).hexdigest()


def statuses(root: Path, onts: list[dict]) -> list[dict]:
    directory = evidence_dir(root)
    records = {}
    invalid = False
    if directory.exists():
        for path in sorted(directory.glob('*.json')):
            try:
                record = json.loads(path.read_text())
                if not isinstance(record, dict) or not all(k in record for k in ('rule_key', 'snapshot', 'status', 'output', 'command', 'exit')):
                    raise ValueError('Invalid evidence record')
                records[record['rule_key']] = record
            except (OSError, ValueError, TypeError):
                invalid = True
    current = snapshot(root) if records else None
    results = []
    for ontology in onts:
        for rule in ontology['invariants']:
            record = records.get(rule_key(ontology['domain'], rule))
            result = {'domain': ontology['domain'], 'rule': rule['text'], 'status': 'not_run'}
            if invalid:
                result['status'] = 'unavailable'
            elif record:
                result.update({k: record[k] for k in ('command', 'exit', 'output')})
                result['status'] = record['status'] if record['snapshot'] == current else 'stale'
                if result['status'] == 'passed':
                    try:
                        log = Path(record['output'])
                        if log.parent.resolve() != directory.resolve() or hashlib.sha256(log.read_bytes()).hexdigest() != record.get('output_sha256'):
                            result['status'] = 'unavailable'
                    except OSError:
                        result['status'] = 'unavailable'
            results.append(result)
    return results
