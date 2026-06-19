# 2AMD20 — Knowledge Engineering: Cycling Infrastructure Prioritization

**Group 15** · TU/e

A Neo4j knowledge graph and interactive dashboard that identifies which Eindhoven
neighbourhoods should be prioritized for cycling infrastructure investment, built
for Gemeente Eindhoven (Municipality of Eindhoven).

## Overview

This project integrates four heterogeneous datasets into a single property graph
in Neo4j and computes a data-driven priority score per neighbourhood, combining
cycling accident risk and bike lane deficit. The result is explored through a
Dash-based dashboard with maps, rankings, and per-neighbourhood detail views.

**Priority score formula:**

```
gap_score = 0.5 * z_accident + 0.5 * z_lane_deficit
```

`z_accident` and `z_lane_deficit` are z-scores of accident rate and lane density
deficit per neighbourhood. Bike parking capacity was evaluated but excluded from
the final formula due to low variance across neighbourhoods.

**Top-priority neighbourhoods identified:** Binnenstad, Driehoeksbos,
Engelsbergen, Barrier.

## Data sources

| Dataset | Description | Raw file(s) |
|---|---|---|
| BRON accident data | Cycling accidents, 2022-2024 | `data/raw/ongevallen_2022_2024.csv` |
| Bike parking facilities | Formal bike parking locations & capacity | `data/raw/fietsenstallingen.csv` |
| Neighbourhood statistics | Population, area, density (CBS kerncijfers) | `data/raw/buurten.csv`, `data/raw/Inwoners - Buurten [117].csv`, `data/raw/Kerncijfers_wijken_en_buurten_2025_*.csv` |
| OpenStreetMap bike lanes | Bike lane geometry & attributes | `data/raw/eindhoven_bike_lanes.geojson`, `.gpkg`, `_attributes.csv` |

Raw data is cleaned and spatially joined (GeoPandas/Shapely) into the files under
`data/clean/`, and into SQL-baseline equivalents under `data/sql/` for comparison
against the Cypher/graph approach.

## Repository structure

```
.
├── data/
│   ├── raw/            # Original source files
│   ├── clean/          # Cleaned & spatially-joined datasets (ds1/ds2/ds3, joins, summaries)
│   └── sql/            # SQL-baseline joins and results, for SQL-vs-Cypher comparison
├── notebooks/
│   ├── DS4_download_cleaning.ipynb     # Neighbourhood stats download & cleaning
│   ├── accident_df_EDA.ipynb           # Accident data exploration
│   ├── cycling_eda.ipynb               # Bike lane EDA
│   ├── join_tables.ipynb               # Spatial joins across datasets
│   └── sql_baseline_comparison.ipynb   # Relational baseline vs. KG approach
├── neo4j/
│   └── cycling_kg_cypher_queries.md    # Full Cypher query archive (import, schema, RQs, viz)
├── figures/             # Exported plots & an HTML bike-parking map
├── frontend/            # Dash dashboard application
│   ├── app.py                # Main Dash app (layout, callbacks, maps, tables)
│   ├── neo4j_client.py        # Neo4j driver/connection wrapper
│   ├── cypher_queries.py      # Cypher queries used by the dashboard
│   ├── data_loader.py         # Query execution + dataframe shaping for the UI
│   ├── data_service.py        # Data service layer
│   ├── test_neo4j_connection.py
│   ├── ds3.csv                         # Neighbourhood summary data (local fallback)
│   ├── eindhoven_bike_lanes_core.geojson
│   ├── style.css
│   ├── .env.example
│   └── requirements.txt
└── README.md
```

## Setup

### 1. Neo4j database

The dashboard expects an existing Neo4j (AuraDB or local) instance populated
with the cycling infrastructure graph. Use `neo4j/cycling_kg_cypher_queries.md`
as the reference for import, schema setup, and validation — it includes:

- Setup & validation queries (§00-§03)
- `AccidentSeverity` schema update (§04-§11)
- Research-question queries (§12-§17)
- SQL vs. Cypher comparison query (§18)
- Visualisation / example-graph queries (§19-§21)
- Display-name setup (§22-§26)
- Cleanup (§27)

Expected node counts after import:

```
BikeLaneSegment:     4627
BikeParkingFacility:    7
CyclingAccident:     1621
Neighbourhood:        111
```

### 2. Dashboard

```bash
cd frontend
pip install -r requirements.txt
cp .env.example .env   # then fill in your Neo4j credentials
python app.py
```

`.env` requires:

```
NEO4J_URI=neo4j+s://your-database-id.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
NEO4J_DATABASE=
```

Test the connection independently with:

```bash
python frontend/test_neo4j_connection.py
```

> **Note:** `app.py` imports from a `services` package (e.g.
> `from services.data_loader import ...`). Make sure `data_loader.py`,
> `neo4j_client.py`, and `cypher_queries.py` are organized under a `services/`
> package (or update the imports) before running the app.

## Data pipeline

1. **Clean & explore** raw data — `notebooks/accident_df_EDA.ipynb`,
   `notebooks/cycling_eda.ipynb`, `notebooks/DS4_download_cleaning.ipynb`.
2. **Spatial join** accidents, bike lanes, parking, and neighbourhood boundaries
   using GeoPandas/Shapely — `notebooks/join_tables.ipynb` → outputs to
   `data/clean/`.
3. **Load into Neo4j** using the import section of
   `neo4j/cycling_kg_cypher_queries.md`.
4. **Compute scores** (accident risk, lane deficit, gap score, priority score)
   via Cypher, validated against a relational SQL baseline in
   `notebooks/sql_baseline_comparison.ipynb` (`data/sql/results/`).
5. **Visualize** through the Dash dashboard (`frontend/app.py`).

## Deliverables

- Knowledge graph (Neo4j) integrating 4 datasets
- Interactive dashboard (maps, rankings, neighbourhood detail cards)
- Poster (poster session)
- Presentation script

## Authors

Group 15, 2AMD20 Knowledge Engineering, TU/e.
