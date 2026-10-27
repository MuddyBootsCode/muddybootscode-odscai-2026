from landtitle import queries
from landtitle.model import Ownership, TitleEvent, Well


def test_owner_of_returns_current_interests_by_owner(graph):
    ownership = queries.owner_of(graph, "T-102")
    assert isinstance(ownership, Ownership)
    assert ownership.owners == {"O-2": 0.5, "O-3": 0.5}


def test_owner_of_reports_the_latest_title_event(graph):
    assert queries.owner_of(graph, "T-102").as_of == "TE-006"


def test_owner_of_unknown_tract_is_none(graph):
    assert queries.owner_of(graph, "T-999") is None


def test_wells_under_lease_in_api_order(graph):
    wells = queries.wells_under(graph, "L-1")
    assert all(isinstance(w, Well) for w in wells)
    assert [w.api_number for w in wells] == ["42-123-00001", "42-123-00002"]


def test_well_carries_name_and_spud_date(graph):
    first = queries.wells_under(graph, "L-1")[0]
    assert (first.name, first.spud.isoformat()) == ("Hartley A 1H", "2019-09-02")


def test_title_chain_is_ordered_by_recording_date(graph):
    chain = queries.title_chain(graph, "T-102")
    assert all(isinstance(e, TitleEvent) for e in chain)
    assert [e.event_id for e in chain] == ["TE-002", "TE-006"]


def test_owner_of_sums_several_interests_held_by_one_owner(graph):
    """Two OWNED_BY edges from one tract to one owner are one holding, added up."""
    graph.execute_query(
        "MATCH (t:Tract {tract_id: 'T-105'}), (o:MineralOwner {owner_id: 'O-5'}) "
        "CREATE (t)-[:OWNED_BY {interest: 0.25, since: 'TE-005', test_extra: true}]->(o)"
    )
    try:
        assert queries.owner_of(graph, "T-105").owners == {"O-5": 1.25}
    finally:
        graph.execute_query("MATCH ()-[r:OWNED_BY {test_extra: true}]->() DELETE r")
