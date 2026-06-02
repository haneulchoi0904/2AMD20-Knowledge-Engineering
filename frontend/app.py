from __future__ import annotations

from typing import Any

import dash
from dash import Input, Output, State, dash_table, dcc, html
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px


KPI_DATA = [
    {"label": "Neighbourhoods", "value": "111", "note": "Total", "accent": "blue", "icon": "NB"},
    {"label": "Cycling Accidents", "value": "1,621", "note": "Total", "accent": "red", "icon": "!"},
    {"label": "Bike Lane Links", "value": "5,467", "note": "Total", "accent": "green", "icon": "LN"},
    {"label": "Parking Facilities", "value": "7", "note": "Total", "accent": "purple", "icon": "P"},
    {"label": "Priority Method", "value": "Composite Score", "note": "Active", "accent": "orange", "icon": "CS"},
]

PRIORITY_ROWS = [
    {
        "rank": 1,
        "buurtcode": "BU001",
        "neighbourhood": "Binnenstad",
        "district": "Centrum",
        "priority_score": 0.86,
        "accident_rate_per_1k": 8.4,
        "lane_density_m_per_km2": 620,
        "parking_capacity_per_1k": 18,
        "population_density_per_km2": 12520,
    },
    {
        "rank": 2,
        "buurtcode": "BU002",
        "neighbourhood": "Strijp",
        "district": "Strijp",
        "priority_score": 0.74,
        "accident_rate_per_1k": 6.1,
        "lane_density_m_per_km2": 710,
        "parking_capacity_per_1k": 24,
        "population_density_per_km2": 9800,
    },
    {
        "rank": 3,
        "buurtcode": "BU003",
        "neighbourhood": "Woensel-Noord",
        "district": "Woensel",
        "priority_score": 0.68,
        "accident_rate_per_1k": 5.7,
        "lane_density_m_per_km2": 680,
        "parking_capacity_per_1k": 21,
        "population_density_per_km2": 10240,
    },
    {
        "rank": 4,
        "buurtcode": "BU004",
        "neighbourhood": "Tongelre",
        "district": "Tongelre",
        "priority_score": 0.63,
        "accident_rate_per_1k": 4.9,
        "lane_density_m_per_km2": 720,
        "parking_capacity_per_1k": 27,
        "population_density_per_km2": 8710,
    },
    {
        "rank": 5,
        "buurtcode": "BU005",
        "neighbourhood": "Gestel",
        "district": "Gestel",
        "priority_score": 0.61,
        "accident_rate_per_1k": 4.5,
        "lane_density_m_per_km2": 750,
        "parking_capacity_per_1k": 29,
        "population_density_per_km2": 8120,
    },
    {
        "rank": 6,
        "buurtcode": "BU006",
        "neighbourhood": "Stratum",
        "district": "Stratum",
        "priority_score": 0.57,
        "accident_rate_per_1k": 4.1,
        "lane_density_m_per_km2": 790,
        "parking_capacity_per_1k": 31,
        "population_density_per_km2": 7550,
    },
    {
        "rank": 7,
        "buurtcode": "BU007",
        "neighbourhood": "Achtse Barrier",
        "district": "Woensel",
        "priority_score": 0.52,
        "accident_rate_per_1k": 3.8,
        "lane_density_m_per_km2": 830,
        "parking_capacity_per_1k": 34,
        "population_density_per_km2": 6980,
    },
    {
        "rank": 8,
        "buurtcode": "BU008",
        "neighbourhood": "Meerhoven",
        "district": "Strijp",
        "priority_score": 0.49,
        "accident_rate_per_1k": 3.5,
        "lane_density_m_per_km2": 860,
        "parking_capacity_per_1k": 36,
        "population_density_per_km2": 6410,
    },
    {
        "rank": 9,
        "buurtcode": "BU009",
        "neighbourhood": "Blixembosch",
        "district": "Woensel",
        "priority_score": 0.45,
        "accident_rate_per_1k": 3.2,
        "lane_density_m_per_km2": 910,
        "parking_capacity_per_1k": 39,
        "population_density_per_km2": 5880,
    },
    {
        "rank": 10,
        "buurtcode": "BU010",
        "neighbourhood": "Gennep",
        "district": "Gestel",
        "priority_score": 0.42,
        "accident_rate_per_1k": 2.9,
        "lane_density_m_per_km2": 940,
        "parking_capacity_per_1k": 42,
        "population_density_per_km2": 5320,
    },
]

