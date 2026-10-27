// Dev seed. Two operators, three leases, five tracts, four wells, six owners,
// seven title events. Loaded by landtitle.db.load_seed() after a wipe.

CREATE (:Operator {operator_id: 'OP-A', name: 'Brazos Basin Resources'});
CREATE (:Operator {operator_id: 'OP-B', name: 'Caprock Energy'});

CREATE (:Lease {lease_id: 'L-1', name: 'Hartley A', effective: date('2019-03-01')});
CREATE (:Lease {lease_id: 'L-2', name: 'Hartley B', effective: date('2020-07-15')});
CREATE (:Lease {lease_id: 'L-3', name: 'McKenzie', effective: date('2021-01-10')});

CREATE (:Tract {tract_id: 'T-101', acres: 160.0, survey: 'H&TC RR Co. Sec 12'});
CREATE (:Tract {tract_id: 'T-102', acres: 320.0, survey: 'H&TC RR Co. Sec 13'});
CREATE (:Tract {tract_id: 'T-103', acres: 80.0,  survey: 'H&TC RR Co. Sec 14'});
CREATE (:Tract {tract_id: 'T-104', acres: 640.0, survey: 'T&P RR Co. Sec 3'});
CREATE (:Tract {tract_id: 'T-105', acres: 120.0, survey: 'T&P RR Co. Sec 4'});

CREATE (:Well {api_number: '42-123-00001', name: 'Hartley A 1H', spud: date('2019-09-02')});
CREATE (:Well {api_number: '42-123-00002', name: 'Hartley A 2H', spud: date('2020-02-18')});
CREATE (:Well {api_number: '42-123-00003', name: 'Hartley B 1H', spud: date('2021-04-11')});
CREATE (:Well {api_number: '42-123-00004', name: 'McKenzie 1',  spud: date('2021-08-30')});

CREATE (:MineralOwner {owner_id: 'O-1', name: 'Hartley Family Trust'});
CREATE (:MineralOwner {owner_id: 'O-2', name: 'J. Hartley'});
CREATE (:MineralOwner {owner_id: 'O-3', name: 'M. Hartley'});
CREATE (:MineralOwner {owner_id: 'O-4', name: 'Permian Minerals LLC'});
CREATE (:MineralOwner {owner_id: 'O-5', name: 'R. McKenzie'});
CREATE (:MineralOwner {owner_id: 'O-6', name: 'Llano Royalty Partners'});

MATCH (o:Operator {operator_id: 'OP-A'}), (l:Lease) WHERE l.lease_id IN ['L-1', 'L-2'] CREATE (o)-[:OPERATES]->(l);
MATCH (o:Operator {operator_id: 'OP-B'}), (l:Lease {lease_id: 'L-3'}) CREATE (o)-[:OPERATES]->(l);

MATCH (l:Lease {lease_id: 'L-1'}), (t:Tract) WHERE t.tract_id IN ['T-101', 'T-102'] CREATE (l)-[:COVERS]->(t);
MATCH (l:Lease {lease_id: 'L-2'}), (t:Tract) WHERE t.tract_id IN ['T-103', 'T-104'] CREATE (l)-[:COVERS]->(t);
MATCH (l:Lease {lease_id: 'L-3'}), (t:Tract {tract_id: 'T-105'}) CREATE (l)-[:COVERS]->(t);

MATCH (l:Lease {lease_id: 'L-1'}), (w:Well) WHERE w.api_number IN ['42-123-00001', '42-123-00002'] CREATE (l)-[:HAS]->(w);
MATCH (l:Lease {lease_id: 'L-2'}), (w:Well {api_number: '42-123-00003'}) CREATE (l)-[:HAS]->(w);
MATCH (l:Lease {lease_id: 'L-3'}), (w:Well {api_number: '42-123-00004'}) CREATE (l)-[:HAS]->(w);

// Title chain. A TitleEvent CHANGES a Tract; the OWNED_BY edges it produced
// carry its event_id as `since`. Events are recorded in county order.
MATCH (t:Tract {tract_id: 'T-101'}) CREATE (:TitleEvent {event_id: 'TE-001', recorded: date('1998-05-04'), kind: 'patent',     instrument: 'Vol 412 Pg 88'})-[:CHANGES]->(t);
MATCH (t:Tract {tract_id: 'T-102'}) CREATE (:TitleEvent {event_id: 'TE-002', recorded: date('1998-05-04'), kind: 'patent',     instrument: 'Vol 412 Pg 90'})-[:CHANGES]->(t);
MATCH (t:Tract {tract_id: 'T-103'}) CREATE (:TitleEvent {event_id: 'TE-003', recorded: date('2003-11-20'), kind: 'deed',       instrument: 'Vol 601 Pg 14'})-[:CHANGES]->(t);
MATCH (t:Tract {tract_id: 'T-104'}) CREATE (:TitleEvent {event_id: 'TE-004', recorded: date('2003-11-20'), kind: 'deed',       instrument: 'Vol 601 Pg 15'})-[:CHANGES]->(t);
MATCH (t:Tract {tract_id: 'T-105'}) CREATE (:TitleEvent {event_id: 'TE-005', recorded: date('2010-02-01'), kind: 'deed',       instrument: 'Doc 2010-00417'})-[:CHANGES]->(t);
MATCH (t:Tract {tract_id: 'T-102'}) CREATE (:TitleEvent {event_id: 'TE-006', recorded: date('2016-08-12'), kind: 'partition',  instrument: 'Doc 2016-03311'})-[:CHANGES]->(t);
MATCH (t:Tract {tract_id: 'T-104'}) CREATE (:TitleEvent {event_id: 'TE-007', recorded: date('2022-06-30'), kind: 'assignment', instrument: 'Doc 2022-01190'})-[:CHANGES]->(t);

// Current ownership, as of the latest TitleEvent on each tract.
MATCH (t:Tract {tract_id: 'T-101'}), (o:MineralOwner {owner_id: 'O-1'}) CREATE (t)-[:OWNED_BY {interest: 1.0,  since: 'TE-001'}]->(o);
MATCH (t:Tract {tract_id: 'T-102'}), (o:MineralOwner {owner_id: 'O-2'}) CREATE (t)-[:OWNED_BY {interest: 0.5,  since: 'TE-006'}]->(o);
MATCH (t:Tract {tract_id: 'T-102'}), (o:MineralOwner {owner_id: 'O-3'}) CREATE (t)-[:OWNED_BY {interest: 0.5,  since: 'TE-006'}]->(o);
MATCH (t:Tract {tract_id: 'T-103'}), (o:MineralOwner {owner_id: 'O-4'}) CREATE (t)-[:OWNED_BY {interest: 0.75, since: 'TE-003'}]->(o);
MATCH (t:Tract {tract_id: 'T-103'}), (o:MineralOwner {owner_id: 'O-6'}) CREATE (t)-[:OWNED_BY {interest: 0.25, since: 'TE-003'}]->(o);
MATCH (t:Tract {tract_id: 'T-104'}), (o:MineralOwner {owner_id: 'O-4'}) CREATE (t)-[:OWNED_BY {interest: 0.6,  since: 'TE-004'}]->(o);
MATCH (t:Tract {tract_id: 'T-104'}), (o:MineralOwner {owner_id: 'O-6'}) CREATE (t)-[:OWNED_BY {interest: 0.3,  since: 'TE-007'}]->(o);
MATCH (t:Tract {tract_id: 'T-105'}), (o:MineralOwner {owner_id: 'O-5'}) CREATE (t)-[:OWNED_BY {interest: 1.0,  since: 'TE-005'}]->(o);
