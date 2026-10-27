# land-title

Who owns what, under which lease, and is title clear. A Neo4j graph of
operators, leases, tracts, wells and mineral owners, with the county title
chain recorded as `TitleEvent` nodes.

## Run

```
docker compose up -d
uv sync
uv run pytest
```

Tests rebuild the graph from `cypher/` on every run. `LANDTITLE_NEO4J_URI`,
`LANDTITLE_NEO4J_USER` and `LANDTITLE_NEO4J_PASSWORD` override the defaults
in `docker-compose.yml`. Stop with `docker compose down -v`.
