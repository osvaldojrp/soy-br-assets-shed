import plotly.express as px
import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
import geopandas as gpd
import pandas as pd
import base64
from io import BytesIO
import zipfile

# Create a Dash app
app = dash.Dash(__name__)
server = app.server


# goejson with limits of municipalities in Brazil
geo = gpd.read_file("BR_Municipios_2019_TRASEID_simplified.shp",
                    keep_default_na=True,
                    )
geo = (geo[['Geocod', 'geometry']]).rename(columns={'Geocod': 'origin_cod'})

# supply shed area: soy assets in Brazil
supply_shed = pd.read_csv("soy_supply_shed_trase_2020_threshold_95%.csv",
                          sep=";",
                          keep_default_na=True
                          )
supply_shed = supply_shed.merge(geo, on='origin_cod', how='left')
supply_shed = gpd.GeoDataFrame(supply_shed, geometry='geometry')

# risk for each asset (silo) in Brazil
asset_risk = pd.read_csv("soy_asset_risk_trase_2020_threshold_95%.csv",
                         sep=";",
                         keep_default_na=True
                         )
asset_risk = gpd.GeoDataFrame(
    asset_risk,
    geometry=gpd.points_from_xy(asset_risk["destination_long"], asset_risk["destination_lat"]),
)
risk_color = {
    "Negligible": "#BBFFEC",
    "At-risk": "#FF6A5F",
}
asset_risk["marker_color"] = asset_risk["asset_risk"].map(risk_color)

# state boundaries
state = gpd.read_file("estados_2010.shp",
                      keep_default_na=True,
                      )

app.layout = html.Div(
    style={"fontFamily": "DM Sans Medium"},
    children=[
        html.Hr(
            style={
                "borderWidth": "1.5pt",
                "borderColor": "#FF6A5F",
                "fill": "true",
                "marginTop": "5px",
                "marginBottom": "0",
            }
        ),
        html.Div(
            className="card",
            style={
                "background": "linear-gradient(to bottom, #BBFFEC, #FFFFFF)",
                "color": "#000000",
                "padding": "20px",
                "marginBottom": "0px",
            },
            children=[
                html.H2(
                    "Soy deforestation risk at asset level for storage facilities in Brazil",
                    className="card-title",
                    style={
                        "fontFamily": "DM Sans Medium",
                        "fontSize": "24px",
                        "color": "#000000",
                    },
                ),
                html.P(
                    "Deforestation risk categorization of soy silos in Brazil for the year 2020, considering all "
                    "silos presented in the Trase database (silos assigned to a given branch in Trase). The risk "
                    "categorization is carried out in two steps: first, we identify municipalities more likely to "
                    "provide production to a given silo based on transportation cost by road and branch assignment in "
                    "Trase; secondly, we classify deforestation risk based on the risk status of each providing "
                    "municipality and the respective soy volume produced by them. Areas 'at-risk', contribute to 95% "
                    "of the national soy deforestation in 2020 (soy occupying areas deforested between 2015-2019). "
                    "Click 'download' to access the original data for the selected area.",
                    className="card-description",
                    style={
                        "fontFamily": "DM Sans",
                        "fontSize": "16px",
                        "color": "#000000",
                        "fontWeight": "normal",
                    },
                ),
            ],
        ),
        html.Div(
            className="row", children=[
                html.Div(className='six columns', children=[
                    html.Label("Destination Municipality", style={"fontFamily": "DM Sans Medium"}),
                    dcc.Dropdown(
                        id='destination-mun-dropdown',
                        options=[{
                            'label': mun,
                            'value': mun
                        } for mun in supply_shed['destination_mun'].unique()],
                        value=['UBERLANDIA'],  # Default municipalities of destination (as a list)
                        multi=True,  # Allow multiple selections
                        placeholder='Destination Municipality',
                        style={"position": "relative", "left": "0"},
                    )], style=dict(width='50%'))
                , html.Div(className='six columns', children=[
                    html.Label("Destination Company", style={"fontFamily": "DM Sans Medium"}),
                    dcc.Dropdown(
                        id='destination-company-dropdown',
                        options=[{
                            'label': company,
                            'value': company
                        } for company in supply_shed['destination_company'].unique()],
                        value=['all'],  # Default value to select all companies (as a list)
                        multi=True,  # Allow multiple selections
                        placeholder='Destination Company',
                        style={"position": "relative", "right": "0"},
                    )], style=dict(width='50%')),
            ], style=dict(display='flex'),
        ),
        html.Div(
            className="download_link", children=[
                html.Div(style={'height': '5px'}),
                html.A(html.Button('Download CSV'), id='download-link')
            ]
        ),
        dcc.Graph(
            id="choropleth-graph", responsive='auto', style={
                'height': 700,
                'width': '100%',
                "display": "block",
                "margin-left": 0,
                "margin-right": 0,
            }
        )
    ],
)


