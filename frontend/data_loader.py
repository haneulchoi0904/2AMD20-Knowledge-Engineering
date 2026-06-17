from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from services.cypher_queries import FINAL_PRIORITY_MAP_QUERY, FINAL_PRIORITY_TABLE_QUERY, SELECTED_NEIGHBOURHOOD_LANES_QUERY, TOTAL_ACCIDENT_QUERY
from services.neo4j_client import Neo4jClient


REQUIRED_COLUMNS = [
    "BUURTCODE",
    "neighbourhood",
    "district",
    "geo_shape",
    "population",
    "area_km2",
    "pop_density",
    "gap_score",
    "priority_score",
    "priority_category",
    "has_score",
    "accident_z",
    "lane_deficit_z",
    "accident_risk_score",
    "lane_deficit_score",
    "accident_pressure_score",
    "bike_lane_shortage_score",
    "accident_count",
    "accident_rate_per_1000",
    "lane_length_m",
    "lane_density_m_per_km2",
    "formal_parking_capacity",
    "formal_parking_capacity_per_1000",
    "parking_context",
    "data_source",
    "total_accidents",
]


def normalize_buurtcode(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def normalize_name(value: Any) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().casefold().split())


def minmax(series: pd.Series) -> pd.Series:
    series = pd.to_numeric(series, errors="coerce")
    min_value = series.min()
    max_value = series.max()
    if pd.isna(min_value) or pd.isna(max_value) or max_value == min_value:
        return pd.Series([0.0] * len(series), index=series.index)
    return (series - min_value) / (max_value - min_value)


def add_display_priority_score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    raw = pd.to_numeric(df["gap_score"], errors="coerce")
    min_value = raw.min()
    max_value = raw.max()
    if pd.isna(min_value) or pd.isna(max_value) or max_value == min_value:
        df["priority_score"] = 50
    else:
        df["priority_score"] = ((raw - min_value) / (max_value - min_value) * 100).round().astype(int)
    df["priority_category"] = pd.cut(
        df["priority_score"],
        bins=[-1, 44, 69, 100],
        labels=["Lower priority", "Medium priority", "High priority"],
    ).astype(str)
    return df


def add_mock_priority_score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    accident_norm = minmax(df["accident_rate_per_1000"])
    lane_deficit_norm = 1 - minmax(df["lane_density_m_per_km2"])
    density_norm = minmax(df["pop_density"])
    df["gap_score"] = (0.5 * accident_norm + 0.5 * lane_deficit_norm).round(3)
    df["accident_z"] = ((accident_norm - accident_norm.mean()) / max(accident_norm.std(), 1e-9)).round(3)
    df["lane_deficit_z"] = ((lane_deficit_norm - lane_deficit_norm.mean()) / max(lane_deficit_norm.std(), 1e-9)).round(3)
    df["gap_score"] = (0.5 * df["accident_z"] + 0.5 * df["lane_deficit_z"] + 0.05 * density_norm).round(3)
    return add_display_priority_score(df)


def resolve_ds3_path(path: str | Path = "data/ds3.csv") -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate
    root_candidate = Path(__file__).resolve().parents[1] / "ds3.csv"
    if root_candidate.exists():
        return root_candidate
    raise FileNotFoundError(f"Could not find ds3.csv at {candidate} or {root_candidate}")


def resolve_ds4_path(path: str | Path = "eindhoven_bike_lanes_core.geojson") -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate
    root_candidate = Path(__file__).resolve().parents[1] / "eindhoven_bike_lanes_core.geojson"
    if root_candidate.exists():
        return root_candidate
    raise FileNotFoundError(f"Could not find bike lane GeoJSON at {candidate} or {root_candidate}")


