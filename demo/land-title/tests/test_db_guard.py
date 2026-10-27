import pytest

from landtitle import db


class _Address:
    def __init__(self, host):
        self.host = host


class _Info:
    def __init__(self, host):
        self.address = _Address(host)


class _Summary:
    def __init__(self, host):
        self.server = _Info(host)


class _Result:
    def __init__(self, host):
        self.summary = _Summary(host)


class _FakeDriver:
    """Looks like a neo4j Driver to reset(): a reader host, a writer host, and a
    record of every query. A routing driver can have different ones."""

    def __init__(self, reader: str, writer: str | None = None):
        self.reader = reader
        self.writer = writer or reader
        self.queries: list[str] = []

    def get_server_info(self):
        return _Info(self.reader)

    def execute_query(self, query, **_):
        self.queries.append(query)
        return _Result(self.writer)


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_reset_wipes_a_local_database(host):
    driver = _FakeDriver(host)
    db.reset(driver)
    assert driver.queries[-1] == "MATCH (n) DETACH DELETE n"


@pytest.mark.parametrize("host", ["title.prod.example.com", "10.0.0.12"])
def test_reset_refuses_a_remote_database_whatever_the_env_says(host, monkeypatch):
    monkeypatch.setenv("LANDTITLE_NEO4J_URI", "bolt://localhost:7687")
    driver = _FakeDriver(host)
    with pytest.raises(RuntimeError, match="not a local database"):
        db.reset(driver)
    assert "MATCH (n) DETACH DELETE n" not in driver.queries


def test_reset_refuses_when_writes_route_to_a_remote_host():
    driver = _FakeDriver(reader="localhost", writer="title.prod.example.com")
    with pytest.raises(RuntimeError, match="not a local database"):
        db.reset(driver)
    assert "MATCH (n) DETACH DELETE n" not in driver.queries
