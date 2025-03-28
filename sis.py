import ee
import folium
import streamlit as st
from streamlit_folium import folium_static
import geopandas as gpd
import osmnx as ox
from folium.plugins import FloatImage

import streamlit as st
import ee
import google.auth
from google.oauth2 import service_account

# Ensure secrets are available
required_keys = [
    "gee_service_account_type",
    "gee_project_id",
    "gee_private_key_id",
    "gee_private_key",
    "gee_client_email",
    "gee_client_id",
    "gee_auth_uri",
    "gee_token_uri",
    "gee_auth_provider_x509_cert_url",
    "gee_client_x509_cert_url",
]

missing_keys = [key for key in required_keys if key not in st.secrets]
if missing_keys:
    st.error(f"Missing keys in secrets.toml: {missing_keys}")
    st.stop()

# Load service account credentials from Streamlit secrets
service_account_info = {
    "type": st.secrets["gee_service_account_type"],
    "project_id": st.secrets["gee_project_id"],
    "private_key_id": st.secrets["gee_private_key_id"],
    "private_key": st.secrets["gee_private_key"].replace("\\n", "\n"),  # Fix private key formatting
    "client_email": st.secrets["gee_client_email"],
    "client_id": st.secrets["gee_client_id"],
    "auth_uri": st.secrets["gee_auth_uri"],
    "token_uri": st.secrets["gee_token_uri"],
    "auth_provider_x509_cert_url": st.secrets["gee_auth_provider_x509_cert_url"],
    "client_x509_cert_url": st.secrets["gee_client_x509_cert_url"],
}

# Create credentials object
credentials = service_account.Credentials.from_service_account_info(service_account_info)

# Initialize Google Earth Engine with these credentials
ee.Initialize(credentials)

st.success("Google Earth Engine Authentication Successful ✅")


st.title("🌍 Satellite Image & Land Analysis")

# Get User Input
latitude = st.number_input("Enter Latitude:", format="%.6f")
longitude = st.number_input("Enter Longitude:", format="%.6f")

if st.button("Analyze Location"):
    st.write(f"📍 **Selected Location:** {latitude}, {longitude}")

    # Define Point Geometry
    point = ee.Geometry.Point([longitude, latitude])

    # Load Sentinel-2 Image
    image = (ee.ImageCollection('COPERNICUS/S2_SR')
        .filterBounds(point)
        .filterDate('2024-01-01', '2024-03-25')
        .sort('CLOUDY_PIXEL_PERCENTAGE')
        .first()
        .select(['B2', 'B3', 'B4', 'B8', 'B11', 'B12']))
    sentinel_vis_params = {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 3000, 'gamma': 1.4}

    # Compute NDVI, NDWI, and NDBI
    ndvi = image.normalizedDifference(['B8', 'B4'])
    ndwi = image.normalizedDifference(['B3', 'B8'])
    ndbi = image.normalizedDifference(['B11', 'B8'])

    classified = (ee.Image(0)
        .where(ndvi.gt(0.2), 1)
        .where(ndwi.gt(0.15), 2)
        .where(ndbi.gt(0.1), 3)
        .where(ndvi.lt(0).And(ndwi.lt(0)).And(ndbi.lt(0)), 4))
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

    # Water Body Analysis
    water_dataset = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence")
    modis_water = ee.ImageCollection("MODIS/006/MOD44W").mosaic().select("water_mask")
    search_area = point.buffer(5000)

    # OpenStreetMap Water Detection
    lakes_gdf = ox.features_from_point((latitude, longitude), tags={"natural": "water"}, dist=5000)
    lake_name = lakes_gdf.iloc[0]["name"] if not lakes_gdf.empty and "name" in lakes_gdf.columns else "No Named Water Body Found"

    # Create Maps
    satellite_map = folium.Map(location=[latitude, longitude], zoom_start=14, control_scale=True)
    segmented_map = folium.Map(location=[latitude, longitude], zoom_start=14, control_scale=True)
    
    def add_ee_layer(self, ee_image, vis_params, name):
        map_id_dict = ee.Image(ee_image).getMapId(vis_params)
        folium.raster_layers.TileLayer(
            tiles=map_id_dict["tile_fetcher"].url_format,
            attr="Google Earth Engine",
            name=name,
            overlay=True,
            control=True,
        ).add_to(self)
    folium.Map.add_ee_layer = add_ee_layer

    satellite_map.add_ee_layer(image, sentinel_vis_params, "Sentinel-2 (RGB)")
    segmented_map.add_ee_layer(earth_cover, worldcover_vis_params, "ESA WorldCover")

    # Display Maps in Streamlit
    st.subheader("🌍 Original Satellite Image")
    folium_static(satellite_map)
    
    st.subheader("🗺️ Segmented Land Cover Image")
    folium_static(segmented_map)

    # Display Results
    st.subheader("🔍 Analysis Results")
    st.write(f"📍 **Location:** Latitude {latitude}, Longitude {longitude}")
    st.write(f"🟤 **Soil Type:** {soil_type}")
    st.write(f"🌾 **Recommended Crops:** {recommended_crops}")
    st.write(f"🌊 **Nearest Water Body:** {lake_name}")
