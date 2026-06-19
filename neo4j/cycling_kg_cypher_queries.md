# Cycling Infrastructure KG — Cypher Query Archive

Neo4j AuraDB query reference for the Eindhoven cycling-infrastructure knowledge graph.
Covers connection tests, import validation, the `AccidentSeverity` schema update,
research-question queries, the SQL/Cypher fan-trap comparison, visualisation helpers,
display-name setup, and cleanup.

---

## Contents

- **Setup & validation** — §00–§03
- **AccidentSeverity schema update** — §04–§11
- **Research-question queries** — §12–§17
- **SQL vs Cypher comparison** — §18
- **Visualisation / example graphs** — §19–§21
- **Display names** — §22–§26
- **Cleanup** — §27

---

# Setup & validation

## 00 · Test connection

```cypher
RETURN "AuraDB is connected" AS message;
```

## 01 · Validate node counts

```cypher
MATCH (n)
RETURN labels(n) AS node_type,
       count(n) AS count
ORDER BY node_type;
```

Expected after import:

```text
BikeLaneSegment:     4627
BikeParkingFacility:    7
CyclingAccident:     1621
Neighbourhood:        111
```

## 02 · Validate relationship counts

```cypher
MATCH ()-[r]->()
RETURN type(r) AS relationship_type,
       count(r) AS count
ORDER BY relationship_type;
```

Expected before adding severity:

```text
LOCATED_IN:        7
OCCURRED_IN:    1621
PASSES_THROUGH: 5467
```

After adding `HAS_SEVERITY`:

```text
HAS_SEVERITY:   1621
```

## 03 · Validate total lane length

```cypher
MATCH (:BikeLaneSegment)-[r:PASSES_THROUGH]->(:Neighbourhood)
RETURN round(sum(r.intersected_length_m), 2) AS total_lane_length_m;
```

Expected: approximately `483302.48` m.

---

# AccidentSeverity schema update

## 04 · Check original severity property values

```cypher
MATCH (a:CyclingAccident)
RETURN a.accident_outcome_standardized AS severity_value,
       count(a) AS accident_count
ORDER BY accident_count DESC;
```

Expected:

```text
property_damage_only: 1276
injury:                341
fatal:                   4
```

## 05 · Create AccidentSeverity uniqueness constraint

```cypher
CREATE CONSTRAINT accident_severity_unique IF NOT EXISTS
FOR (s:AccidentSeverity)
REQUIRE s.name IS UNIQUE;
```

## 06 · Create AccidentSeverity nodes and HAS_SEVERITY relationships

```cypher
MATCH (a:CyclingAccident)
WHERE a.accident_outcome_standardized IS NOT NULL
  AND trim(a.accident_outcome_standardized) <> ""
MERGE (s:AccidentSeverity {name: a.accident_outcome_standardized})
MERGE (a)-[:HAS_SEVERITY]->(s);
```

## 07 · Validate AccidentSeverity distribution

```cypher
MATCH (s:AccidentSeverity)
RETURN s.name AS severity,
       count {
         (a:CyclingAccident)-[:HAS_SEVERITY]->(s)
       } AS accident_count
ORDER BY accident_count DESC;
```

## 08 · Validate HAS_SEVERITY relationship count

```cypher
MATCH (:CyclingAccident)-[r:HAS_SEVERITY]->(:AccidentSeverity)
RETURN count(r) AS has_severity_relationships;
```

Expected: `1621`.

## 09 · Validate accidents without severity

```cypher
MATCH (a:CyclingAccident)
WHERE NOT (a)-[:HAS_SEVERITY]->(:AccidentSeverity)
RETURN count(a) AS accidents_without_severity;
```

Expected: `0`.

## 10 · Remove orphan AccidentSeverity nodes

Use only if zero-count severity nodes were accidentally created (e.g. `Letsel`, `UMS`, `Materieel`).

