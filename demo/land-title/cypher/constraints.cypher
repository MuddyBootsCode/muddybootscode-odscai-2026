// Node keys. One per entity. Applied by landtitle.db.apply_constraints().
CREATE CONSTRAINT operator_id IF NOT EXISTS FOR (n:Operator) REQUIRE n.operator_id IS UNIQUE;
CREATE CONSTRAINT lease_id IF NOT EXISTS FOR (n:Lease) REQUIRE n.lease_id IS UNIQUE;
CREATE CONSTRAINT tract_id IF NOT EXISTS FOR (n:Tract) REQUIRE n.tract_id IS UNIQUE;
CREATE CONSTRAINT well_api_number IF NOT EXISTS FOR (n:Well) REQUIRE n.api_number IS UNIQUE;
CREATE CONSTRAINT owner_id IF NOT EXISTS FOR (n:MineralOwner) REQUIRE n.owner_id IS UNIQUE;
CREATE CONSTRAINT title_event_id IF NOT EXISTS FOR (n:TitleEvent) REQUIRE n.event_id IS UNIQUE;
