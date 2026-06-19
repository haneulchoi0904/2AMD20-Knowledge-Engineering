# cycling-kg-neo4j-import

Cleaned data and Neo4j import instructions for the **Eindhoven cycling-infrastructure knowledge graph** (2AMD20 Knowledge Engineering, Group 15).

This repository hosts the cleaned CSV files and the Cypher import script needed to rebuild the Neo4j knowledge graph from scratch. The knowledge graph links cycling accidents, accident severity, bike-lane segments, and formal bike-parking facilities to Eindhoven neighbourhoods, supporting a neighbourhood-level priority ranking for cycling-infrastructure improvement.

The live database is not shared (a cloud Neo4j AuraDB instance needs credentials and does not stay available over time). Instead, the reproducible artefacts are the cleaned CSV files in this repository plus the `LOAD CSV` import script below. Anyone can rebuild an identical graph by following the steps here.

---

## Repository contents

| File | Description |
|---|---|
| `neighbourhood_summary.csv` | One row per Eindhoven neighbourhood (111). Source for `Neighbourhood` nodes. |
| `accident_neighbourhood_join.csv` | One row per cycling accident (1653; 1621 matched to a neighbourhood). Source for `CyclingAccident` nodes and `OCCURRED_IN`. |
| `parking_neighbourhood_join.csv` | One row per formal bike-parking facility (7). Source for `BikeParkingFacility` nodes and `LOCATED_IN`. |
| `lane_neighbourhood_join.csv` | One row per bike-lane / neighbourhood intersection (5467 rows; 4627 unique segments). Source for `BikeLaneSegment` nodes and `PASSES_THROUGH`. |
| `README.md` | This file. |

**Note:** in `neighbourhood_summary.csv`, only the first columns (`BUURTCODE`, `BUURTNAAM`, `WIJKNAAM`, `STADSDEELNAAM`, `population`, `area_km2`, `OAD`, `pop_density`) become node properties. The remaining columns (`accident_count`, `lane_length_m`, `parking_count`, …) are pre-computed validation summaries, not node properties.

---

## Graph model

- **Nodes:** `Neighbourhood`, `CyclingAccident`, `AccidentSeverity`, `BikeLaneSegment`, `BikeParkingFacility`
- **Relationships:**
  - `(:CyclingAccident)-[:OCCURRED_IN]->(:Neighbourhood)`
  - `(:CyclingAccident)-[:HAS_SEVERITY]->(:AccidentSeverity)`
  - `(:BikeLaneSegment)-[:PASSES_THROUGH {intersected_length_m}]->(:Neighbourhood)`
  - `(:BikeParkingFacility)-[:LOCATED_IN]->(:Neighbourhood)`

`intersected_length_m` is stored on the `PASSES_THROUGH` relationship (not on the node) because one bike-lane segment may cross several neighbourhoods. Formal bike parking is included as contextual information only and is **not** part of the final priority score.

---

## How to rebuild the graph in Neo4j

Works with Neo4j 5 / Neo4j AuraDB. The CSV files are read directly from this public repository via their raw URLs, so no local download is needed.

Run the blocks below **once, in order, on an empty database** (in Neo4j Browser or cypher-shell). `PASSES_THROUGH` is created with `CREATE`, so re-running on a non-empty database would duplicate edges — clear the database first (Step 0) if you re-import.

### 0. (Optional) Clear the database before a fresh import

```cypher
MATCH (n) DETACH DELETE n;
```

### 1. Create constraints

```cypher
CREATE CONSTRAINT neighbourhood_code_unique IF NOT EXISTS
FOR (n:Neighbourhood) REQUIRE n.BUURTCODE IS UNIQUE;

CREATE CONSTRAINT accident_id_unique IF NOT EXISTS
FOR (a:CyclingAccident) REQUIRE a.accident_id IS UNIQUE;

CREATE CONSTRAINT bike_parking_id_unique IF NOT EXISTS
FOR (p:BikeParkingFacility) REQUIRE p.facility_id IS UNIQUE;

CREATE CONSTRAINT bike_lane_id_unique IF NOT EXISTS
FOR (l:BikeLaneSegment) REQUIRE l.id IS UNIQUE;

CREATE CONSTRAINT accident_severity_unique IF NOT EXISTS
FOR (s:AccidentSeverity) REQUIRE s.name IS UNIQUE;
```

### 2. Neighbourhood nodes