QUERY_LIBRARY = {
    "Accident Hotspots": {
        "cypher": """MATCH (a:CyclingAccident)-[:OCCURRED_IN]->(n:Neighbourhood)
RETURN n.BUURTNAAM AS neighbourhood,
       count(a) AS accident_count
ORDER BY accident_count DESC
LIMIT 5;""",
        "rows": [
            {"neighbourhood": "Binnenstad", "accident_count": 54},
            {"neighbourhood": "Woensel-Noord", "accident_count": 48},
            {"neighbourhood": "Strijp", "accident_count": 42},
            {"neighbourhood": "Tongelre", "accident_count": 38},
            {"neighbourhood": "Gestel", "accident_count": 31},
        ],
        "value_col": "accident_count",
        "value_label": "Accident Count",
        "title": "Top 5 Accident Hotspots",
    },
    "Lane Deficit": {
        "cypher": """MATCH (n:Neighbourhood)
OPTIONAL MATCH (l:BikeLaneSegment)-[:PASSES_THROUGH]->(n)
RETURN n.BUURTNAAM AS neighbourhood,
       sum(l.length_m) / n.area_km2 AS lane_density
ORDER BY lane_density ASC
LIMIT 5;""",
        "rows": [
            {"neighbourhood": "Binnenstad", "lane_density": 620},
            {"neighbourhood": "Woensel-Noord", "lane_density": 680},
            {"neighbourhood": "Strijp", "lane_density": 710},
            {"neighbourhood": "Tongelre", "lane_density": 720},
            {"neighbourhood": "Gestel", "lane_density": 750},
        ],
        "value_col": "lane_density",
        "value_label": "Lane Density",
        "title": "Lowest Lane Density",
    },
    "Parking Deficit": {
        "cypher": """MATCH (n:Neighbourhood)
OPTIONAL MATCH (p:BikeParkingFacility)-[:LOCATED_IN]->(n)
RETURN n.BUURTNAAM AS neighbourhood,
       count(p) / (n.population / 1000.0) AS parking_capacity
ORDER BY parking_capacity ASC
LIMIT 5;""",
        "rows": [
            {"neighbourhood": "Binnenstad", "parking_capacity": 18},
            {"neighbourhood": "Woensel-Noord", "parking_capacity": 21},
            {"neighbourhood": "Strijp", "parking_capacity": 24},
            {"neighbourhood": "Tongelre", "parking_capacity": 27},
            {"neighbourhood": "Gestel", "parking_capacity": 29},
        ],
        "value_col": "parking_capacity",
        "value_label": "Parking Capacity",
        "title": "Lowest Parking Capacity",
    },
    "Combined Priority": {
        "cypher": """MATCH (n:Neighbourhood)
RETURN n.BUURTNAAM AS neighbourhood,
       n.priority_score AS priority_score
ORDER BY priority_score DESC
LIMIT 5;""",
        "rows": [
            {"neighbourhood": row["neighbourhood"], "priority_score": row["priority_score"]}
            for row in PRIORITY_ROWS
        ],
        "value_col": "priority_score",
        "value_label": "Priority Score",
        "title": "Top Combined Priority",
    },
}


def get_kpi_data() -> list[dict[str, Any]]:
    return KPI_DATA


def get_priority_data() -> list[dict[str, Any]]:
    return PRIORITY_ROWS


def get_query_result(query_type: str) -> dict[str, Any]:
    return QUERY_LIBRARY[query_type]


