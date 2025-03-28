import ee
import folium
import geopandas as gpd
import osmnx as ox
from IPython.core.display import HTML, display
from folium.plugins import FloatImage

ee.Initialize()

# 🔹 Get Latitude and Longitude from User
latitude = float(input("Enter Latitude: "))
longitude = float(input("Enter Longitude: "))
print(f"\n📍 Location Selected: {latitude}, {longitude}")

def add_ee_layer(self, ee_image, vis_params, name):
    """Adds an Earth Engine image as a layer to the folium map."""
    map_id_dict = ee.Image(ee_image).getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id_dict["tile_fetcher"].url_format,
        attr="Google Earth Engine",
        name=name,
        overlay=True,
        control=True,
    ).add_to(self)
folium.Map.add_ee_layer = add_ee_layer

# Define Point Geometry
point = ee.Geometry.Point([longitude, latitude])

# Load Sentinel-2 Image
image = ee.ImageCollection('COPERNICUS/S2_SR')\
    .filterBounds(point)\
    .filterDate('2024-01-01', '2024-03-25')\
    .sort('CLOUDY_PIXEL_PERCENTAGE')\
    .first()\
    .select(['B2', 'B3', 'B4', 'B8', 'B11', 'B12'])

sentinel_vis_params = {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 3000, 'gamma': 1.4}

# Compute NDVI, NDWI, and NDBI
ndvi = image.normalizedDifference(['B8', 'B4'])
ndwi = image.normalizedDifference(['B3', 'B8'])
ndbi = image.normalizedDifference(['B11', 'B8'])

classified = (
    ee.Image(0)
    .where(ndvi.gt(0.2), 1)  # Vegetation (Green)
    .where(ndwi.gt(0.15), 2)  # Water Bodies (Blue)
    .where(ndbi.gt(0.1), 3)  # Buildings (Gray)
    .where(ndvi.lt(0).And(ndwi.lt(0)).And(ndbi.lt(0)), 4)  # Roads & Bare Land (Yellow)
)
classified_vis = {'min': 0, 'max': 4, 'palette': ['black', 'green', 'blue', 'gray', 'yellow']}

# Load ESA WorldCover Land Classification
earth_cover = ee.ImageCollection("ESA/WorldCover/v100").first().clip(point.buffer(1000))
worldcover_vis_params = {"min": 10, "max": 100, "palette": ["brown", "green", "gray", "blue"]}

# Load Soil Data
soil_dataset = ee.Image('OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02')
soil_texture = soil_dataset.select('b0')
soil_value = soil_texture.reduceRegion(reducer=ee.Reducer.mode(), geometry=point, scale=250).getInfo()

soil_type = "Unknown"
if soil_value:
    soil_class = soil_value.get("b0", None)
    if soil_class:
        soil_type = {1: "Sandy Soil", 2: "Sandy Soil", 3: "Loamy Soil", 4: "Loamy Soil", 5: "Clayey Soil", 6: "Clayey Soil"}.get(soil_class, "Unknown")

# Crop Recommendations
crop_recommendations = {
    "Sandy Soil": "Carrots, Peanuts, Watermelon",
    "Loamy Soil": "Wheat, Maize, Vegetables",
    "Clayey Soil": "Rice, Sugarcane, Pulses",
}
recommended_crops = crop_recommendations.get(soil_type, "No recommendation available")

# Water Body Analysis (JRC, MODIS, OSM, HydroLAKES)
water_dataset = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence")
modis_water = ee.ImageCollection("MODIS/006/MOD44W").mosaic().select("water_mask")
search_area = point.buffer(5000)

water_info = water_dataset.reduceRegion(reducer=ee.Reducer.mean(), geometry=search_area, scale=30, maxPixels=1e13)
modis_info = modis_water.reduceRegion(reducer=ee.Reducer.mean(), geometry=search_area, scale=250, maxPixels=1e13)

# OpenStreetMap Water Detection
lakes_gdf = ox.features_from_point((latitude, longitude), tags={"natural": "water"}, dist=5000)
lake_name = lakes_gdf.iloc[0]["name"] if not lakes_gdf.empty and "name" in lakes_gdf.columns else "No Named Water Body Found"

# Create Maps
satellite_map = folium.Map(location=[latitude, longitude], zoom_start=14, control_scale=True)
satellite_map.add_ee_layer(image, sentinel_vis_params, "Sentinel-2 (RGB)")

segmented_map = folium.Map(location=[latitude, longitude], zoom_start=14, control_scale=True)
segmented_map.add_ee_layer(earth_cover, worldcover_vis_params, "ESA WorldCover")

# Display Maps
map_html = f"""
<div style="display: flex; justify-content: center; gap: 20px;">
    <div style="width: 48%; border: 3px solid black; padding: 10px; background: white; text-align: center; font-size: 16px; font-weight: bold;">
        <div><strong>Original Satellite Image</strong></div>
        {satellite_map._repr_html_()}
    </div>
    <div style="width: 48%; border: 3px solid black; padding: 10px; background: white; text-align: center; font-size: 16px; font-weight: bold;">
        <div><strong>Segmented Image (Land Cover)</strong></div>
        {segmented_map._repr_html_()}
    </div>
</div>
"""
display(HTML(map_html))

# Print Results
print("\n🔍 **Analysis Results:**")
print(f"📍 **Location:** Latitude {latitude}, Longitude {longitude}")
print(f"🟤 **Soil Type:** {soil_type}")
print(f"🌾 **Recommended Crops:** {recommended_crops}")
print(f"🌊 **Nearest Water Body:** {lake_name}")
