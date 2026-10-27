import pytest

from landtitle import db


@pytest.fixture(scope="session")
def graph():
    """A driver against a freshly rebuilt graph: wipe, constraints, seed."""
    driver = db.connect()
    db.reset(driver)
    db.apply_constraints(driver)
    db.load_seed(driver)
    yield driver
    driver.close()
