import pytest
from neo4j.exceptions import TransientError

from landtitle import db


class _Address:
    def __init__(self, host):
        self.host = host


class _ServerInfo:
    def __init__(self, host):
        self.address = _Address(host)


class _Summary:
    def __init__(self, host):
        self.server = _ServerInfo(host)


class _Result:
    def __init__(self, host):
        self._host = host

    def consume(self):
        return _Summary(self._host)


class _Tx:
    """One transaction, pinned to one server, recording what ran on it."""

    def __init__(self, host, fail_delete=False):
        self.host = host
        self.fail_delete = fail_delete
        self.queries: list[str] = []

    def run(self, query, **_):
        self.queries.append(query)
        if self.fail_delete and query.startswith("MATCH"):
            raise TransientError("leader switched")
        return _Result(self.host)


class _Session:
    """Each execute_write attempt gets the next transaction, as a retry on a
    routing driver may land on a different writer."""

    def __init__(self, txs):
        self.txs = list(txs)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute_write(self, fn):
        while True:
            tx = self.txs.pop(0)
            try:
                return fn(tx)
            except TransientError:
                if not self.txs:
                    raise


class _FakeDriver:
    def __init__(self, *txs):
        self.txs = txs

    def session(self, **_):
        return _Session(self.txs)


def deletes_on(tx):
    return [q for q in tx.queries if q.startswith("MATCH (n) DETACH DELETE")]


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_reset_wipes_a_local_database(host):
    tx = _Tx(host)
    db.reset(_FakeDriver(tx))
    assert deletes_on(tx) == ["MATCH (n) DETACH DELETE n"]


@pytest.mark.parametrize("host", ["title.prod.example.com", "10.0.0.12"])
def test_reset_refuses_a_remote_database_whatever_the_env_says(host, monkeypatch):
    monkeypatch.setenv("LANDTITLE_NEO4J_URI", "bolt://localhost:7687")
    tx = _Tx(host)
    with pytest.raises(RuntimeError, match="not a local database"):
        db.reset(_FakeDriver(tx))
    assert deletes_on(tx) == []


def test_reset_rechecks_the_server_when_a_retry_lands_on_a_remote_writer():
    first = _Tx("localhost", fail_delete=True)   # passes the check, then the write fails over
    second = _Tx("title.prod.example.com")        # the retry runs here
    with pytest.raises(RuntimeError, match="not a local database"):
        db.reset(_FakeDriver(first, second))
    assert deletes_on(second) == []
