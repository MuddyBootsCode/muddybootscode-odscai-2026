import pytest
from neo4j.exceptions import ConstraintError


def test_title_event_append_only(graph):
    """A recorded TitleEvent is never rewritten: a second write of its id fails."""
    with pytest.raises(ConstraintError):
        graph.execute_query(
            "MATCH (t:Tract {tract_id: 'T-102'}) "
            "CREATE (:TitleEvent {event_id: 'TE-006', recorded: date('2016-08-12'), kind: 'partition'})-[:CHANGES]->(t)"
        )