def section_title(text: str) -> html.Div:
    return html.Div([html.H2(text), html.Span("i", className="info-dot")], className="section-title")


def kpi_card(item: dict[str, str]) -> html.Div:
    return html.Div(
        [
            html.Div(item["icon"], className=f"kpi-icon {item['accent']}"),
            html.Div(
                [
                    html.Div(item["label"], className=f"kpi-label {item['accent']}"),
                    html.Div(item["value"], className="kpi-value"),
                    html.Div(item["note"], className="muted"),
                ],
                className="kpi-copy",
            ),
        ],
        className="dashboard-card kpi-card",
    )


def priority_table() -> dash_table.DataTable:
    rows = get_priority_data()[:8]
    display_rows = [
        {
            "rank": row["rank"],
            "neighbourhood": row["neighbourhood"],
            "priority_score": row["priority_score"],
            "accident_rate_per_1k": row["accident_rate_per_1k"],
            "lane_density_m_per_km2": row["lane_density_m_per_km2"],
            "parking_capacity_per_1k": row["parking_capacity_per_1k"],
        }
        for row in rows
    ]
    return dash_table.DataTable(
        id="priority-table",
        data=display_rows,
        columns=[
            {"name": "Rank", "id": "rank", "type": "numeric"},
            {"name": "Neighbourhood", "id": "neighbourhood"},
            {"name": "Priority Score", "id": "priority_score", "type": "numeric", "format": {"specifier": ".2f"}},
            {"name": "Accident Rate (per 1k)", "id": "accident_rate_per_1k", "type": "numeric"},
            {"name": "Lane Density (m/km2)", "id": "lane_density_m_per_km2", "type": "numeric"},
            {"name": "Parking Capacity (per 1k)", "id": "parking_capacity_per_1k", "type": "numeric"},
        ],
        row_selectable="single",
        selected_rows=[0],
        page_size=8,
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_as_list_view=True,
        style_cell={
            "fontFamily": "Inter, Arial, sans-serif",
            "fontSize": "13px",
            "padding": "10px 12px",
            "textAlign": "left",
            "whiteSpace": "normal",
            "height": "auto",
            "border": "1px solid #e6eaf0",
        },
        style_header={
            "backgroundColor": "#f8fafc",
            "fontWeight": "700",
            "color": "#0f172a",
            "border": "1px solid #e6eaf0",
        },
        style_data_conditional=[
            {
                "if": {"column_id": "priority_score"},
                "backgroundColor": "#fee2e2",
                "color": "#b91c1c",
                "fontWeight": "700",
                "textAlign": "center",
            },
            {
                "if": {"state": "selected"},
                "backgroundColor": "#eff6ff",
                "border": "1px solid #2563eb",
            },
        ],
    )


def all_priority_table() -> dash_table.DataTable:
    rows = get_priority_data()
    display_rows = [
        {
            "rank": row["rank"],
            "neighbourhood": row["neighbourhood"],
            "district": row["district"],
            "priority_score": row["priority_score"],
            "accident_rate_per_1k": row["accident_rate_per_1k"],
            "lane_density_m_per_km2": row["lane_density_m_per_km2"],
            "parking_capacity_per_1k": row["parking_capacity_per_1k"],
            "population_density_per_km2": row["population_density_per_km2"],
        }
        for row in rows
    ]
    return dash_table.DataTable(
        data=display_rows,
        columns=[
            {"name": "Rank", "id": "rank", "type": "numeric"},
            {"name": "Neighbourhood", "id": "neighbourhood"},
            {"name": "District", "id": "district"},
            {"name": "Priority Score", "id": "priority_score", "type": "numeric", "format": {"specifier": ".2f"}},
            {"name": "Accident Rate (per 1k)", "id": "accident_rate_per_1k", "type": "numeric"},
            {"name": "Lane Density (m/km2)", "id": "lane_density_m_per_km2", "type": "numeric"},
            {"name": "Parking Capacity (per 1k)", "id": "parking_capacity_per_1k", "type": "numeric"},
            {"name": "Population Density (per km2)", "id": "population_density_per_km2", "type": "numeric"},
        ],
        page_size=10,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto", "maxHeight": "62vh", "overflowY": "auto"},
        style_as_list_view=True,
        style_cell={
            "fontFamily": "Inter, Arial, sans-serif",
            "fontSize": "13px",
            "padding": "9px 10px",
            "textAlign": "left",
            "whiteSpace": "normal",
            "height": "auto",
            "border": "1px solid #e6eaf0",
        },
        style_header={"backgroundColor": "#f8fafc", "fontWeight": "700", "color": "#0f172a"},
        style_data_conditional=[
            {
                "if": {"column_id": "priority_score"},
                "backgroundColor": "#fee2e2",
                "color": "#b91c1c",
                "fontWeight": "700",
                "textAlign": "center",
            },
        ],
    )