def load_neighbourhood_geometry(path: str | Path = "data/ds3.csv") -> tuple[pd.DataFrame, dict[str, Any]]:
    ds3_path = resolve_ds3_path(path)
    df = pd.read_csv(ds3_path)
    keep_cols = ["BUURTCODE", "BUURTNAAM", "STADSDEELNAAM", "geo_shape", "population", "area_km2", "pop_density"]
    df = df[[col for col in keep_cols if col in df.columns]].copy()
    df["BUURTCODE"] = df["BUURTCODE"].apply(normalize_buurtcode)
    df["BUURTNAAM"] = df["BUURTNAAM"].astype(str)
    df["name_key"] = df["BUURTNAAM"].apply(normalize_name)

    features = []
    for _, row in df.iterrows():
        if pd.isna(row.get("geo_shape")):
            continue
        try:
            geometry = json.loads(row["geo_shape"])
        except (TypeError, json.JSONDecodeError):
            print(f"[Data] Skipping invalid geo_shape for {row.get('BUURTNAAM', 'unknown')}.")
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "BUURTCODE": row["BUURTCODE"],
                    "BUURTNAAM": row["BUURTNAAM"],
                },
                "geometry": geometry,
            }
        )
    return df, {"type": "FeatureCollection", "features": features}


@lru_cache(maxsize=1)
def load_bike_lane_geometry(path: str = "eindhoven_bike_lanes_core.geojson") -> pd.DataFrame:
    ds4_path = resolve_ds4_path(path)
    with open(ds4_path, encoding="utf-8") as lane_file:
        data = json.load(lane_file)

    rows = []
    for feature in data.get("features", []):
        props = feature.get("properties", {}) or {}
        geometry = feature.get("geometry")
        lane_id = props.get("id")
        if lane_id is None or not geometry:
            continue
        rows.append(
            {
                "id": str(lane_id),
                "geometry_obj": geometry,
                "ds4_name": props.get("name", ""),
                "ds4_highway": props.get("highway", ""),
                "ds4_surface": props.get("surface", ""),
            }
        )
    return pd.DataFrame(rows)


