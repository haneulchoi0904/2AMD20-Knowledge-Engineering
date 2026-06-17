from __future__ import annotations

from pathlib import Path
from typing import Any

import dash
from dash import Input, Output, State, callback_context, dash_table, dcc, html
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from services.data_loader import get_bike_lanes_for_neighbourhood, get_dashboard_data, get_map_data


DS3_CSV_PATH = Path(__file__).with_name("ds3.csv")
RISK_COLORS = ["#77c35a", "#d6d85b", "#ffc857", "#f28c28", "#e53935"]
DEFAULT_SELECTED_NEIGHBOURHOOD = "Tongelre"


FORMAT_RULES = {
    "priority_score": 0,
    "gap_score": 2,
    "accident_z": 2,
    "lane_deficit_z": 2,
    "accident_rate_per_1000": 2,
    "lane_density_m_per_km2": 2,
    "formal_parking_capacity": 0,
    "formal_parking_capacity_per_1000": 2,
    "pop_density": 2,
    "population": 0,
    "area_km2": 2,
}


def clean_number(value: Any) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return None
    return float(numeric)


def fmt_number(value: Any, decimals: int = 2, comma: bool = True) -> str:
    numeric = clean_number(value)
    if numeric is None:
        return "-"
    if decimals == 0:
        return f"{numeric:,.0f}" if comma else f"{numeric:.0f}"
    return f"{numeric:,.{decimals}f}" if comma else f"{numeric:.{decimals}f}"


def fmt_metric(value: Any, metric: str) -> str:
    return fmt_number(value, FORMAT_RULES.get(metric, 2))


def fmt_card_metric(value: Any, metric: str) -> str:
    if metric == "lane_density_m_per_km2":
        return fmt_number(value, 0)
    if metric in {"accident_rate_per_1000", "pop_density"}:
        return fmt_number(value, 1)
    return fmt_metric(value, metric)


def scored_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if bool(row.get("has_score", False))]


DS3_DF, NEIGHBOURHOOD_GEOJSON = get_dashboard_data(DS3_CSV_PATH)
MAP_DF = get_map_data(DS3_CSV_PATH)
DS3_CODES = DS3_DF["BUURTCODE"].tolist()


def conceptual_priority_rows() -> list[dict[str, Any]]:
    # Mock priority formula basis:
    # 0.40 * normalized accidents + 0.25 * lane deficit
    # + 0.20 * parking deficit + 0.15 * population density.
    # The score is hardcoded here so the UI is stable before Neo4j Query 16 is connected.
    rows = [
        ("Woensel-Zuid", "Woensel", 85, 68.3, 12.4, 18.6, 6980, 0),
        ("Oud-Woensel", "Woensel", 76, 61.2, 14.6, 21.3, 7420, 2),
        ("Gestel Noord", "Gestel", 69, 58.7, 16.8, 19.2, 6410, 4),
        ("Strijp", "Strijp", 64, 54.1, 18.9, 22.8, 5960, 6),
        ("Tongelre", "Tongelre", 58, 47.3, 22.3, 28.6, 6120, 8),
        ("Woensel-Noord", "Woensel", 43, 36.9, 27.8, 30.4, 5210, 10),
        ("Centrum", "Centrum", 39, 32.7, 30.9, 34.7, 7880, 12),
        ("Stratum", "Stratum", 37, 29.4, 32.1, 36.2, 5430, 14),
        ("Gestel Zuid", "Gestel", 31, 25.8, 36.4, 41.6, 4020, 16),
        ("Aalst", "Stratum", 26, 22.1, 40.3, 45.9, 3180, 18),
        ("Meerhoven", "Strijp", 22, 19.4, 44.1, 48.8, 2890, 20),
        ("Acht", "Woensel", 18, 16.2, 47.5, 52.0, 2410, 22),
        ("Blixembosch", "Woensel", 15, 13.4, 50.2, 55.4, 2290, 24),
        ("Gennep", "Gestel", 13, 11.8, 53.0, 59.7, 2100, 26),
        ("Koudenhoven", "Tongelre", 9, 9.6, 57.2, 64.0, 1840, 28),
    ]
    result = []
    for rank, (name, district, score, accident_rate, lane_density, parking_capacity, pop_density, code_index) in enumerate(rows, start=1):
        code = DS3_CODES[code_index % len(DS3_CODES)]
        result.append(
            {
                "rank": rank,
                "BUURTCODE": code,
                "neighbourhood": name,
                "district": district,
                "year": 2024,
                "priority_score": score,
                "priority_category": "High" if score >= 70 else "Medium" if score >= 50 else "Low",
                "accident_rate_per_1000_residents": accident_rate,
                "lane_density_m_per_km2": lane_density,
                "parking_capacity_per_1000_residents": parking_capacity,
                "pop_density": pop_density,
                "parking_capacity": round(parking_capacity * max(pop_density, 1) / 1000),
            }
        )
    return result