def selected_metric(label: str, value: str) -> html.Div:
    return html.Div([html.Div(label, className="metric-label"), html.Div(value, className="metric-value")], className="metric-tile")


def make_indicator_fig(metric: str, title: str, selected_name: str) -> px.bar:
    df = pd.DataFrame(get_priority_data())
    colors = ["#ef4444" if name == selected_name else "#cbd5e1" for name in df["neighbourhood"]]
    fig = px.bar(df, x="neighbourhood", y=metric, title=title)
    fig.update_traces(marker_color=colors, hovertemplate="%{x}<br>%{y}<extra></extra>")
    fig.update_layout(
        height=220,
        margin=dict(l=42, r=12, t=38, b=65),
        autosize=False,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="#0f172a", family="Inter, Arial, sans-serif", size=11),
        title=dict(font=dict(size=13), x=0.5),
        showlegend=False,
    )
    fig.update_xaxes(title=None, tickangle=45, showgrid=False)
    fig.update_yaxes(title=None, gridcolor="#e6eaf0")
    return fig


def make_query_fig(query_type: str) -> px.bar:
    query = get_query_result(query_type)
    df = pd.DataFrame(query["rows"])
    value_col = query["value_col"]
    fig = px.bar(df, x=value_col, y="neighbourhood", orientation="h", title=query["title"])
    fig.update_traces(marker_color="#ef4444", hovertemplate="%{y}<br>%{x}<extra></extra>")
    fig.update_layout(
        height=190,
        margin=dict(l=98, r=12, t=34, b=35),
        autosize=False,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="#0f172a", family="Inter, Arial, sans-serif", size=11),
        title=dict(font=dict(size=12), x=0.5),
        showlegend=False,
    )
    fig.update_xaxes(title=query["value_label"], gridcolor="#e6eaf0")
    fig.update_yaxes(title=None, autorange="reversed")
    return fig


def query_table(query_type: str) -> dash_table.DataTable:
    query = get_query_result(query_type)
    df = pd.DataFrame(query["rows"])
    columns = [{"name": col.replace("_", " ").title(), "id": col} for col in df.columns]
    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=columns,
        page_size=5,
        style_table={"overflowX": "auto"},
        style_as_list_view=True,
        style_cell={
            "fontFamily": "Inter, Arial, sans-serif",
            "fontSize": "12px",
            "padding": "7px 9px",
            "textAlign": "left",
            "border": "1px solid #e6eaf0",
        },
        style_header={"backgroundColor": "#f8fafc", "fontWeight": "700", "color": "#0f172a"},
    )


def card(children: Any, class_name: str = "") -> html.Div:
    return html.Div(html.Div(children, className="card-inner"), className=f"dashboard-card {class_name}".strip())


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], title="Eindhoven Cycling Dashboard")
server = app.server

