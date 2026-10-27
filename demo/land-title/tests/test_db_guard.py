import pytest

from landtitle import db


@pytest.mark.parametrize("uri", ["bolt://localhost:7687", "bolt://127.0.0.1:7687", "neo4j://localhost:7688"])
def test_local_databases_are_disposable(uri):
    assert db.is_disposable(uri)


@pytest.mark.parametrize("uri", ["neo4j+s://title.prod.example.com", "bolt://10.0.0.12:7687"])
def test_remote_databases_are_not_disposable(uri):
    assert not db.is_disposable(uri)