def build_ds3_mock_rows() -> list[dict[str, Any]]:
    df = DS3_DF.copy()
    df["pop_density"] = pd.to_numeric(df["pop_density"], errors="coerce").fillna(0)
    df["population"] = pd.to_numeric(df["population"], errors="coerce").fillna(0)
    density_min = df["pop_density"].min()
    density_max = df["pop_density"].max()
    density_spread = max(density_max - density_min, 1)
    rows = []
    for index, row in df.iterrows():
        density_norm = (row["pop_density"] - density_min) / density_spread
        # Deterministic mock metrics for all DS3 polygons. Replace this block with Neo4j
        # Query 16 output once neighbourhood-level indicators are finalized.
        accident_rate = 10 + density_norm * 52 + ((index * 7) % 11)
        lane_density = 58 - density_norm * 36 + ((index * 3) % 8)
        parking_per_1k = 62 - density_norm * 40 + ((index * 5) % 9)
        lane_deficit = 1 - min(lane_density / 65, 1)
        parking_deficit = 1 - min(parking_per_1k / 70, 1)
        accident_norm = min(accident_rate / 75, 1)
        priority_score = round((0.40 * accident_norm + 0.25 * lane_deficit + 0.20 * parking_deficit + 0.15 * density_norm) * 100)
        district = row.get("STADSDEELNAAM")
        if pd.isna(district) or not str(district).strip():
            district = row.get("WIJKNAAM")
        if pd.isna(district) or not str(district).strip():
            district = "Unknown"
        rows.append(
            {
                "rank": 0,
                "BUURTCODE": row["BUURTCODE"],
                "neighbourhood": row["BUURTNAAM"],
                "district": str(district),
                "year": 2024,
                "priority_score": priority_score,
                "priority_category": "High" if priority_score >= 70 else "Medium" if priority_score >= 50 else "Low",
                "accident_rate_per_1000_residents": round(accident_rate, 1),
                "lane_density_m_per_km2": round(lane_density, 1),
                "parking_capacity_per_1000_residents": round(parking_per_1k, 1),
                "pop_density": int(round(row["pop_density"])),
                "population": int(round(row["population"])),
                "area_km2": clean_number(row.get("area_km2")) or 0,
                "parking_capacity": int(round(parking_per_1k * max(row["population"], 1) / 1000)),
            }
        )
    rows = sorted(rows, key=lambda item: item["priority_score"], reverse=True)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def dashboard_rows() -> list[dict[str, Any]]:
    rows = DS3_DF.to_dict("records")
    for row in rows:
        row["rank"] = int(row.get("rank", 0) or 0)
        row["priority_score"] = int(row.get("priority_score", 0) or 0)
    return rows


def map_rows() -> list[dict[str, Any]]:
    rows = MAP_DF.to_dict("records")
    for row in rows:
        row["rank"] = int(row.get("rank", 0) or 0)
        row["priority_score"] = int(row.get("priority_score", 0) or 0)
    return rows


MOCK_ROWS = dashboard_rows()
MAP_ROWS = map_rows()
CONCEPT_ROWS = conceptual_priority_rows()
DEFAULT_SELECTED_NEIGHBOURHOOD = MOCK_ROWS[4]["neighbourhood"] if len(MOCK_ROWS) >= 5 else MOCK_ROWS[0]["neighbourhood"]
DATA_SOURCE = str(DS3_DF["data_source"].dropna().iloc[0]) if "data_source" in DS3_DF and not DS3_DF["data_source"].dropna().empty else "mock"


METRIC_OPTIONS = {
    "priority_score": "Priority Score",
    "accident_rate_per_1000_residents": "Accident Rate",
    "lane_density_m_per_km2": "Bike Lane Supply",
    "accident_pressure_score": "Accident Pressure",
    "bike_lane_shortage_score": "Bike Lane Shortage",
    "pop_density": "Population Density",
}


def rows_df(rows: list[dict[str, Any]] | None = None) -> pd.DataFrame:
    return pd.DataFrame(rows or MOCK_ROWS)


def filter_rows(district: str) -> list[dict[str, Any]]:
    if district == "ALL":
        return MOCK_ROWS
    return [row for row in MOCK_ROWS if row["district"] == district]


def filter_map_rows(district: str) -> list[dict[str, Any]]:
    if district == "ALL":
        return MAP_ROWS
    return [row for row in MAP_ROWS if row["district"] == district]


def display_number(value: Any, digits: int = 0) -> str:
    numeric = clean_number(value)
    if numeric is None:
        return "N/A"
    return f"{numeric:,.{digits}f}" if digits else f"{numeric:,.0f}"


def category_color(score: float) -> str:
    if score >= 70:
        return "#e53935"
    if score >= 50:
        return "#f28c28"
    if score >= 35:
        return "#ffc857"
    return "#77c35a"


