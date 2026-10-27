"""Connection and graph (re)build. The graph is derived from cypher/ on demand."""
from __future__ import annotations

import os
from pathlib import Path

from neo4j import Driver, GraphDatabase

CYPHER_DIR = Path(__file__).resolve().parent.parent / "cypher"


def connect() -> Driver:
    uri = os.environ.get("LANDTITLE_NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("LANDTITLE_NEO4J_USER", "neo4j")
    password = os.environ.get("LANDTITLE_NEO4J_PASSWORD", "landtitle")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    return driver


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def reset(driver: Driver) -> None:
    """Delete every node. Only for the local dev graph, which cypher/ rebuilds.

    The check and the delete run in one write transaction: the probe reports
    the server executing that transaction, so a routing driver whose writer is
    remote, or that fails over to one on a retry, is refused before deleting.
    """

    def wipe(tx) -> None:
        host = tx.run("RETURN 1").consume().server.address.host
        if host not in LOCAL_HOSTS:
            raise RuntimeError(f"refusing to wipe {host}: not a local database")
        tx.run("MATCH (n) DETACH DELETE n").consume()

    with driver.session() as session:
        session.execute_write(wipe)


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