```cypher
LOAD CSV WITH HEADERS FROM "https://raw.githubusercontent.com/itsjoecsh/cycling-kg-neo4j-import/main/neighbourhood_summary.csv" AS row
MERGE (n:Neighbourhood {BUURTCODE: row.BUURTCODE})
SET n.BUURTNAAM     = row.BUURTNAAM,
    n.WIJKNAAM      = row.WIJKNAAM,
    n.STADSDEELNAAM = row.STADSDEELNAAM,
    n.population    = CASE WHEN row.population  IS NULL OR trim(row.population)  = "" THEN null ELSE toInteger(toFloat(row.population)) END,
    n.area_km2      = CASE WHEN row.area_km2    IS NULL OR trim(row.area_km2)    = "" THEN null ELSE toFloat(row.area_km2)   END,
    n.OAD           = CASE WHEN row.OAD         IS NULL OR trim(row.OAD)         = "" THEN null ELSE toFloat(row.OAD)        END,
    n.pop_density   = CASE WHEN row.pop_density IS NULL OR trim(row.pop_density) = "" THEN null ELSE toFloat(row.pop_density) END;
```

### 3. CyclingAccident nodes + OCCURRED_IN

Rows with an empty `BUURTCODE` (unmatched accidents) are skipped, leaving 1621 accident nodes and 1621 `OCCURRED_IN` edges.

```cypher
LOAD CSV WITH HEADERS FROM "https://raw.githubusercontent.com/itsjoecsh/cycling-kg-neo4j-import/main/accident_neighbourhood_join.csv" AS row
WITH row
WHERE row.BUURTCODE IS NOT NULL AND trim(row.BUURTCODE) <> ""
MERGE (a:CyclingAccident {accident_id: row.accident_id})
SET a.accident_year                 = CASE WHEN row.accident_year IS NULL OR trim(row.accident_year) = "" THEN null ELSE toInteger(row.accident_year) END,
    a.accident_outcome_standardized = row.accident_outcome_standardized,
    a.accident_nature               = row.accident_nature,
    a.road_situation                = row.road_situation,
    a.speed_limit                   = CASE WHEN row.speed_limit IS NULL OR trim(row.speed_limit) = "" THEN null ELSE toInteger(toFloat(row.speed_limit)) END,
    a.street_name                   = row.street_name,
    a.longitude                     = CASE WHEN row.longitude IS NULL OR trim(row.longitude) = "" THEN null ELSE toFloat(row.longitude) END,
    a.latitude                      = CASE WHEN row.latitude  IS NULL OR trim(row.latitude)  = "" THEN null ELSE toFloat(row.latitude)  END
WITH a, row
MATCH (n:Neighbourhood {BUURTCODE: row.BUURTCODE})
MERGE (a)-[:OCCURRED_IN]->(n);
```

### 4. BikeParkingFacility nodes + LOCATED_IN

Empty `capacity` (pop-up facilities) is kept as `null`, not 0, to preserve the distinction between "zero capacity" and "unknown capacity".

```cypher
LOAD CSV WITH HEADERS FROM "https://raw.githubusercontent.com/itsjoecsh/cycling-kg-neo4j-import/main/parking_neighbourhood_join.csv" AS row
WITH row
WHERE row.facility_id IS NOT NULL AND trim(row.facility_id) <> ""
MERGE (p:BikeParkingFacility {facility_id: row.facility_id})
SET p.name     = row.name,
    p.address  = row.address,
    p.type     = row.type,
    p.capacity = CASE WHEN row.capacity IS NULL OR trim(row.capacity) = "" THEN null ELSE toInteger(toFloat(row.capacity)) END,
    p.lon      = CASE WHEN row.lon IS NULL OR trim(row.lon) = "" THEN null ELSE toFloat(row.lon) END,
    p.lat      = CASE WHEN row.lat IS NULL OR trim(row.lat) = "" THEN null ELSE toFloat(row.lat) END
WITH p, row
WHERE row.BUURTCODE IS NOT NULL AND trim(row.BUURTCODE) <> ""
MATCH (n:Neighbourhood {BUURTCODE: row.BUURTCODE})
MERGE (p)-[:LOCATED_IN]->(n);
```

### 5. BikeLaneSegment nodes + PASSES_THROUGH