def section_title(text: str) -> html.Div:
    return html.Div([html.H2(text), html.Span("i", className="info-dot")], className="section-title")


def build_header() -> html.Header:
    districts = sorted({row["district"] for row in MOCK_ROWS + MAP_ROWS})
    source_label = "Neo4j Connected" if DATA_SOURCE == "neo4j" else "Mock Data"
    source_class = "mock-pill neo4j" if DATA_SOURCE == "neo4j" else "mock-pill"
    return html.Header(
        [
            html.Div(
                [
                    html.Div("BIKE", className="header-icon"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H1("Eindhoven Cycling Infrastructure Dashboard"),
                                    html.Span(source_label, className=source_class),
                                ],
                                className="title-line",
                            ),
                            html.P("Prioritizing neighborhoods for safer and more equitable cycling improvements"),
                        ],
                        className="header-copy",
                    ),
                ],
                className="header-left",
            ),
            html.Div(
                [
                    filter_control(
                        "District",
                        dcc.Dropdown(
                            id="district-filter",
                            options=[{"label": "All Districts", "value": "ALL"}] + [{"label": district, "value": district} for district in districts],
                            value="ALL",
                            clearable=False,
                        ),
                    ),
                    filter_control(
                        "Metric (Map)",
                        dcc.Dropdown(
                            id="map-metric-filter",
                            options=[{"label": label, "value": value} for value, label in METRIC_OPTIONS.items()],
                            value="priority_score",
                            clearable=False,
                        ),
                    ),
                    html.Button("Reset Filters", id="reset-filters", className="reset-button"),
                ],
                className="header-filters",
            ),
        ],
        className="dashboard-header",
    )


def filter_control(label: str, control: Any) -> html.Div:
    return html.Div([html.Label(label), control], className="filter-control")


def kpi_card(icon: str, title: str, value: str, subtext: str, accent: str) -> html.Div:
    return html.Div(
        [
            html.Div(icon, className=f"kpi-icon {accent}"),
            html.Div([html.Div(title, className="kpi-title"), html.Div(value, className="kpi-value"), html.Div(subtext, className="kpi-subtext")]),
        ],
        className="dashboard-card kpi-card",
    )


def build_kpi_cards(rows: list[dict[str, Any]]) -> list[html.Div]:
    effective_rows = scored_rows(rows) or rows
    df = rows_df(effective_rows)
    if "priority_category" in df:
        high_count = int((df["priority_category"] == "High priority").sum())
    else:
        high_count = int((df["priority_score"] >= 70).sum())
    total_accidents = int(round(pd.to_numeric(df.get("total_accidents", df.get("accident_count", 0)), errors="coerce").fillna(0).max()))
    if total_accidents == 0:
        total_accidents = int(round(pd.to_numeric(df.get("accident_count", 0), errors="coerce").fillna(0).sum()))
    avg_accident_rate = pd.to_numeric(df["accident_rate_per_1000_residents"], errors="coerce").mean()
    avg_lane_density = df["lane_density_m_per_km2"].mean()
    return [
        kpi_card("UP", "High Priority Neighbourhoods", str(high_count), f"{high_count} out of {len(effective_rows)}", "blue"),
        kpi_card("!", "Total Cycling Accidents", f"{total_accidents:,}", "recorded cycling accidents", "red"),
        kpi_card("AR", "Avg Accident Rate", f"{avg_accident_rate:.2f} per 1k", "across ranked neighbourhoods", "green"),
        kpi_card("LN", "Avg Bike Lane Supply", f"{avg_lane_density:,.2f} m/km²", "across ranked neighbourhoods", "purple"),
    ]