def ensure_dashboard_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    numeric_cols = [
        "population",
        "area_km2",
        "pop_density",
        "gap_score",
        "priority_score",
        "has_score",
        "accident_z",
        "lane_deficit_z",
        "accident_risk_score",
        "lane_deficit_score",
        "accident_pressure_score",
        "bike_lane_shortage_score",
        "accident_count",
        "accident_rate_per_1000",
        "lane_length_m",
        "lane_density_m_per_km2",
        "formal_parking_capacity",
        "formal_parking_capacity_per_1000",
        "total_accidents",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["BUURTCODE"] = df["BUURTCODE"].apply(normalize_buurtcode)
    df["neighbourhood"] = df["neighbourhood"].fillna(df.get("BUURTNAAM", "Unknown")).astype(str)
    df["district"] = df["district"].fillna(df.get("STADSDEELNAAM", "Unknown")).astype(str)
    df["priority_category"] = df["priority_category"].fillna("Lower priority")
    df["parking_context"] = df["parking_context"].fillna("No formal parking in DS1")
    df["data_source"] = df["data_source"].fillna("mock")
    df["accident_rate_per_1000_residents"] = df["accident_rate_per_1000"]
    df["parking_capacity"] = df["formal_parking_capacity"]
    df["parking_capacity_per_1000_residents"] = df["formal_parking_capacity_per_1000"]
    return df


def enrich_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    population = pd.to_numeric(df["population"], errors="coerce")
    formal_parking = pd.to_numeric(df["formal_parking_capacity"], errors="coerce").fillna(0)
    df["formal_parking_capacity_per_1000"] = (formal_parking * 1000 / population.where(population != 0)).round(2)
    df["formal_parking_capacity_per_1000"] = df["formal_parking_capacity_per_1000"].fillna(0)
    df = add_relative_scores(df)
    return ensure_dashboard_columns(df)


def add_relative_scores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    def scale_0_100(series: pd.Series) -> pd.Series:
        series = pd.to_numeric(series, errors="coerce")
        min_value = series.min()
        max_value = series.max()
        if pd.isna(min_value) or pd.isna(max_value) or max_value == min_value:
            return pd.Series([50] * len(series), index=series.index)
        return ((series - min_value) / (max_value - min_value) * 100).round(0)

    df["accident_pressure_score"] = scale_0_100(df.get("accident_z", pd.Series(index=df.index, dtype="float64")))
    df["bike_lane_shortage_score"] = scale_0_100(df.get("lane_deficit_z", pd.Series(index=df.index, dtype="float64")))
    df["accident_risk_score"] = df["accident_pressure_score"]
    df["lane_deficit_score"] = df["bike_lane_shortage_score"]
    return df


def load_mock_neighbourhood_indicators(path: str | Path = "data/ds3.csv") -> pd.DataFrame:
    geometry_df, _ = load_neighbourhood_geometry(path)
    df = geometry_df.copy()
    df["population"] = pd.to_numeric(df.get("population"), errors="coerce").fillna(0)
    df["area_km2"] = pd.to_numeric(df.get("area_km2"), errors="coerce").fillna(0)
    df["pop_density"] = pd.to_numeric(df.get("pop_density"), errors="coerce").fillna(0)
    density_norm = minmax(df["pop_density"])
    index_series = pd.Series(range(len(df)), index=df.index)
    df["accident_rate_per_1000"] = (10 + density_norm * 52 + ((index_series * 7) % 11)).round(2)
    df["lane_density_m_per_km2"] = (58 - density_norm * 36 + ((index_series * 3) % 8)).round(2)
    df["accident_count"] = (df["accident_rate_per_1000"] * df["population"] / 1000).round().astype(int)
    df["lane_length_m"] = (df["lane_density_m_per_km2"] * df["area_km2"]).round(2)
    df["formal_parking_capacity"] = (((62 - density_norm * 40 + ((index_series * 5) % 9)) * df["population"]) / 1000).round().astype(int)
    df["parking_context"] = df["formal_parking_capacity"].apply(lambda value: "No formal parking in DS1" if value == 0 else "Has formal parking in DS1")
    df["neighbourhood"] = df["BUURTNAAM"]
    df["district"] = df["STADSDEELNAAM"].fillna("Unknown")
    df = add_mock_priority_score(df)
    df["has_score"] = True
    df["data_source"] = "mock"
    df["total_accidents"] = int(df["accident_count"].sum())
    return enrich_display_columns(df)


def run_neo4j_query(query: str) -> tuple[pd.DataFrame, int]:
    client = Neo4jClient()
    try:
        if not client.verify():
            raise RuntimeError("Neo4j connectivity verification failed.")
        rows = client.run_query(query)
        if not rows:
            raise RuntimeError("Final priority query returned no rows.")
        total_rows = client.run_query(TOTAL_ACCIDENT_QUERY)
        total_accidents = int(total_rows[0].get("total_accidents", 0)) if total_rows else 0
        return pd.DataFrame(rows), total_accidents
    finally:
        client.close()


def get_bike_lanes_for_neighbourhood(neighbourhood: str | None) -> pd.DataFrame:
    if not neighbourhood:
        return pd.DataFrame()
    try:
        client = Neo4jClient()
        try:
            rows = client.run_query(SELECTED_NEIGHBOURHOOD_LANES_QUERY, {"neighbourhood": neighbourhood})
        finally:
            client.close()
        if not rows:
            return pd.DataFrame()
        lanes = pd.DataFrame(rows)
        lanes["lane_id"] = lanes["lane_id"].astype(str)
        geometry_df = load_bike_lane_geometry()
        merged = lanes.merge(geometry_df, left_on="lane_id", right_on="id", how="inner")
        if merged.empty:
            print(f"[Data] No DS4 geometry matched Neo4j lane IDs for {neighbourhood}.")
        return merged
    except Exception as exc:
        print(f"[Data] Could not load bike lanes for {neighbourhood}: {exc}")
        return pd.DataFrame()


def merge_indicators_with_geometry(indicators_df: pd.DataFrame, geometry_df: pd.DataFrame, how: str = "inner") -> pd.DataFrame:
    indicators = indicators_df.copy()
    if "BUURTCODE" in indicators:
        indicators["BUURTCODE"] = indicators["BUURTCODE"].apply(normalize_buurtcode)
    indicators["name_key"] = indicators["neighbourhood"].apply(normalize_name)
    indicators["has_score"] = True

    merged = geometry_df.merge(indicators.drop(columns=["BUURTCODE"], errors="ignore"), on="name_key", how=how, suffixes=("_geo", ""))

    matched_codes = set(merged.loc[merged["has_score"].notna(), "BUURTCODE"]) if "has_score" in merged else set()
    matched_names = set(merged["neighbourhood"]) if not merged.empty and "neighbourhood" in merged else set()
    missing = indicators[~indicators["neighbourhood"].isin(matched_names)]
    if not missing.empty:
        print("[Data] Unmatched Neo4j neighbourhood rows:", ", ".join(missing["neighbourhood"].head(8).astype(str)))
    if merged.empty:
        raise RuntimeError("Final priority rows could not be matched to ds3.csv geometry.")

    merged["neighbourhood"] = merged["neighbourhood"].fillna(merged["BUURTNAAM"])
    merged["district"] = merged.get("district", pd.Series(index=merged.index, dtype="object")).fillna(merged["STADSDEELNAAM"])
    merged["has_score"] = merged["has_score"].fillna(False)
    merged["data_source"] = merged["data_source"].fillna("neo4j")
    return merged


def get_dashboard_neighbourhood_data(path: str | Path = "data/ds3.csv") -> tuple[pd.DataFrame, dict[str, Any]]:
    geometry_df, geojson = load_neighbourhood_geometry(path)
    try:
        indicators_df, total_accidents = run_neo4j_query(FINAL_PRIORITY_TABLE_QUERY)
        indicators_df = add_display_priority_score(indicators_df)
        indicators_df["data_source"] = "neo4j"
        indicators_df["total_accidents"] = total_accidents
        merged = merge_indicators_with_geometry(indicators_df, geometry_df, how="inner")
        merged = enrich_display_columns(merged)
        print("[Data] Loaded final top-15 priority ranking from Neo4j.")
    except Exception as exc:
        print(f"[Data] Falling back to mock data: {exc}")
        merged = load_mock_neighbourhood_indicators(path)

    merged = merged.sort_values(["gap_score", "priority_score"], ascending=False).reset_index(drop=True)
    merged["rank"] = merged.index + 1
    return merged, geojson


def get_dashboard_data(path: str | Path = "data/ds3.csv") -> tuple[pd.DataFrame, dict[str, Any]]:
    return get_dashboard_neighbourhood_data(path)


def get_map_data(path: str | Path = "data/ds3.csv") -> pd.DataFrame:
    geometry_df, _ = load_neighbourhood_geometry(path)
    try:
        indicators_df, total_accidents = run_neo4j_query(FINAL_PRIORITY_MAP_QUERY)
        indicators_df = add_display_priority_score(indicators_df)
        indicators_df["data_source"] = "neo4j"
        indicators_df["total_accidents"] = total_accidents
        merged = merge_indicators_with_geometry(indicators_df, geometry_df, how="left")
        merged = enrich_display_columns(merged)
        print("[Data] Loaded map-specific priority scores from Neo4j.")
    except Exception as exc:
        print(f"[Data] Falling back to mock map data: {exc}")
        merged = load_mock_neighbourhood_indicators(path)

    merged = merged.sort_values(["has_score", "gap_score", "priority_score"], ascending=False).reset_index(drop=True)
    merged["rank"] = merged.index + 1
    return merged