```cypher
MATCH (s:AccidentSeverity)
WHERE NOT (:CyclingAccident)-[:HAS_SEVERITY]->(s)
DETACH DELETE s;
```

## 11 · Add Dutch alternative labels and descriptions

```cypher
MATCH (s:AccidentSeverity {name: "injury"})
SET s.alternative_name_nl = "Letsel",
    s.description = "Accident involving injury";

MATCH (s:AccidentSeverity {name: "fatal"})
SET s.alternative_name_nl = "Dodelijk",
    s.description = "Fatal accident";

MATCH (s:AccidentSeverity {name: "property_damage_only"})
SET s.alternative_name_nl = "UMS / Materieel",
    s.description = "Property-damage-only accident";
```

---

# Research-question queries

## 12 · Accident hotspots

> Where are accident hotspots?

```cypher
MATCH (a:CyclingAccident)-[:OCCURRED_IN]->(n:Neighbourhood)
RETURN n.BUURTCODE AS BUURTCODE,
       n.BUURTNAAM AS neighbourhood,
       count(a) AS accident_count
ORDER BY accident_count DESC
LIMIT 10;
```

## 13 · Accident hotspots with severity breakdown

Uses the semantic `AccidentSeverity` node and `HAS_SEVERITY` relationship.

```cypher
MATCH (a:CyclingAccident)-[:OCCURRED_IN]->(n:Neighbourhood)
MATCH (a)-[:HAS_SEVERITY]->(s:AccidentSeverity)
RETURN n.BUURTCODE AS BUURTCODE,
       n.BUURTNAAM AS neighbourhood,
       count(a) AS accident_count,
       sum(CASE WHEN s.name = "injury" THEN 1 ELSE 0 END) AS injury_count,
       sum(CASE WHEN s.name = "fatal" THEN 1 ELSE 0 END) AS fatal_count,
       sum(CASE WHEN s.name = "property_damage_only" THEN 1 ELSE 0 END) AS property_damage_only_count
ORDER BY accident_count DESC
LIMIT 10;
```

## 14 · Low bike lane density

> Where is infrastructure insufficient in terms of bike lane coverage?

```cypher
MATCH (n:Neighbourhood)
OPTIONAL MATCH (l:BikeLaneSegment)-[r:PASSES_THROUGH]->(n)
WITH n,
     coalesce(sum(r.intersected_length_m), 0) AS lane_length_m
RETURN n.BUURTCODE AS BUURTCODE,
       n.BUURTNAAM AS neighbourhood,
       n.area_km2 AS area_km2,
       lane_length_m,
       CASE
           WHEN n.area_km2 IS NULL OR n.area_km2 = 0 THEN null
           ELSE round(lane_length_m / n.area_km2, 2)
       END AS lane_density_m_per_km2
ORDER BY lane_density_m_per_km2 ASC
LIMIT 20;
```

## 15 · Formal bike parking capacity context

> Where is formal bike parking capacity low?

DS1 is used as supplementary context only; it covers formally registered facilities.

```cypher
MATCH (n:Neighbourhood)
OPTIONAL MATCH (p:BikeParkingFacility)-[:LOCATED_IN]->(n)
WITH n,
     count(p) AS parking_count,
     coalesce(sum(p.capacity), 0) AS parking_capacity
RETURN n.BUURTCODE AS BUURTCODE,
       n.BUURTNAAM AS neighbourhood,
       n.population AS population,
       parking_count,
       parking_capacity,
       CASE
           WHEN n.population IS NULL OR n.population = 0 THEN null
           ELSE round(parking_capacity * 1000.0 / n.population, 2)
       END AS parking_capacity_per_1000_residents
ORDER BY parking_capacity_per_1000_residents ASC
LIMIT 20;
```

## 16 · Combined priority candidates

> Where do accidents and infrastructure deficits overlap?

Main combined query, using accident risk, bike lane density, and formal parking context.