def table_data(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_rows = sorted(scored_rows(rows), key=lambda row: row.get("gap_score", row["priority_score"]), reverse=True)[:15]
    return [
        {
            "rank": row["rank"],
            "neighbourhood": row["neighbourhood"],
            "priority_score": fmt_metric(row["priority_score"], "priority_score"),
            "accident_rate": fmt_metric(row["accident_rate_per_1000_residents"], "accident_rate_per_1000"),
            "lane_density": fmt_metric(row["lane_density_m_per_km2"], "lane_density_m_per_km2"),
            "accident_pressure": fmt_metric(row.get("accident_pressure_score", 0), "priority_score"),
            "bike_lane_shortage": fmt_metric(row.get("bike_lane_shortage_score", 0), "priority_score"),
            "pop_density": fmt_metric(row["pop_density"], "pop_density"),
        }
        for row in sorted_rows
    ]


def build_priority_table() -> dash_table.DataTable:
    return dash_table.DataTable(
        id="priority-table",
        data=table_data(MOCK_ROWS),
        columns=[
            {"name": "Rank", "id": "rank"},
            {"name": "Neighborhood", "id": "neighbourhood"},
            {"name": "Priority Score", "id": "priority_score"},
            {"name": "Accident Rate", "id": "accident_rate"},
            {"name": "Bike Lane Supply", "id": "lane_density"},
            {"name": "Accident Pressure", "id": "accident_pressure"},
            {"name": "Bike Lane Shortage", "id": "bike_lane_shortage"},
            {"name": "Population Density", "id": "pop_density"},
        ],
        row_selectable="single",
        selected_rows=[],
        page_size=8,
        sort_action="native",
        style_table={"height": "318px", "overflowY": "hidden", "overflowX": "hidden"},
        style_as_list_view=True,
        style_cell={
            "fontFamily": "Inter, Arial, sans-serif",
            "fontSize": "12px",
            "padding": "7px 8px",
            "whiteSpace": "normal",
            "height": "auto",
            "textAlign": "left",
            "border": "none",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
            "maxWidth": 0,
        },
        style_header={"fontWeight": "800", "backgroundColor": "#ffffff", "borderBottom": "1px solid #d9e2ef", "color": "#0f1f3d"},
        style_cell_conditional=[
            {"if": {"column_id": "rank"}, "width": "46px", "textAlign": "center"},
            {"if": {"column_id": "neighbourhood"}, "width": "22%"},
            {"if": {"column_id": "priority_score"}, "width": "90px", "textAlign": "center"},
            {"if": {"column_id": "accident_pressure"}, "width": "96px", "textAlign": "center"},
            {"if": {"column_id": "bike_lane_shortage"}, "width": "104px", "textAlign": "center"},
        ],
        style_data_conditional=[
            {"if": {"state": "selected"}, "backgroundColor": "#eaf3ff", "border": "1px solid #a7c9ff"},
        ],
        tooltip_header={
            "priority_score": "Priority: normalized 0-100 display score based on the final priority ranking",
            "accident_rate": "Accident Rate: accidents per 1,000 residents",
            "lane_density": "Bike Lane Supply: metres of bike lane per km²",
            "accident_pressure": "Accident Pressure: normalized 0-100 display score",
            "bike_lane_shortage": "Bike Lane Shortage: normalized 0-100 display score",
            "pop_density": "Population Density: residents per km²",
        },
        tooltip_delay=0,
        tooltip_duration=None,
    )


def selected_row_from_name(name: str | None, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if name:
        for row in rows:
            if row["neighbourhood"] == name:
                return row
    return next((row for row in rows if row["neighbourhood"] == DEFAULT_SELECTED_NEIGHBOURHOOD), rows[0])


def selected_row_or_none(name: str | None, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not name:
        return None
    for row in rows:
        if row["neighbourhood"] == name:
            return row
    return None


def selected_feature_lines(selected_code: str) -> tuple[list[float], list[float]]:
    for feature in NEIGHBOURHOOD_GEOJSON["features"]:
        if feature["properties"]["BUURTCODE"] != selected_code:
            continue
        coordinates = feature["geometry"]["coordinates"]
        ring = coordinates[0] if feature["geometry"]["type"] == "Polygon" else coordinates[0][0]
        return [point[0] for point in ring], [point[1] for point in ring]
    return [], []


def selected_feature_bounds(selected_code: str) -> tuple[float, float, float, float] | None:
    for feature in NEIGHBOURHOOD_GEOJSON["features"]:
        if feature["properties"]["BUURTCODE"] != selected_code:
            continue
        geometry = feature["geometry"]
        rings = geometry["coordinates"] if geometry["type"] == "Polygon" else [ring for polygon in geometry["coordinates"] for ring in polygon]
        points = [point for ring in rings for point in ring]
        if not points:
            return None
        lon_values = [point[0] for point in points]
        lat_values = [point[1] for point in points]
        return min(lon_values), min(lat_values), max(lon_values), max(lat_values)
    return None


def map_zoom_for_bounds(bounds: tuple[float, float, float, float]) -> float:
    min_lon, min_lat, max_lon, max_lat = bounds
    span = max(max_lon - min_lon, max_lat - min_lat)
    if span < 0.01:
        return 14
    if span < 0.025:
        return 13
    return 12


def lane_trace_points(lanes_df: pd.DataFrame) -> tuple[list[float | None], list[float | None], list[str | None]]:
    lon_values: list[float | None] = []
    lat_values: list[float | None] = []
    hover_text: list[str | None] = []
    for _, lane in lanes_df.iterrows():
        geometry = lane.get("geometry_obj")
        if not isinstance(geometry, dict):
            continue
        if geometry.get("type") == "LineString":
            lines = [geometry.get("coordinates", [])]
        elif geometry.get("type") == "MultiLineString":
            lines = geometry.get("coordinates", [])
        else:
            continue
        name = lane.get("name") or lane.get("ds4_name") or "Unknown"
        highway = lane.get("highway") or lane.get("ds4_highway") or "Unknown"
        surface = lane.get("surface") or lane.get("ds4_surface") or "Unknown"
        length = fmt_number(lane.get("intersected_length_m"), 2)
        text = (
            "Bike lane segment<br>"
            f"Name: {name}<br>"
            f"Type: {highway}<br>"
            f"Surface: {surface}<br>"
            f"Length in neighbourhood: {length} m"
        )
        for line in lines:
            for point in line:
                if len(point) < 2:
                    continue
                lon_values.append(point[0])
                lat_values.append(point[1])
                hover_text.append(text)
            lon_values.append(None)
            lat_values.append(None)
            hover_text.append(None)
    return lon_values, lat_values, hover_text


def map_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    merged = rows_df(rows).copy()
    for col in METRIC_OPTIONS:
        merged[col] = pd.to_numeric(merged[col], errors="coerce")
    merged["has_score"] = merged["has_score"].astype(bool) if "has_score" in merged else True
    return merged


def build_priority_map(rows: list[dict[str, Any]], metric: str, selected_name: str | None = None) -> go.Figure:
    df = map_dataframe(rows)
    scored_df = df[df["has_score"]].copy()
    missing_df = df[~df["has_score"]].copy()
    label = METRIC_OPTIONS.get(metric, "Priority Score")
    choropleth = getattr(px, "choropleth_map", px.choropleth_mapbox)
    if scored_df.empty:
        scored_df = df.copy()
        scored_df[metric] = pd.NA
    fig = choropleth(
        scored_df,
        geojson=NEIGHBOURHOOD_GEOJSON,
        locations="BUURTCODE",
        featureidkey="properties.BUURTCODE",
        color=metric,
        color_continuous_scale=RISK_COLORS,
        opacity=0.78,
        center={"lat": 51.44, "lon": 5.48},
        zoom=10.4,
        hover_name="neighbourhood",
        custom_data=["priority_score", "accident_rate_per_1000_residents", "lane_density_m_per_km2", "accident_pressure_score", "bike_lane_shortage_score", "pop_density"],
    )
    if not missing_df.empty:
        trace_class = getattr(go, "Choroplethmap", getattr(go, "Choroplethmapbox"))
        fig.add_trace(
            trace_class(
                geojson=NEIGHBOURHOOD_GEOJSON,
                locations=missing_df["BUURTCODE"],
                featureidkey="properties.BUURTCODE",
                z=[0] * len(missing_df),
                colorscale=[[0, "#e5e7eb"], [1, "#e5e7eb"]],
                marker_line_width=0.6,
                marker_line_color="#ffffff",
                showscale=False,
                text=missing_df["neighbourhood"],
                hovertemplate="<b>%{text}</b><br>No score / filtered out<extra></extra>",
            )
        )
    fig.update_traces(
        marker_line_width=0.9,
        marker_line_color="#ffffff",
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "Priority Score: %{customdata[0]}<br>"
            "Accident Rate: %{customdata[1]:.2f} per 1k<br>"
            "Bike Lane Supply: %{customdata[2]:,.2f} m/km²<br>"
            "Accident Pressure: %{customdata[3]:.0f} / 100<br>"
            "Bike Lane Shortage: %{customdata[4]:.0f} / 100<br>"
            "Population Density: %{customdata[5]:,.2f} /km²<extra></extra>"
        ),
    )
    selected = selected_row_from_name(selected_name, rows) if selected_name else None
    lon, lat = selected_feature_lines(selected["BUURTCODE"]) if selected else ([], [])
    if selected and lon and lat:
        fig.add_trace(go.Scattermap(lon=lon, lat=lat, mode="lines", line={"color": "#0f1f3d", "width": 3}, hoverinfo="skip", showlegend=False))
        lanes_df = get_bike_lanes_for_neighbourhood(selected["neighbourhood"])
        lane_lon, lane_lat, lane_text = lane_trace_points(lanes_df)
        if lane_lon and lane_lat:
            fig.add_trace(
                go.Scattermap(
                    lon=lane_lon,
                    lat=lane_lat,
                    text=lane_text,
                    mode="lines",
                    line={"color": "#0b5cad", "width": 2},
                    opacity=0.82,
                    hovertemplate="%{text}<extra></extra>",
                    showlegend=False,
                )
            )
    fig.update_layout(
        autosize=True,
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        paper_bgcolor="white",
        coloraxis_colorbar={"title": "Priority", "thickness": 12, "len": 0.32, "x": 0.02, "y": 0.18, "xanchor": "left", "yanchor": "bottom", "tickvals": [0, 50, 100], "ticktext": ["0", "50", "100"]},
    )
    if selected:
        bounds = selected_feature_bounds(selected["BUURTCODE"])
        if bounds:
            min_lon, min_lat, max_lon, max_lat = bounds
            fig.update_layout(
                map_center={"lat": (min_lat + max_lat) / 2, "lon": (min_lon + max_lon) / 2},
                map_zoom=map_zoom_for_bounds(bounds),
            )
    if hasattr(fig.layout, "map"):
        fig.update_layout(map_style="carto-positron")
    else:
        fig.update_layout(mapbox_style="carto-positron")
    return fig


def chart_layout(fig: go.Figure, showlegend: bool = False) -> go.Figure:
    fig.update_layout(
        height=230,
        margin=dict(l=36, r=14, t=36, b=44),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=10, color="#0f1f3d", family="Inter, Arial, sans-serif"),
        showlegend=showlegend,
        legend=dict(orientation="h", yanchor="bottom", y=1.12, xanchor="center", x=0.5, font=dict(size=9)),
    )
    fig.update_xaxes(automargin=True, tickangle=-45, gridcolor="#edf2f7")
    fig.update_yaxes(automargin=True, gridcolor="#edf2f7")
    return fig


def accident_chart(rows: list[dict[str, Any]]) -> go.Figure:
    df = rows_df(scored_rows(rows) or rows).sort_values("accident_rate_per_1000_residents", ascending=False).head(8)
    colors = [category_color(score) for score in df["priority_score"]]
    fig = px.bar(df, x="neighbourhood", y="accident_rate_per_1000_residents", color_discrete_sequence=colors)
    fig.update_traces(marker_color=colors, hovertemplate="%{x}<br>%{y:.1f}<extra></extra>")
    fig.add_hline(y=df["accident_rate_per_1000_residents"].mean(), line_dash="dash", line_color="#7aa0d8", annotation_text="City Avg", annotation_font_size=9)
    fig.update_yaxes(title="Accident rate /1k residents")
    fig.update_xaxes(title=None)
    return chart_layout(fig)


def infrastructure_chart(rows: list[dict[str, Any]]) -> go.Figure:
    df = rows_df(scored_rows(rows) or rows).sort_values("gap_score", ascending=False).head(8)
    fig = go.Figure()
    fig.add_bar(name="Accident pressure", x=df["neighbourhood"], y=df["accident_pressure_score"], marker_color="#e53935")
    fig.add_bar(name="Bike lane shortage", x=df["neighbourhood"], y=df["bike_lane_shortage_score"], marker_color="#3f6fc8")
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="Relative score", range=[0, 115])
    fig.update_xaxes(title=None)
    return chart_layout(fig, showlegend=True)


