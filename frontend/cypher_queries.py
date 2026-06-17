TEST_CONNECTION_QUERY = """
RETURN "AuraDB is connected" AS message;
"""


NODE_COUNT_QUERY = """
MATCH (n)
RETURN labels(n) AS node_type,
       count(n) AS count
ORDER BY node_type;
"""


RELATIONSHIP_COUNT_QUERY = """
MATCH ()-[r]->()
RETURN type(r) AS relationship_type,
       count(r) AS count
ORDER BY relationship_type;
"""


TOTAL_ACCIDENT_QUERY = """
MATCH (a:CyclingAccident)
RETURN count(a) AS total_accidents;
"""


FINAL_PRIORITY_TABLE_QUERY = """
MATCH (n:Neighbourhood)
WHERE n.population >= 500
  AND n.area_km2 >= 0.1

OPTIONAL MATCH (a:CyclingAccident)-[:OCCURRED_IN]->(n)
WITH n,
     count(a) AS accident_count

OPTIONAL MATCH (l:BikeLaneSegment)-[r:PASSES_THROUGH]->(n)
WITH n,
     accident_count,
     coalesce(sum(r.intersected_length_m), 0) AS lane_length_m

WITH n,
     accident_count,
     lane_length_m,
     accident_count * 1000.0 / n.population AS accident_rate,
     lane_length_m / n.area_km2             AS lane_density

WITH collect({
     n:              n,
     accident_count: accident_count,
     lane_length_m:  lane_length_m,
     accident_rate:  accident_rate,
     lane_density:   lane_density
}) AS rows

UNWIND rows AS row_for_stats
WITH rows,
     avg(row_for_stats.accident_rate)   AS avg_accident_rate,
     stdev(row_for_stats.accident_rate) AS sd_accident_rate,
     avg(row_for_stats.lane_density)    AS avg_lane_density,
     stdev(row_for_stats.lane_density)  AS sd_lane_density

UNWIND rows AS row
WITH row,
     CASE
         WHEN sd_accident_rate = 0 OR sd_accident_rate IS NULL THEN 0
         ELSE (row.accident_rate - avg_accident_rate) / sd_accident_rate
     END AS z_accident,
     CASE
         WHEN sd_lane_density = 0 OR sd_lane_density IS NULL THEN 0
         ELSE (avg_lane_density - row.lane_density) / sd_lane_density
     END AS z_lane_deficit

WITH row,
     z_accident,
     z_lane_deficit,
     row.n AS n

OPTIONAL MATCH (p:BikeParkingFacility)-[:LOCATED_IN]->(n)
WITH row, z_accident, z_lane_deficit,
     coalesce(sum(p.capacity), 0) AS parking_capacity

RETURN row.n.BUURTNAAM                                    AS neighbourhood,
       round(0.5 * z_accident + 0.5 * z_lane_deficit, 3) AS gap_score,
       round(z_accident, 3)                               AS accident_z,
       round(z_lane_deficit, 3)                           AS lane_deficit_z,
       row.n.population                                   AS population,
       round(row.accident_rate, 2)                        AS accident_rate_per_1000,
       round(row.lane_density, 2)                         AS lane_density_m_per_km2,
       parking_capacity                                   AS formal_parking_capacity,
       CASE WHEN parking_capacity = 0 THEN "No formal parking in DS1"
            ELSE "Has formal parking in DS1"
       END                                                AS parking_context
ORDER BY gap_score DESC
LIMIT 15;
"""


FINAL_PRIORITY_MAP_QUERY = FINAL_PRIORITY_TABLE_QUERY.replace(
    "ORDER BY gap_score DESC\nLIMIT 15;",
    "ORDER BY gap_score DESC;",
)


FINAL_PRIORITY_QUERY = FINAL_PRIORITY_TABLE_QUERY


ACCIDENT_HOTSPOTS_WITH_SEVERITY_QUERY = """
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
"""


SELECTED_NEIGHBOURHOOD_LANES_QUERY = """
MATCH (l:BikeLaneSegment)-[r:PASSES_THROUGH]->(n:Neighbourhood)
WHERE n.BUURTNAAM = $neighbourhood
RETURN l.id AS lane_id,
       coalesce(l.name, "") AS name,
       coalesce(l.highway, "") AS highway,
       coalesce(l.surface, "") AS surface,
       coalesce(l.lit, "") AS lit,
       round(r.intersected_length_m, 2) AS intersected_length_m
ORDER BY intersected_length_m DESC;
"""