app.layout = dbc.Container(
    [
        html.Header(
            [
                html.Div(
                    [
                        html.Div("BI", className="brand-mark"),
                        html.Div(
                            [
                                html.H1("Eindhoven Cycling Infrastructure Prioritisation Dashboard"),
                                html.P(
                                    "A Neo4j-backed knowledge graph dashboard for data-driven cycling infrastructure planning."
                                ),
                            ]
                        ),
                    ],
                    className="header-title",
                ),
                html.Div("Last updated: May 12, 2025 10:24", className="timestamp-badge"),
            ],
            className="dashboard-header",
        ),
        html.Div([kpi_card(item) for item in get_kpi_data()], className="kpi-grid"),
        dbc.Row(
            [
                dbc.Col(
                    card(
                        [
                            html.Div(
                                [
                                    section_title("Top Priority Neighbourhoods"),
                                    dbc.Button("View all", id="open-priority-modal", color="primary", outline=True, size="sm"),
                                ],
                                className="card-title-row",
                            ),
                            priority_table(),
                        ],
                        "priority-card",
                    ),
                    lg=6,
                ),
                dbc.Col(
                    card(
                        [
                            section_title("Query Explorer"),
                            dcc.Dropdown(
                                id="query-type",
                                options=[{"label": key, "value": key} for key in QUERY_LIBRARY],
                                value="Accident Hotspots",
                                clearable=False,
                                className="query-dropdown",
                            ),
                            html.Pre(id="cypher-preview", className="cypher-box"),
                            dbc.Row(
                                [
                                    dbc.Col(html.Div(id="query-result-table"), md=5),
                                    dbc.Col(
                                        html.Div(
                                            dcc.Graph(
                                                id="query-result-chart",
                                                config={"displayModeBar": False, "responsive": False},
                                                style={"height": "190px", "width": "100%"},
                                            ),
                                            className="query-chart-box",
                                        ),
                                        md=7,
                                    ),
                                ],
                                className="g-3 align-items-center",
                            ),
                        ]
                    ),
                    lg=6,
                ),
            ],
            className="g-3 align-items-stretch dashboard-row",
        ),
        dbc.Row(
            [
                dbc.Col(card(html.Div(id="selected-neighbourhood-card"), "selected-card"), xl=3, lg=4, md=12),
                dbc.Col(
                    card(
                        [
                            section_title("Indicator Overview"),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        html.Div(
                                            dcc.Graph(
                                                id="accident-chart",
                                                config={"displayModeBar": False, "responsive": False},
                                                style={"height": "220px", "width": "100%"},
                                            ),
                                            className="chart-box",
                                        ),
                                        md=4,
                                    ),
                                    dbc.Col(
                                        html.Div(
                                            dcc.Graph(
                                                id="lane-chart",
                                                config={"displayModeBar": False, "responsive": False},
                                                style={"height": "220px", "width": "100%"},
                                            ),
                                            className="chart-box",
                                        ),
                                        md=4,
                                    ),
                                    dbc.Col(
                                        html.Div(
                                            dcc.Graph(
                                                id="parking-chart",
                                                config={"displayModeBar": False, "responsive": False},
                                                style={"height": "220px", "width": "100%"},
                                            ),
                                            className="chart-box",
                                        ),
                                        md=4,
                                    ),
                                ],
                                className="g-2",
                            ),
                        ]
                    ),
                    xl=9,
                    lg=8,
                    md=12,
                ),
            ],
            className="g-3 align-items-stretch dashboard-row",
        ),
        card(
            [
                section_title("Knowledge Graph Overview"),
                html.Div(
                    [
                        html.Div([html.Div("NB", className="kg-node blue"), html.Div("Neighbourhood"), html.Small("(111)")]),
                        html.Div([html.Div("OCCURRED_IN", className="kg-edge-label"), html.Div("1,621", className="kg-edge-count")], className="kg-edge"),
                        html.Div([html.Div("!", className="kg-node red"), html.Div("CyclingAccident"), html.Small("(1,621)")]),
                        html.Div([html.Div("LOCATED_IN", className="kg-edge-label"), html.Div("7", className="kg-edge-count")], className="kg-edge"),
                        html.Div([html.Div("P", className="kg-node purple"), html.Div("BikeParkingFacility"), html.Small("(7)")]),
                        html.Div([html.Div("PASSES_THROUGH", className="kg-edge-label"), html.Div("5,467", className="kg-edge-count")], className="kg-edge"),
                        html.Div([html.Div("LN", className="kg-node green"), html.Div("BikeLaneSegment"), html.Small("(5,467)")]),
                    ],
                    className="kg-flow",
                ),
            ],
            class_name="kg-card",
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("All Priority Neighbourhoods")),
                dbc.ModalBody(
                    [
                        html.P("Sorted by composite priority score.", className="modal-note"),
                        all_priority_table(),
                    ]
                ),
            ],
            id="priority-modal",
            size="xl",
            is_open=False,
            scrollable=True,
        ),
    ],
    fluid=True,
    className="page-shell",
)