```cypher
MATCH (n:Neighbourhood)
WHERE n.population > 0

OPTIONAL MATCH (a:CyclingAccident)-[:OCCURRED_IN]->(n)
OPTIONAL MATCH (a)-[:HAS_SEVERITY]->(s:AccidentSeverity)
WITH n,
     count(a) AS accident_count,
     sum(CASE WHEN s.name = "injury" THEN 1 ELSE 0 END) AS injury_count,
     sum(CASE WHEN s.name = "fatal" THEN 1 ELSE 0 END) AS fatal_count,
     sum(CASE WHEN s.name = "property_damage_only" THEN 1 ELSE 0 END) AS property_damage_only_count

OPTIONAL MATCH (b:BikeLaneSegment)-[r:PASSES_THROUGH]->(n)
WITH n,
     accident_count,
     injury_count,
     fatal_count,
     property_damage_only_count,
     coalesce(sum(r.intersected_length_m), 0) AS lane_length_m

OPTIONAL MATCH (p:BikeParkingFacility)-[:LOCATED_IN]->(n)
WITH n,
     accident_count,
     injury_count,
     fatal_count,
     property_damage_only_count,
     lane_length_m,
     count(p) AS parking_count,
     coalesce(sum(p.capacity), 0) AS parking_capacity

RETURN n.BUURTCODE AS BUURTCODE,
       n.BUURTNAAM AS neighbourhood,
       n.population AS population,
       n.area_km2 AS area_km2,
       n.pop_density AS pop_density,

       accident_count,
       injury_count,
       fatal_count,
       property_damage_only_count,

       lane_length_m,
       parking_count,
       parking_capacity,

       round(accident_count * 1000.0 / n.population, 2) AS accident_rate_per_1000_residents,
       round(lane_length_m / n.area_km2, 2) AS lane_density_m_per_km2,
       round(parking_capacity * 1000.0 / n.population, 2) AS parking_capacity_per_1000_residents

ORDER BY accident_rate_per_1000_residents DESC,
         lane_density_m_per_km2 ASC
LIMIT 20;
```

## 17 · Dense areas with infrastructure gap

> Which dense areas have the largest infrastructure gap?

Prioritises dense neighbourhoods with lower bike lane density and lower formal parking context.

```cypher
MATCH (n:Neighbourhood)
WHERE n.population > 0
  AND n.area_km2 > 0

OPTIONAL MATCH (l:BikeLaneSegment)-[r:PASSES_THROUGH]->(n)
WITH n,
     coalesce(sum(r.intersected_length_m), 0) AS lane_length_m

OPTIONAL MATCH (p:BikeParkingFacility)-[:LOCATED_IN]->(n)
WITH n,
     lane_length_m,
     count(p) AS parking_count,
     coalesce(sum(p.capacity), 0) AS parking_capacity

RETURN n.BUURTCODE AS BUURTCODE,
       n.BUURTNAAM AS neighbourhood,
       n.population AS population,
       n.pop_density AS pop_density,
       n.area_km2 AS area_km2,
       lane_length_m,
       parking_count,
       parking_capacity,
       round(lane_length_m / n.area_km2, 2) AS lane_density_m_per_km2,
       round(parking_capacity * 1000.0 / n.population, 2) AS parking_capacity_per_1000_residents
ORDER BY n.pop_density DESC,
         lane_density_m_per_km2 ASC
LIMIT 20;
```

---

# SQL vs Cypher comparison

## 18 · Fan-trap demonstration (not for final analysis)

Demonstrates that row multiplication can also occur in Cypher when multiple
one-to-many patterns are matched before aggregation.

```cypher
// Do not use this for final analysis.
// Matching multiple one-to-many patterns before aggregation can multiply rows.
MATCH (n:Neighbourhood)
OPTIONAL MATCH (a:CyclingAccident)-[:OCCURRED_IN]->(n)
OPTIONAL MATCH (b:BikeLaneSegment)-[:PASSES_THROUGH]->(n)
OPTIONAL MATCH (p:BikeParkingFacility)-[:LOCATED_IN]->(n)
RETURN n.BUURTNAAM AS neighbourhood,
       count(a) AS inflated_accident_count,
       count(b) AS inflated_lane_count,
       count(p) AS inflated_parking_count
ORDER BY inflated_accident_count DESC
LIMIT 10;
```

