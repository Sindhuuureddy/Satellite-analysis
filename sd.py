import json
import ee
import streamlit as st
import folium
import geemap
import osmnx as ox
import geopandas as gpd
from streamlit_folium import folium_static

# ✅ Google Earth Engine Authentication using Streamlit Secrets
try:
    service_account = st.secrets["GEE_SERVICE_ACCOUNT"]
    private_key = st.secrets["GEE_PRIVATE_KEY"].replace("\\n", "\n")

    credentials = ee.ServiceAccountCredentials(service_account, key_data=private_key)
    ee.Initialize(credentials)

    st.success("✅ Google Earth Engine Initialized Successfully!")
except Exception as e:
    st.error(f"❌ Failed to initialize Google Earth Engine: {e}")

# 🏡 **Streamlit UI**
st.title("🌍 Satellite Image Segmentation & Analysis")

location = st.text_input("📍 Enter Location Name", "")

# ---- 📍 Function to Fetch Soil Analysis ----
def analyze_soil(latitude, longitude):
    point = ee.Geometry.Point([longitude, latitude])

    # Load Sentinel-2 image
    image = ee.ImageCollection('COPERNICUS/S2_SR')\
        .filterBounds(point)\
        .filterDate('2024-01-01', '2024-03-25')\
        .sort('CLOUDY_PIXEL_PERCENTAGE')\
        .first()\
        .select(['B2', 'B3', 'B4', 'B8', 'B11', 'B12'])

    # Compute NDVI, NDWI, and NDBI
    ndvi = image.normalizedDifference(['B8', 'B4'])
    ndwi = image.normalizedDifference(['B3', 'B8'])
    ndbi = image.normalizedDifference(['B11', 'B8'])

    # Adjusted NDWI threshold for better water detection
    classified = (
        ee.Image(0)
        .where(ndvi.gt(0.2), 1)  # Vegetation (Green)
        .where(ndwi.gt(0.15), 2)  # Water Bodies (Blue, refined threshold)
        .where(ndbi.gt(0.1), 3)  # Buildings (Gray)
        .where(ndvi.lt(0).And(ndwi.lt(0)).And(ndbi.lt(0)), 4)  # Roads & Bare Land (Yellow)
    )

    # Load soil data
    soil_dataset = ee.Image('OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02')
    soil_texture = soil_dataset.select('b0')
    soil_value = soil_texture.reduceRegion(
        reducer=ee.Reducer.mode(),
        geometry=point,
        scale=250
    ).getInfo()

    soil_type = "Unknown"
    if soil_value:
        soil_class = soil_value.get("b0", None)
        if soil_class:
            if soil_class in [1, 2]:
                soil_type = "Sandy Soil"
            elif soil_class in [3, 4]:
                soil_type = "Loamy Soil"
            elif soil_class in [5, 6]:
                soil_type = "Clayey Soil"

    # Recommend Crops based on Soil Type
    crop_recommendations = {
        "Sandy Soil": "Carrots, Peanuts, Watermelon",
        "Loamy Soil": "Wheat, Maize, Vegetables",
        "Clayey Soil": "Rice, Sugarcane, Pulses",
    }
    recommended_crops = crop_recommendations.get(soil_type, "No recommendation available")

    return soil_type, recommended_crops

# ---- 🌊 Function to Fetch Water Analysis ----
def get_water_body_info(latitude, longitude, hydrolakes_path):
    point = ee.Geometry.Point([longitude, latitude])

    water_dataset = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence")
    modis_water = ee.ImageCollection("MODIS/006/MOD44W").mosaic().select("water_mask")

    search_area = point.buffer(5000)

    # Get water occurrence value from JRC dataset
    water_info = water_dataset.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=search_area,
        scale=30,
        maxPixels=1e13
    )

    modis_info = modis_water.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=search_area,
        scale=250,
        maxPixels=1e13
    )

    # Try to get named lakes using OpenStreetMap
    lakes_gdf = ox.features_from_point((latitude, longitude), tags={"natural": "water"}, dist=5000)

    if not lakes_gdf.empty and "name" in lakes_gdf.columns:
        lake_name = lakes_gdf.iloc[0]["name"]
    else:
        lakes_gdf = gpd.read_file(hydrolakes_path)
        point_gdf = gpd.GeoDataFrame(geometry=[gpd.points_from_xy([longitude], [latitude])], crs=lakes_gdf.crs)
        lakes_gdf = lakes_gdf.to_crs(point_gdf.crs)
        lakes_gdf['distance'] = lakes_gdf.geometry.distance(point_gdf.geometry[0])
        nearest_lake = lakes_gdf.loc[lakes_gdf['distance'].idxmin()]
        lake_name = nearest_lake['Lake_name'] if 'Lake_name' in nearest_lake and not nearest_lake.empty else "Unknown"

    return {
        "Water Presence": "Water detected (JRC)" if water_info.get("occurrence", 0) > 5 else "No water detected",
        "Occurrence % (JRC)": water_info.get("occurrence", "N/A"),
        "MODIS Water Mask": modis_info.get("water_mask", "N/A"),
        "Water Body Name": lake_name,
    }

# ✅ **Run Analysis When Location is Provided**
if location:
    # Convert location to coordinates
    latitude, longitude = 12.65819, 77.4336  # Replace with geocoding if needed

    st.write(f"📍 Analyzing for: {location} (Lat: {latitude}, Lon: {longitude})")

    soil_type, recommended_crops = analyze_soil(latitude, longitude)
    st.write(f"🟤 **Soil Type:** {soil_type}")
    st.write(f"🌾 **Recommended Crops:** {recommended_crops}")

    water_results = get_water_body_info(latitude, longitude, "HydroLAKES_polys_v10.shp")
    st.write(f"🌊 **Water Body Name:** {water_results['Water Body Name']}")
    st.write(f"💧 **Water Presence:** {water_results['Water Presence']}")

    # 📍 **Generate Map**
    Map = folium.Map(location=[latitude, longitude], zoom_start=13)
    folium.Marker([latitude, longitude], popup=location, icon=folium.Icon(color="red")).add_to(Map)
    folium_static(Map)