def selected_row_from_table(derived_rows: list[dict[str, Any]] | None, selected_rows: list[int] | None) -> dict[str, Any]:
    visible_rows = derived_rows or priority_table().data
    selected_index = selected_rows[0] if selected_rows else 0
    visible_row = visible_rows[selected_index] if selected_index < len(visible_rows) else visible_rows[0]
    full_rows = {row["neighbourhood"]: row for row in get_priority_data()}
    return full_rows[visible_row["neighbourhood"]]


@app.callback(
    Output("selected-neighbourhood-card", "children"),
    Output("accident-chart", "figure"),
    Output("lane-chart", "figure"),
    Output("parking-chart", "figure"),
    Input("priority-table", "derived_virtual_data"),
    Input("priority-table", "selected_rows"),
)
def update_selected_neighbourhood(derived_rows: list[dict[str, Any]] | None, selected_rows: list[int] | None):
    row = selected_row_from_table(derived_rows, selected_rows)
    selected_card = html.Div(
        [
            section_title("Selected Neighbourhood"),
            html.Div(
                [
                    html.Div("PIN", className="selected-pin"),
                    html.Div([html.H3(row["neighbourhood"]), html.P(f"District: {row['district']}")]),
                ],
                className="selected-heading",
            ),
            html.Div(
                [
                    selected_metric("Accident Rate (per 1k)", f"{row['accident_rate_per_1k']:.1f}"),
                    selected_metric("Lane Density (m/km2)", f"{int(row['lane_density_m_per_km2']):,}"),
                    selected_metric("Parking Capacity (per 1k)", f"{int(row['parking_capacity_per_1k']):,}"),
                    selected_metric("Population Density (per km2)", f"{int(row['population_density_per_km2']):,}"),
                ],
                className="metric-grid",
            ),
        ]
    )
    selected_name = row["neighbourhood"]
    return (
        selected_card,
        make_indicator_fig("accident_rate_per_1k", "Accident Rate (per 1k)", selected_name),
        make_indicator_fig("lane_density_m_per_km2", "Lane Density (m/km2)", selected_name),
        make_indicator_fig("parking_capacity_per_1k", "Parking Capacity (per 1k)", selected_name),
    )


@app.callback(
    Output("cypher-preview", "children"),
    Output("query-result-table", "children"),
    Output("query-result-chart", "figure"),
    Input("query-type", "value"),
)
def update_query_explorer(query_type: str):
    query = get_query_result(query_type)
    return query["cypher"], query_table(query_type), make_query_fig(query_type)


@app.callback(
    Output("priority-modal", "is_open"),
    Input("open-priority-modal", "n_clicks"),
    State("priority-modal", "is_open"),
    prevent_initial_call=True,
)
def open_priority_modal(n_clicks: int | None, is_open: bool):
    if n_clicks:
        return not is_open
    return is_open


if __name__ == "__main__":
    app.run(debug=False, dev_tools_ui=False, dev_tools_props_check=False)
