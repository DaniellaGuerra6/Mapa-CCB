import geopandas as gpd
import folium
from folium.features import GeoJsonTooltip
import branca.colormap as cm
from shapely.ops import transform
import warnings
warnings.filterwarnings("ignore")

# -------------------------
# FUNCIONES
# -------------------------
def drop_z(geom):
    if geom is None:
        return None
    return transform(lambda x, y, z=None: (x, y), geom)

# -------------------------
# CARGA DE DATOS
# -------------------------
atlantico = gpd.read_file("MAPAS/MGN_2/DPTO_CNMBR_ATLÁNTICO.shp")
atlantico = atlantico.rename(columns={
    "MPIO_CCNCT": "COD_MUN",
    "MPIO_CNMBR": "NOM_MUN"
})
atlantico = atlantico[["COD_MUN", "NOM_MUN", "MPM", "geometry"]]

vias   = gpd.read_file("MAPAS/VIAS/Linea.shp")
puntos = gpd.read_file("MAPAS/PUNTOS/Puntos.shp")
nuevas = gpd.read_file("MAPAS/NUEVAS/Vías Nuevas.shp")

# Limpieza categorías
vias["Categoria"]   = vias["Categoria"].str.strip()
puntos["Categoria"] = puntos["Categoria"].str.strip()

# -------------------------
# REPROYECCIÓN OBLIGATORIA
# -------------------------
for gdf in [atlantico, vias, puntos, nuevas]:
    gdf.to_crs(epsg=4326, inplace=True)
    gdf["geometry"] = gdf["geometry"].apply(drop_z)

# -------------------------
# MAPA BASE
# -------------------------
centro = atlantico.to_crs(epsg=3116).geometry.centroid.to_crs(epsg=4326)

m = folium.Map(
    location=[centro.y.mean(), centro.x.mean()],
    zoom_start=10,
    tiles="CartoDB positron"
)

# -------------------------
# MUNICIPIOS (CAPA FIJA)
# -------------------------
folium.GeoJson(
    atlantico,
    name="Municipios",
    style_function=lambda x: {
        "fillColor": "#eeeeee",
        "color": "#444444",
        "weight": 1,
        "fillOpacity": 0.5
    },
    tooltip=GeoJsonTooltip(
        fields=["NOM_MUN"],
        aliases=["Municipio:"]
    )
).add_to(m)

# -------------------------
# MUNICIPIOS POR MPM (OPCIONAL)
# -------------------------
colormap = cm.LinearColormap(
    colors=["#ffffcc", "#41b6c4", "#0c2c84"],
    vmin=atlantico["MPM"].min(),
    vmax=atlantico["MPM"].max(),
    caption="MPM"
)

mpm_fg = folium.FeatureGroup(name="Municipios por MPM", show=False)

folium.GeoJson(
    atlantico,
    style_function=lambda x: {
        "fillColor": colormap(x["properties"]["MPM"]),
        "color": "black",
        "weight": 0.8,
        "fillOpacity": 0.7
    },
    tooltip=GeoJsonTooltip(
        fields=["NOM_MUN", "MPM"],
        aliases=["Municipio:", "MPM:"]
    )
).add_to(mpm_fg)

mpm_fg.add_to(m)
colormap.add_to(m)

# -------------------------
# NUEVAS RUTAS
# -------------------------
nuevas_fg = folium.FeatureGroup(name="Nuevas rutas", show=False).add_to(m)

folium.GeoJson(
    nuevas,
    style_function=lambda x: {
        "color": "#0055cc",
        "weight": 4
    },
    tooltip=GeoJsonTooltip(
        fields=["Nombre"],
        aliases=["Proyecto:"]
    )
).add_to(nuevas_fg)

# -------------------------
# CATEGORÍAS (BOX ÚNICO)
# -------------------------
CATEGORIA_COLORES = {
    "Ambiental y Gestión de del territorio": "#1b9e77",
    "Transporte": "#d95f02",
    "Social y cultural": "#7570b3",
    "Urbanismo y desarrollo metropolitano": "#e7298a"
}

for categoria, color in CATEGORIA_COLORES.items():

    fg = folium.FeatureGroup(
        name=categoria,
        show=False
    ).add_to(m)

    # ---- VÍAS ----
    subset_vias = vias[vias["Categoria"] == categoria]

    if not subset_vias.empty:
        folium.GeoJson(
            subset_vias,
            style_function=lambda x, col=color: {
                "color": col,
                "weight": 3
            },
            tooltip=GeoJsonTooltip(
                fields=["name"],
                aliases=["Proyecto:"]
            )
        ).add_to(fg)

    # ---- PUNTOS ----
    subset_puntos = puntos[puntos["Categoria"] == categoria]

    for _, row in subset_puntos.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=6,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            tooltip=row["name"]
        ).add_to(fg)

# -------------------------
# CONTROL DE CAPAS
# -------------------------
folium.LayerControl(
    collapsed=False
).add_to(m)


# Exportar
from datetime import datetime

filename = f"mapa_ccb_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
m.save(filename)