def lane_vs_accident_chart(rows: list[dict[str, Any]]) -> go.Figure:
    df = rows_df(scored_rows(rows) or rows).sort_values("gap_score", ascending=False).head(8)
    fig = px.scatter(df, x="lane_density_m_per_km2", y="accident_rate_per_1000_residents", color="priority_score", color_continuous_scale=RISK_COLORS, hover_name="neighbourhood")
    fig.update_traces(marker=dict(size=8, line=dict(width=1, color="#ffffff")))
    if len(df) >= 2:
        x0 = df["lane_density_m_per_km2"].min()
        x1 = df["lane_density_m_per_km2"].max()
        y0 = df.loc[df["lane_density_m_per_km2"].idxmin(), "accident_rate_per_1000_residents"]
        y1 = df.loc[df["lane_density_m_per_km2"].idxmax(), "accident_rate_per_1000_residents"]
        fig.add_trace(go.Scatter(x=[x0, x1], y=[y0, y1], mode="lines", line=dict(color="#7aa0d8", dash="dash", width=1.5), hoverinfo="skip", showlegend=False))
    fig.update_layout(coloraxis_showscale=False)
    fig.update_xaxes(title="Bike lane density (m/km²)")
    fig.update_yaxes(title="Accident rate /1k residents")
    return chart_layout(fig)


