import pytest

from landtitle import db


class _FakeDriver:
    """Looks like a neo4j Driver to reset(): reports a host, records queries."""

    def __init__(self, host: str):
        self.host = host
        self.queries: list[str] = []

    def get_server_info(self):
        class _Address:
            host = self.host

        class _Info:
            address = _Address()

        return _Info()

    def execute_query(self, query, **_):
        self.queries.append(query)


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_reset_wipes_a_local_database(host):
    driver = _FakeDriver(host)
    db.reset(driver)
    assert driver.queries == ["MATCH (n) DETACH DELETE n"]


@pytest.mark.parametrize("host", ["title.prod.example.com", "10.0.0.12"])
def test_reset_refuses_a_remote_database_whatever_the_env_says(host, monkeypatch):
    monkeypatch.setenv("LANDTITLE_NEO4J_URI", "bolt://localhost:7687")
    driver = _FakeDriver(host)
    with pytest.raises(RuntimeError, match="not a local database"):
        db.reset(driver)
    assert driver.queries == []