The correct approach aggregates each relationship pattern step by step with `WITH` (see §16).

---

# Visualisation / example graphs

## 19 · Select a readable example neighbourhood

Finds a neighbourhood with accidents, parking, and lane segments for a readable instance graph.

```cypher
MATCH (n:Neighbourhood)
OPTIONAL MATCH (a:CyclingAccident)-[:OCCURRED_IN]->(n)
OPTIONAL MATCH (p:BikeParkingFacility)-[:LOCATED_IN]->(n)
OPTIONAL MATCH (l:BikeLaneSegment)-[:PASSES_THROUGH]->(n)
WITH n,
     count(DISTINCT a) AS accident_count,
     count(DISTINCT p) AS parking_count,
     count(DISTINCT l) AS lane_count
WHERE accident_count > 0
  AND parking_count > 0
  AND lane_count > 0
RETURN n.BUURTNAAM AS neighbourhood,
       accident_count,
       parking_count,
       lane_count
ORDER BY accident_count DESC
LIMIT 10;
```

## 20 · Example graph for Binnenstad

Readable instance graph around Binnenstad; limits each connected node type.

```cypher
MATCH (n:Neighbourhood {BUURTNAAM: "Binnenstad"})
CALL (n) {
    MATCH (a:CyclingAccident)-[r:OCCURRED_IN]->(n)
    RETURN a AS x, r AS rel
    LIMIT 3
    UNION
    WITH n
    MATCH (p:BikeParkingFacility)-[r:LOCATED_IN]->(n)
    RETURN p AS x, r AS rel
    LIMIT 3
    UNION
    WITH n
    MATCH (l:BikeLaneSegment)-[r:PASSES_THROUGH]->(n)
    RETURN l AS x, r AS rel
    LIMIT 3
}
RETURN n, x, rel;
```

## 21 · Example graph for Binnenstad including AccidentSeverity

Use when the visualisation should show the semantic severity node.

```cypher
MATCH (n:Neighbourhood {BUURTNAAM: "Binnenstad"})
CALL (n) {
    MATCH (a:CyclingAccident)-[r1:OCCURRED_IN]->(n)
    MATCH (a)-[r2:HAS_SEVERITY]->(s:AccidentSeverity)
    RETURN a AS x, r1 AS rel1, s AS y, r2 AS rel2
    LIMIT 3
}
RETURN n, x, rel1, y, rel2;
```

---

# Display names

Helper updates that give nodes a readable label for Neo4j Browser / Bloom visualisation.

## 22 · Neighbourhood

```cypher
MATCH (n:Neighbourhood)
SET n.display_name = n.BUURTNAAM;
```

## 23 · CyclingAccident

```cypher
MATCH (a:CyclingAccident)
SET a.display_name =
    toString(a.accident_year) + " " + coalesce(a.accident_outcome_standardized, "unknown");
```

## 24 · BikeParkingFacility

```cypher
MATCH (p:BikeParkingFacility)
SET p.display_name = coalesce(p.name, "bike parking");
```

## 25 · BikeLaneSegment

```cypher
MATCH (l:BikeLaneSegment)
SET l.display_name = coalesce(l.name, coalesce(l.highway, "lane segment"));
```

## 26 · AccidentSeverity

```cypher
MATCH (s:AccidentSeverity)
SET s.display_name = s.name;
```

---

# Cleanup

## 27 · Remove AccidentSeverity nodes and relationships

Use only to undo the severity schema update.

```cypher
MATCH (:CyclingAccident)-[r:HAS_SEVERITY]->(:AccidentSeverity)
DELETE r;

MATCH (s:AccidentSeverity)
DETACH DELETE s;
```