def density_bubble_chart(rows: list[dict[str, Any]]) -> go.Figure:
    df = rows_df(scored_rows(rows) or rows).sort_values("gap_score", ascending=False).head(8)
    fig = px.scatter(
        df,
        x="pop_density",
        y="lane_density_m_per_km2",
        size="accident_rate_per_1000_residents",
        color="priority_score",
        color_continuous_scale=RISK_COLORS,
        size_max=28,
        hover_name="neighbourhood",
    )
    fig.update_traces(marker=dict(line=dict(width=1, color="#ffffff")))
    fig.update_layout(coloraxis_showscale=False)
    fig.update_xaxes(title="Population density (residents/km²)")
    fig.update_yaxes(title="Bike lane density (m/km²)")
    return chart_layout(fig)


def build_chart_card(title: str, subtitle: str, graph_id: str, figure: go.Figure) -> html.Div:
    return html.Div(
        [
            html.Div([section_title(title), html.P(subtitle, className="chart-subtitle")], className="chart-card-head"),
            dcc.Graph(id=graph_id, figure=figure, config={"displayModeBar": False, "responsive": True}, style={"height": "230px", "width": "100%"}),
        ],
        className="dashboard-card chart-card",
    )


def build_insight_strip(rows: list[dict[str, Any]]) -> html.Div:
    top_names = [row["neighbourhood"] for row in sorted(scored_rows(rows), key=lambda item: item.get("gap_score", item["priority_score"]), reverse=True)[:3]]
    text = "Highest priority overlap: " + ", ".join(top_names) if top_names else "Highest priority overlap: N/A"
    return html.Div([html.Span("!", className="insight-icon"), html.Span(text)], className="insight-strip")