The node is `MERGE`d on `id` (→ 4627 unique nodes); each row creates one `PASSES_THROUGH` edge carrying `intersected_length_m` (→ 5467 edges). Columns containing a colon are wrapped in backticks.

```cypher
LOAD CSV WITH HEADERS FROM "https://raw.githubusercontent.com/itsjoecsh/cycling-kg-neo4j-import/main/lane_neighbourhood_join.csv" AS row
WITH row
WHERE row.id IS NOT NULL AND trim(row.id) <> ""
MERGE (l:BikeLaneSegment {id: row.id})
SET l.element          = row.element,
    l.name             = row.name,
    l.highway          = row.highway,
    l.bicycle          = row.bicycle,
    l.cycleway         = row.cycleway,
    l.`cycleway:left`  = row.`cycleway:left`,
    l.`cycleway:right` = row.`cycleway:right`,
    l.`cycleway:both`  = row.`cycleway:both`,
    l.cyclestreet      = row.cyclestreet,
    l.oneway           = row.oneway,
    l.`oneway:bicycle` = row.`oneway:bicycle`,
    l.foot             = row.foot,
    l.segregated       = row.segregated,
    l.surface          = row.surface,
    l.lit              = row.lit,
    l.maxspeed         = row.maxspeed,
    l.source_query     = row.source_query
WITH l, row
WHERE row.BUURTCODE IS NOT NULL AND trim(row.BUURTCODE) <> ""
MATCH (n:Neighbourhood {BUURTCODE: row.BUURTCODE})
CREATE (l)-[:PASSES_THROUGH {
    intersected_length_m: CASE WHEN row.intersected_length_m IS NULL OR trim(row.intersected_length_m) = "" THEN 0.0 ELSE toFloat(row.intersected_length_m) END
}]->(n);
```

### 6. AccidentSeverity nodes + HAS_SEVERITY

```cypher
MATCH (a:CyclingAccident)
WHERE a.accident_outcome_standardized IS NOT NULL
  AND trim(a.accident_outcome_standardized) <> ""
MERGE (s:AccidentSeverity {name: a.accident_outcome_standardized})
MERGE (a)-[:HAS_SEVERITY]->(s);
```

Optional Dutch labels:

```cypher
MATCH (s:AccidentSeverity {name: "injury"})
SET s.alternative_name_nl = "Letsel", s.description = "Accident involving injury";
MATCH (s:AccidentSeverity {name: "fatal"})
SET s.alternative_name_nl = "Dodelijk", s.description = "Fatal accident";
MATCH (s:AccidentSeverity {name: "property_damage_only"})
SET s.alternative_name_nl = "UMS / Materieel", s.description = "Property-damage-only accident";
```

---

## Verify the import

```cypher
MATCH (n) RETURN labels(n) AS node_type, count(n) AS count ORDER BY node_type;
```

Expected:

```text
AccidentSeverity: 3
BikeLaneSegment: 4627
BikeParkingFacility: 7
CyclingAccident: 1621
Neighbourhood: 111
```

```cypher
MATCH ()-[r]->() RETURN type(r) AS relationship_type, count(r) AS count ORDER BY relationship_type;
```

Expected:

```text
HAS_SEVERITY: 1621
LOCATED_IN: 7
OCCURRED_IN: 1621
PASSES_THROUGH: 5467
```

---

## Troubleshooting

- **`LOAD CSV` cannot read the file** — the URL must be a **raw** URL (`raw.githubusercontent.com/...`), not a normal GitHub page (`github.com/.../blob/...`). This repository is public, so no token is needed.
- **`PASSES_THROUGH` count is 4627 instead of 5467** — the relationship was created with `MERGE` instead of `CREATE`; use `CREATE` as in Step 5.
- **Numeric conversion error on `population`** — values are written as float strings (e.g. `3773.0`), so use `toInteger(toFloat(...))`, not `toInteger(...)`.
- **Colon columns** — `cycleway:left`, `cycleway:right`, `cycleway:both`, `oneway:bicycle` must be written with backticks, e.g. `` row.`cycleway:left` ``.

---

## Data sources

The cleaned files in this repository are derived from public/open data: cycling accident records (BRON, via the European Data Portal), Eindhoven neighbourhood boundaries (Gemeente Eindhoven Open Data) and population statistics (Onderzoek040), and bike-lane geometries from OpenStreetMap (© OpenStreetMap contributors, ODbL). The data is reused here for an academic course project; original licensing and attribution remain with the respective providers.
