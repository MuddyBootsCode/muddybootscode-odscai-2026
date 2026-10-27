"""Connection and graph (re)build. The graph is derived from cypher/ on demand."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

from neo4j import Driver, GraphDatabase

CYPHER_DIR = Path(__file__).resolve().parent.parent / "cypher"


def connect() -> Driver:
    uri = os.environ.get("LANDTITLE_NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("LANDTITLE_NEO4J_USER", "neo4j")
    password = os.environ.get("LANDTITLE_NEO4J_PASSWORD", "landtitle")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    return driver


def is_disposable(uri: str) -> bool:
    """True only for a database on this machine. reset() refuses anything else."""
    return urlsplit(uri).hostname in {"localhost", "127.0.0.1", "::1"}


def reset(driver: Driver) -> None:
    """Delete every node. Only for the local dev graph, which cypher/ rebuilds."""
    uri = os.environ.get("LANDTITLE_NEO4J_URI", "bolt://localhost:7687")
    if not is_disposable(uri):
        raise RuntimeError(f"refusing to wipe {uri}: not a local database")
    driver.execute_query("MATCH (n) DETACH DELETE n")


def apply_constraints(driver: Driver) -> None:
    _run_file(driver, CYPHER_DIR / "constraints.cypher")


def load_seed(driver: Driver) -> None:
    _run_file(driver, CYPHER_DIR / "seed.cypher")


def _run_file(driver: Driver, path: Path) -> None:
    """Run each `;`-terminated statement in the file, skipping // comments."""
    body = "\n".join(
        line for line in path.read_text().splitlines() if not line.lstrip().startswith("//")
    )
    for statement in body.split(";"):
        if statement.strip():
            driver.execute_query(statement)
