"""
"""

# =====================================================
# IMPORTS
# =====================================================
import geopandas as gpd
import re
import pandas as pd
import folium
from folium.features import GeoJsonTooltip
import branca.colormap as cm
from shapely.ops import transform
from bs4 import BeautifulSoup
import re
import warnings
import matplotlib.cm as mpl_cm
warnings.filterwarnings("ignore")

# -------------------------
# FUNCIONES
# -------------------------
def drop_z(geom):
    if geom is None:
        return None
    return transform(lambda x, y, z=None: (x, y), geom)


def html_a_texto(html):
    if html is None or str(html).strip() == "":
        return ""

    soup = BeautifulSoup(html, "html.parser")
    texto = soup.get_text(separator=" ")
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def extraer_nombre_proyecto(texto, fallback=None):
    if texto is None or texto.strip() == "":
        return fallback

    patrones = [
        r"NOMBRE\s+DEL\s+PROYECTO\s*:\s*(.+)",
        r"NOMBRE\s+PROYECTO\s*:\s*(.+)"
    ]

    for pat in patrones:
        m = re.search(pat, texto, flags=re.IGNORECASE)
        if m:
            nombre = m.group(1)

            # Cortar cuando empieza otra sección típica
            nombre = re.split(
                r"PRIORIZADO|PLAN\s+PLURIANUAL|INVERSIÓN|ENTIDAD\s+CONTRATANTE",
                nombre,
                flags=re.IGNORECASE
            )[0]

            nombre = nombre.strip(" .:-")
            if nombre != "":
                return nombre.upper()

    return fallback


# -------------------------
# CARGA DE DATOS
# -------------------------
atlantico = gpd.read_file("MAPAS/MGN_2/DPTO_CNMBR_ATLÁNTICO.shp")
vias      = gpd.read_file("MAPAS/VIAS/Linea.shp")
puntos    = gpd.read_file("MAPAS/PUNTOS/Puntos.shp")
nuevas    = gpd.read_file("MAPAS/NUEVAS/Vías Nuevas.shp")
nuevas = nuevas.rename(columns={'Nombre': 'name'})
# Municipios
atlantico = atlantico.rename(columns={
    "MPIO_CCNCT": "COD_MUN",
    "MPIO_CNMBR": "NOM_MUN"
})
atlantico = atlantico[["COD_MUN", "NOM_MUN", "MPM", "geometry"]]

# Texto y categorías
for df in [vias, puntos]:
    df["name"] = df["name"].str.strip().str.upper()
    df["descripcion_txt"] = df["descriptio"].apply(html_a_texto).str.upper()
    df["Categoria"] = df["Categoria"].str.strip().str.upper()
    df["proyecto_nombre"] = df.apply(
        lambda r: extraer_nombre_proyecto(r["descripcion_txt"], r["name"]),
        axis=1
    )
    df = df.drop(columns=['name', 'altitude', 'alt_mode', 'descriptio', 'folders', 'time_begin', 'time_end', 'time_when', 'descripcion_txt'])
nuevas['proyecto_nombre'] = nuevas['name'].str.strip().str.upper()
nuevas = nuevas.drop(columns=['id', 'name', 'Longitud (',])

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
        "weight": 0.5,
        "fillOpacity": 0.1
    },
    tooltip=GeoJsonTooltip(
        fields=["NOM_MUN"],
        aliases=["Municipio:"]
    )
).add_to(m)

# -------------------------
# MUNICIPIOS POR MPM (OPCIONAL)
# -------------------------
ylgnbu_r = mpl_cm.get_cmap("YlGnBu", 256)  # 256 pasos
colors = [ylgnbu_r(i) for i in range(256)]

colormap = cm.LinearColormap(
    colors=colors,
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
nuevas_fg = folium.FeatureGroup(
    name="Nuevas rutas", 
    show=False
    ).add_to(m)

folium.GeoJson(
    nuevas,
    style_function=lambda x: {
        "color": "#685AFF",
        "weight": 4
    },
    tooltip=GeoJsonTooltip(
        fields=["proyecto_nombre"],
        aliases=["Proyecto:"]
    )
).add_to(nuevas_fg)

# -------------------------
# CATEGORÍAS (BOX ÚNICO)
# -------------------------
CATEGORIA_COLORES = {
    "AMBIENTAL Y GESTIÓN DE DEL TERRITORIO": "#0D7C66",
    "TRANSPORTE": "#FF5B5B",
    "SOCIAL Y CULTURAL": "#B771E5",
    "URBANISMO Y DESARROLLO METROPOLITANO": "#4FD3C4"
}

ICONOS_CATEGORIA = {
    "AMBIENTAL Y GESTIÓN DE DEL TERRITORIO": "icons/ambiente.png",
    "TRANSPORTE": "icons/transporte.png",
    "SOCIAL Y CULTURAL": "icons/cultura.png",
    "URBANISMO Y DESARROLLO METROPOLITANO": "icons/urbanismo.png"
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
                fields=["proyecto_nombre"],
                aliases=["Proyecto:"],
                sticky=True
            )
        ).add_to(fg)

    # ---- PUNTOS ----
    subset_puntos = puntos[puntos["Categoria"] == categoria]

    icon_path = ICONOS_CATEGORIA.get(categoria)

    for _, row in subset_puntos.iterrows():

        if icon_path:
            icono = folium.CustomIcon(
                icon_image=icon_path,
                icon_size=(26, 26)
            )
        else:
            icono = folium.Icon(
                icon="info-sign",
                prefix="glyphicon",
                color="blue"
            )

        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            icon=icono,
            tooltip=f"Proyecto: {row['proyecto_nombre']}"
        ).add_to(fg)

# -------------------------
# CONTROL DE CAPAS
# -------------------------
folium.LayerControl(
    collapsed=False
).add_to(m)


filename = f"mapa_CCB_proyectos.html"
m.save(filename)