def priority_label(score: float) -> str:
    if score >= 70:
        return "High priority"
    if score >= 50:
        return "Medium priority"
    return "Low priority"


def selected_metric_card(label: str, unit: str | None, value: str, compact: bool = False, note: str | None = None) -> html.Div:
    label_children: list[Any] = [label]
    if unit:
        label_children.append(html.Span(unit, className="metric-unit"))
    return html.Div(
        [
            html.Div(label_children, className="metric-label"),
            html.Div(value, className=f"metric-value{' compact' if compact else ''}"),
            html.Div(note, className="metric-note") if note else None,
        ],
        className="metric-card",
    )


def build_selected_card(row: dict[str, Any], rows: list[dict[str, Any]]) -> html.Div:
    return html.Div(
        [
            html.Div([html.Span("Selected Neighbourhood"), html.Span("i", className="info-dot")], className="selected-panel-header"),
            html.Div(
                [
                    html.Div("PIN", className="pin-icon"),
                    html.Div(
                        [
                            html.H3(row["neighbourhood"], className="selected-name"),
                            html.Div(f"District: {row['district']}", className="selected-district"),
                        ],
                    ),
                ],
                className="selected-identity",
            ),
            html.Div(
                [
                    selected_metric_card("Priority Score", None, f"{fmt_metric(row['priority_score'], 'priority_score')} / 100"),
                    selected_metric_card("Accident Rate", "(per 1k)", fmt_card_metric(row["accident_rate_per_1000_residents"], "accident_rate_per_1000")),
                    selected_metric_card("Bike Lane Supply", "(m/km²)", fmt_card_metric(row["lane_density_m_per_km2"], "lane_density_m_per_km2")),
                    selected_metric_card("Accident Pressure", "(/100)", fmt_metric(row.get("accident_pressure_score", 0), "priority_score")),
                    selected_metric_card("Bike Lane Shortage", "(/100)", fmt_metric(row.get("bike_lane_shortage_score", 0), "priority_score")),
                    selected_metric_card("Population Density", "(per km²)", fmt_metric(row["pop_density"], "pop_density"), compact=True),
                ],
                className="metric-grid",
            ),
        ]
    )


def build_empty_selected_card() -> html.Div:
    return html.Div(
        [
            html.Div([html.Span("Selected Neighbourhood"), html.Span("i", className="info-dot")], className="selected-panel-header"),
            html.Div(
                [
                    html.Div("PIN", className="pin-icon muted"),
                    html.Div(
                        [
                            html.H3("No selection", className="selected-name empty"),
                            html.Div("Click a table row or map polygon.", className="selected-district"),
                        ],
                    ),
                ],
                className="selected-identity empty",
            ),
            html.Div(
                [
                    selected_metric_card("Priority Score", None, "-"),
                    selected_metric_card("Accident Rate", "(per 1k)", "-"),
                    selected_metric_card("Bike Lane Supply", "(m/km²)", "-"),
                    selected_metric_card("Accident Pressure", "(/100)", "-"),
                    selected_metric_card("Bike Lane Shortage", "(/100)", "-"),
                    selected_metric_card("Population Density", "(per km²)", "-"),
                ],
                className="metric-grid empty",
            ),
        ]
    )


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], title="Eindhoven Cycling Dashboard")
server = app.server

app.layout = html.Div(
    [
        dcc.Store(id="selected-neighbourhood-store", data=None),
        dcc.Store(id="map-selected-neighbourhood-store", data=None),
        build_header(),
        html.Div(id="kpi-grid", className="kpi-grid", children=build_kpi_cards(MOCK_ROWS)),
        html.Div(
            [
                html.Div(
                    [
                        section_title("Priority Score by Neighborhood"),
                        dcc.Graph(id="priority-map", figure=build_priority_map(MAP_ROWS, "priority_score", None), config={"displayModeBar": False, "responsive": True}, style={"height": "350px", "width": "100%"}),
                    ],
                    className="dashboard-card map-card",
                ),
                html.Div(
                    [
                        html.Div([section_title("Top Priority Neighborhoods"), html.P("Click a row to update the Selected Neighborhood panel.", className="table-subtitle")], className="table-head"),
                        build_priority_table(),
                        html.Div("Showing top 15 scored neighbourhoods", id="table-footer", className="table-footer"),
                    ],
                    className="dashboard-card table-card",
                ),
                html.Div(id="selected-neighbourhood-card-body", className="dashboard-card selected-card"),
            ],
            className="main-grid",
        ),
        html.Div(
            [
                build_chart_card("Accident Rate by Neighbourhood", "Cycling accidents per 1,000 residents, 2024", "accident-chart", accident_chart(MOCK_ROWS)),
                build_chart_card("Why These Neighbourhoods Are Prioritised", "Relative accident pressure and bike lane shortage", "infrastructure-chart", infrastructure_chart(MOCK_ROWS)),
                build_chart_card("Bike Lane Density vs Accident Rate", "Each point represents one neighbourhood", "lane-accident-chart", lane_vs_accident_chart(MOCK_ROWS)),
                build_chart_card("Population Density vs Bike Lane Density", "Bubble size = accident rate per 1,000 residents", "density-bubble-chart", density_bubble_chart(MOCK_ROWS)),
            ],
            className="chart-grid",
        ),
        html.Div(id="insight-strip-container", children=build_insight_strip(MOCK_ROWS)),
    ],
    className="page",
)