# define map data and layout
def create_choropleth_figure(supply_shed, asset_risk):
    state_trace = go.Choropleth(
        geojson=state.geometry.__geo_interface__,
        locations=state.index,  # Use the index of the GeoDataFrame as locations
        z=[0] * len(state),  # Specify a constant value of 0 for all locations (for single fill color)
        colorscale=[[0, "#E2EAE7"], [1, "#E2EAE7"]],  # Single fill color #BECFC9
        showscale=False,  # Hide the color scale legend
        marker=dict(line=dict(color="white", width=1)),  # White borders with width 1
        name="states_trace",
    )

    # Create the main Plotly figure
    fig = go.Figure()

    # Add the choropleth_trace as the first trace (in the back) to the figure
    fig.add_trace(state_trace)
    fig.update_traces(
        selector=dict(name="states_trace"),
        hoverinfo="skip"
    )
    fig.update_geos(selector=dict(name="states_trace"),
                    fitbounds='geojson',
                    lonaxis_range=[-100, -10],
                    lataxis_range=[-45, 10]
                    )

    # Create the Plotly Express choropleth trace
    px_choropleth_trace = px.choropleth(
        data_frame=supply_shed,
        locations=supply_shed.index,
        color="risk_score",
        color_discrete_map={
            "Negligible": "#BBFFEC",
            "At-risk": "#FF6A5F",
        },
        geojson=supply_shed.geometry.__geo_interface__,
        scope="south america",
        center={"lat": -15, "lon": -55},
        hover_data=[
            "origin_mun",
            "origin_uf",
            "origin_biome",
            "destination_mun",
            "destination_state",
            "destination_biome"
        ],
        title='basemap'
    )

    # Manually set the hovertemplate for the px_choropleth_trace
    hovertemplate_px_choropleth = (
        "<b><span style='font-family: DM Sans Medium; color: #31464E; font-size: 16px'>%{customdata[0]}</span></b><br><br>"
        "<span style='position: relative;'>"
        "<span style='font-family: DM Sans; color: #828F94; font-size: 12px;'>Origin state</span><br>"
        "<span style='font-family: DM Sans Medium; color: #31464E;'>%{customdata[1]}</span><br><br>"
        "<span style='font-family: DM Sans; color: #828F94; font-size: 12px;'>Origin biome</span><br>"
        "<span style='font-family: DM Sans Medium; color: #31464E;'>%{customdata[2]}</span><br><br>"
        "<span style='font-family: DM Sans; color: #828F94; font-size: 12px;'>Destination mun.</span><br>"
        "<span style='font-family: DM Sans Medium; color: #31464E;'>%{customdata[3]}</span><br><br>"
        "<span style='font-family: DM Sans; color: #828F94; font-size: 12px;'>Destination state.</span><br>"
        "<span style='font-family: DM Sans Medium; color: #31464E;'>%{customdata[4]}</span><br><br>"
        "<span style='font-family: DM Sans; color: #828F94; font-size: 12px;'>Destination biome.</span><br>"
        "<span style='font-family: DM Sans Medium; color: #31464E;'>%{customdata[5]}</span>"
        "</span>"
        "<extra></extra>"
    )

    # Set the hovertemplate for the px_choropleth_trace
    px_choropleth_trace.update_traces(hovertemplate=hovertemplate_px_choropleth,
                                      marker_line_width=0.5,
                                      marker_line_color="white",
                                      hoverlabel=dict(bgcolor="#BBFFEC"),
                                      )

    # Add the individual traces from the Plotly Express choropleth figure to the main figure
    for trace in px_choropleth_trace.data:
        fig.add_trace(trace)

    fig.update_geos(fitbounds="locations",
                    lonaxis_range=[-100, -10],
                    lataxis_range=[-45, 10])

    hovertemplate_asset = (
        "<b><span style='font-family: DM Sans Medium; color: #31464E; font-size: 16px'>%{customdata[0]}</span></b><br><br>"
        "<span style='position: relative;'>"
        "<span style='font-family: DM Sans; color: #828F94; font-size: 12px;'>CNPJ</span><br>"
        "<span style='font-family: DM Sans Medium; color: #31464E;'>%{customdata[1]}</span><br><br>"
        "<span style='font-family: DM Sans; color: #828F94; font-size: 12px;'>Latitude:</span><br>"
        "<span style='font-family: DM Sans Medium; color: #31464E;'>%{customdata[2]}</span><br><br>"
        "<span style='font-family: DM Sans; color: #828F94; font-size: 12px;'>Longitude:</span><br>"
        "<span style='font-family: DM Sans Medium; color: #31464E;'>%{customdata[3]}</span><br><br>"
        "<span style='font-family: DM Sans; color: #828F94; font-size: 12px;'>Associated branches.</span><br>"
        "<span style='font-family: DM Sans Medium; color: #31464E;'>%{customdata[4]}</span><br><br>"
        "<span style='font-family: DM Sans; color: #828F94; font-size: 12px;'>Risk score.</span><br>"
        "<span style='font-family: DM Sans Medium; color: #31464E;'>%{customdata[5]}</span><br><br>"
        "</span>"
        "<extra></extra>"
    )

    asset_risk_trace = go.Scattergeo(
        lat=asset_risk["destination_lat"],
        lon=asset_risk["destination_long"],
        mode="markers",
        marker=dict(size=6, color=asset_risk["marker_color"], line=dict(color="black", width=0.5)),
        customdata=asset_risk[['destination_company',
                               'destination_cnpj',
                               'destination_lat',
                               'destination_long',
                               'destination_dt',
                               'asset_risk']],
        hovertemplate=hovertemplate_asset,
        hoverlabel=dict(bgcolor="#BBFFEC"),
        showlegend=False
    )
    fig.add_trace(asset_risk_trace)

    # Set the width of the map to a larger value, e.g., 1000 pixels
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        geo=dict(
            showframe=False,
            showcoastlines=False,
            showocean=False,
            showcountries=False,
            showland=False,
        ),
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            itemclick="toggleothers",
            font=dict(family="DM Sans", size=14, color="#839A8C"),
            title="Risk categories",
            title_font={"size": 14, "color": "#839A8C", "family": "DM Sans Medium"},
            bgcolor="rgba(0,0,0,0)",
        ),
    )

    return fig

