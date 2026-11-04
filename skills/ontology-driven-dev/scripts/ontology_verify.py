#!/usr/bin/env python3
"""Run an explicitly selected acceptance command and retain rule-specific evidence.

ontology_verify.py --rule 'unique rule text' [--domain NAME] [--timeout 300] -- COMMAND ARGS...
Gate annotations are never executed. A successful command only verifies the chosen
check; the reviewer must assess its relevance and retain a failing counterexample.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import time
import uuid

from ontology_lib import find_repo_root, load_all
from ontology_evidence import evidence_dir, rule_key, snapshot
from ontology_check import ComparisonError


def write_record(path, record):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record) + '\n')
    temporary.replace(path)


def interrupted(signum, frame):
    raise KeyboardInterrupt


def main() -> int:
    if os.name == 'posix':
        signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rule', required=True, help='Unique substring of an invariant')
    parser.add_argument('--domain')
    parser.add_argument('--timeout', type=float, default=300)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    root = find_repo_root()
    try:
        matches = [(o, r) for o in load_all(root, args.domain) for r in o['invariants']
                   if args.rule.strip() and args.rule in r['text']]
        if len(matches) != 1:
            raise ValueError('Select exactly one known invariant with --rule and optionally --domain.')
        if not command or args.timeout <= 0:
            raise ValueError('Provide a command after -- and a positive timeout.')
        ontology, rule = matches[0]
        before = snapshot(root)
        directory = evidence_dir(root)
        directory.mkdir(parents=True, exist_ok=True)
        token = f'{time.time_ns():020d}-{uuid.uuid4().hex}'
        output = directory / (token + '.log')
        record_path = directory / (token + '.json')
        record = {'rule_key': rule_key(ontology['domain'], rule), 'rule': rule['text'],
                  'domain': ontology['domain'], 'snapshot': before, 'status': 'interrupted',
                  'command': command, 'exit': None, 'output': str(output), 'cwd': str(root)}
        # Invalidate an older success before starting, including when this process is killed.
        write_record(record_path, record)
        error = ''
        with output.open('w') as stream:
            try:
                process = subprocess.Popen(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT,
                                           start_new_session=os.name == 'posix')
                try:
                    exit_code = process.wait(timeout=args.timeout)
                finally:
                    # A test runner can spawn workers; stop the entire command group,
                    # including descendants left behind after the parent exits.
                    if os.name == 'posix':
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    elif process.poll() is None:
                        process.kill()
                    process.wait()
                record['exit'] = exit_code
                record['status'] = 'passed' if exit_code == 0 else 'failed'
            except (OSError, subprocess.TimeoutExpired) as exc:
                error = str(exc)
                stream.write(error + '\n')
                record['status'] = 'unavailable'
        try:
            if snapshot(root) != before:
                record['status'] = 'stale'
                error = 'Repository changed during verification; rerun on the final source.'
        except (OSError, ValueError, ComparisonError) as exc:
            record['status'] = 'unavailable'
            error = str(exc)
        record['output_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
        write_record(record_path, record)
        print(json.dumps(record))
        if error:
            print(error, file=sys.stderr)
        return 0 if record['status'] == 'passed' else 1
    except (OSError, ValueError, ComparisonError) as exc:
        print(f'Verification unavailable: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