@app.callback(
    Output("district-filter", "value"),
    Output("map-metric-filter", "value"),
    Output("selected-neighbourhood-store", "data", allow_duplicate=True),
    Output("map-selected-neighbourhood-store", "data", allow_duplicate=True),
    Input("reset-filters", "n_clicks"),
    prevent_initial_call=True,
)
def reset_filters(_: int | None):
    return "ALL", "priority_score", None, None


@app.callback(
    Output("priority-table", "data"),
    Output("priority-table", "selected_rows"),
    Output("kpi-grid", "children"),
    Output("accident-chart", "figure"),
    Output("infrastructure-chart", "figure"),
    Output("lane-accident-chart", "figure"),
    Output("density-bubble-chart", "figure"),
    Output("table-footer", "children"),
    Output("insight-strip-container", "children"),
    Input("district-filter", "value"),
)
def update_filtered_views(district: str):
    rows = filter_rows(district)
    data = table_data(rows)
    return (
        data,
        [],
        build_kpi_cards(rows),
        accident_chart(rows),
        infrastructure_chart(rows),
        lane_vs_accident_chart(rows),
        density_bubble_chart(rows),
        f"Showing top {min(15, len(scored_rows(rows)))} of {len(scored_rows(rows))} scored neighbourhoods",
        build_insight_strip(rows),
    )


@app.callback(
    Output("selected-neighbourhood-store", "data"),
    Output("map-selected-neighbourhood-store", "data"),
    Input("priority-table", "derived_virtual_data"),
    Input("priority-table", "selected_rows"),
    prevent_initial_call=True,
)
def update_selected_store(rows: list[dict[str, Any]] | None, selected_rows: list[int] | None):
    visible_rows = rows or table_data(MOCK_ROWS)
    if not visible_rows or not selected_rows:
        return None, None
    selected_index = selected_rows[0]
    selected_index = min(selected_index, len(visible_rows) - 1)
    selected_name = visible_rows[selected_index]["neighbourhood"]
    return selected_name, selected_name


@app.callback(
    Output("selected-neighbourhood-store", "data", allow_duplicate=True),
    Output("map-selected-neighbourhood-store", "data", allow_duplicate=True),
    Input("priority-map", "clickData"),
    prevent_initial_call=True,
)
def update_selected_from_map(click_data: dict[str, Any] | None):
    if not click_data or not click_data.get("points"):
        return dash.no_update, dash.no_update
    point = click_data["points"][0]
    buurtcode = point.get("location")
    selected_name = None
    if buurtcode:
        selected_name = next((row["neighbourhood"] for row in MAP_ROWS if row.get("BUURTCODE") == str(buurtcode)), None)
    if not selected_name:
        customdata = point.get("customdata") or []
        if customdata:
            selected_name = next((row["neighbourhood"] for row in MAP_ROWS if row.get("priority_score") == customdata[0]), None)
    if not selected_name:
        return dash.no_update, dash.no_update
    panel_name = selected_name if any(row["neighbourhood"] == selected_name for row in MOCK_ROWS) else dash.no_update
    return panel_name, selected_name


@app.callback(
    Output("selected-neighbourhood-card-body", "children"),
    Output("priority-map", "figure"),
    Input("selected-neighbourhood-store", "data"),
    Input("map-selected-neighbourhood-store", "data"),
    Input("district-filter", "value"),
    Input("map-metric-filter", "value"),
)
def update_selected_details(selected_name: str, map_selected_name: str | None, district: str, map_metric: str):
    rows = filter_rows(district)
    map_display_rows = filter_map_rows(district)
    selected = selected_row_or_none(selected_name, rows)
    selected_panel = build_selected_card(selected, rows) if selected else build_empty_selected_card()
    return selected_panel, build_priority_map(map_display_rows, map_metric, map_selected_name)


if __name__ == "__main__":
    app.run(debug=False, dev_tools_ui=False, dev_tools_props_check=False)