@app.callback(
    [Output('destination-company-dropdown', 'options'),
     Output('destination-company-dropdown', 'value')],
    [Input('destination-mun-dropdown', 'value')]
)
def update_destination_company_dropdown(mun):
    # Filter the supply_shed DataFrame based on the selected municipalities
    if mun and 'all' not in mun:
        supply_shed_filtered = supply_shed[supply_shed['destination_mun'].isin(mun)]
    else:
        supply_shed_filtered = supply_shed

    # Get the unique companies in the filtered supply_shed DataFrame
    unique_companies = supply_shed_filtered['destination_company'].unique()

    # Create a list of dictionaries with 'label' and 'value' keys for the dropdown options
    options = [{'label': 'All Companies', 'value': 'all'}] + [{'label': company, 'value': company} for company in unique_companies]

    # Set the default value for destination-company-dropdown to ['all'] if all companies are selected, else set to []
    value = ['all'] if len(unique_companies) > 1 else []

    return options, value


@app.callback(
    Output('choropleth-graph', 'figure'),
    [
        Input('destination-mun-dropdown', 'value'),
        Input('destination-company-dropdown', 'value'),
    ],
)
def update_choropleth_map(mun, company):
    # Check if no municipality is selected in the "Destination Municipality" dropdown
    if not mun:
        mun = supply_shed['destination_mun'].unique()

    # Filter the supply_shed and asset_risk DataFrames based on dropdown selections
    supply_shed_filtered = supply_shed[supply_shed['destination_mun'].isin(mun)]

    # Convert company to a list if it's a single value
    if isinstance(company, str):
        company = [company]

    if company and 'all' not in company:
        supply_shed_filtered = supply_shed_filtered[supply_shed_filtered['destination_company'].isin(company)]

    asset_risk_filtered = asset_risk[asset_risk['destination_mun'].isin(mun)]

    # Convert company to a list if it's a single value
    if isinstance(company, str):
        company = [company]

    if company and 'all' not in company:
        asset_risk_filtered = asset_risk_filtered[asset_risk_filtered['destination_company'].isin(company)]

    # Create a new choropleth map with the filtered DataFrames
    updated_fig = create_choropleth_figure(supply_shed_filtered, asset_risk_filtered)

    # Set the value of the destination-company-dropdown to the selected company (or all companies)
    return updated_fig


@app.callback(
    Output('download-link', 'href'),
    Output('download-link', 'download'),
    [
        Input('destination-mun-dropdown', 'value'),
        Input('destination-company-dropdown', 'value'),
    ],
)
def update_download_link(mun, company):
    # Filter the supply_shed and asset_risk DataFrames based on dropdown selections
    supply_shed_filtered = supply_shed[supply_shed['destination_mun'].isin(mun)]
    supply_shed_filtered = (supply_shed_filtered[['origin_cod',
                                                  'origin_mun',
                                                  'origin_uf',
                                                  'origin_biome',
                                                  'origin_lat',
                                                  'origin_long',
                                                  'destination_cod',
                                                  'destination_mun',
                                                  'destination_state',
                                                  'destination_biome',
                                                  'destination_lat',
                                                  'destination_long',
                                                  'destination_cnpj',
                                                  'destination_company',
                                                  'destination_dt',
                                                  'risk_score']]).rename(
        columns={'origin_cod': 'Origin municipality Trase ID (IBGE)',
                 'origin_mun': 'Origin municipality',
                 'origin_uf': 'Origin state',
                 'origin_biome': 'Origin biome',
                 'origin_lat': 'Origin latitude',
                 'origin_long': 'Origin longitude',
                 'destination_cod': 'Destination municipality Trase ID (IBGE)',
                 'destination_mun': 'Destination municipality',
                 'destination_state': 'Destination state',
                 'destination_biome': 'Destination biome',
                 'destination_lat': 'Destination latitude',
                 'destination_long': 'Destination longitude',
                 'destination_cnpj': 'Destination CNPJ',
                 'destination_company': 'Destination company',
                 'destination_dt': 'Destination (trase branch assignment)',
                 'risk_score': 'Risk score'})

    # Convert company to a list if 'all' is selected or multiple companies are selected
    if 'all' in company or len(company) > 1:
        company = supply_shed_filtered['Destination company'].unique()

    if 'all' not in company:
        supply_shed_filtered = supply_shed_filtered[supply_shed_filtered['Destination company'].isin(company)]

    asset_risk_filtered = asset_risk[asset_risk['destination_mun'].isin(mun)]
    asset_risk_filtered = (asset_risk_filtered[['destination_cod',
                                                'destination_mun',
                                                'destination_state',
                                                'destination_biome',
                                                'destination_lat',
                                                'destination_long',
                                                'destination_cnpj',
                                                'destination_company',
                                                'destination_dt',
                                                'asset_risk']]).rename(
        columns={'destination_cod': 'Mun. Trase ID (IBGE)',
                 'destination_mun': 'Municipality',
                 'destination_state': 'State',
                 'destination_biome': 'Biome',
                 'destination_lat': 'Latitude',
                 'destination_long': 'Longitude',
                 'destination_cnpj': 'Company CNPJ',
                 'destination_company': 'Company name',
                 'destination_dt': 'Related branch',
                 'asset_risk': 'Asset risk score'})

    # Convert company to a list if 'all' is selected or multiple companies are selected
    if 'all' in company or len(company) > 1:
        company = asset_risk_filtered['Company name'].unique()

    if 'all' not in company:
        asset_risk_filtered = asset_risk_filtered[asset_risk_filtered['Company name'].isin(company)]

    # Create BytesIO buffer to store the ZIP file
    zip_buffer = BytesIO()

    # Create a ZIP file and add the CSV data as individual files
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('supply_shed.csv', supply_shed_filtered.to_csv(index=False, encoding='utf-8'))
        zip_file.writestr('asset_risk.csv', asset_risk_filtered.to_csv(index=False, encoding='utf-8'))

    # Encode the ZIP file to base64
    zip_b64 = base64.b64encode(zip_buffer.getvalue()).decode()

    # Create download link for the ZIP file
    zip_href = f"data:application/zip;base64,{zip_b64}"

    return zip_href, "Asset_and_SupplyShed_data.zip"


if __name__ == "__main__":
    app.run_server(debug=False)
