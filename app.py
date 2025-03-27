import streamlit as st
import json
import ee
import geopy
import folium
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim
import requests
import numpy as np
from PIL import Image
import io

# Initialize Streamlit App
st.set_page_config(page_title="Soil & Water Analysis", layout="wide")

st.title("🌍 Soil & Water Analysis using Google Earth Engine")

# --------- GEE AUTHENTICATION ---------
def authenticate_gee():
    service_account = st.secrets["GEE"]["client_email"]
    private_key = st.secrets["GEE"]["private_key"]

    credentials_dict = {
        "type": "service_account",
        "project_id": st.secrets["GEE"]["project_id"],
        "private_key_id": st.secrets["GEE"]["private_key_id"],
        "private_key": private_key,
        "client_email": service_account,
        "client_id": st.secrets["GEE"]["client_id"],
        "auth_uri": st.secrets["GEE"]["auth_uri"],
        "token_uri": st.secrets["GEE"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["GEE"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["GEE"]["client_x509_cert_url"],
    }

    credentials = ee.ServiceAccountCredentials(service_account, json.dumps(credentials_dict))
    ee.Initialize(credentials)
    st.success("✅ GEE Authentication Successful")

authenticate_gee()

# --------- LOCATION INPUT ---------
location_input = st.text_input("📍 Enter a Location Name (or Lat, Lon):", "New Delhi, India")

def get_lat_lon(location):
    geolocator = Nominatim(user_agent="geoapi")
    try:
        loc = geolocator.geocode(location)
        if loc:
            return loc.latitude, loc.longitude
        else:
            return None, None
    except:
        return None, None

if "," in location_input:
    try:
        lat, lon = map(float, location_input.split(","))
    except ValueError:
        lat, lon = get_lat_lon(location_input)
else:
    lat, lon = get_lat_lon(location_input)

if lat is None or lon is None:
    st.error("❌ Unable to find the location. Please enter a valid place name or coordinates.")
    st.stop()

st.success(f"🌎 Location Found: {lat}, {lon}")

# --------- DISPLAY MAP ---------
m = folium.Map(location=[lat, lon], zoom_start=12)
folium.Marker([lat, lon], tooltip="Selected Location").add_to(m)
folium_static(m)

# --------- FETCH SATELLITE IMAGE ---------
def fetch_satellite_image(lat, lon):
    image = ee.ImageCollection("COPERNICUS/S2").filterBounds(ee.Geometry.Point(lon, lat)).sort("system:time_start", False).first()
    url = image.getThumbURL({'min': 0, 'max': 3000, 'bands': ['B4', 'B3', 'B2'], 'dimensions': 512, 'format': 'png'})
    return url

sat_image_url = fetch_satellite_image(lat, lon)
st.subheader("🛰️ Original Satellite Image")
st.image(sat_image_url, caption="Satellite Image", use_column_width=True)

# --------- SEGMENTATION (Soil & Water Detection) ---------
def segment_image(lat, lon):
    image = ee.ImageCollection("COPERNICUS/S2").filterBounds(ee.Geometry.Point(lon, lat)).sort("system:time_start", False).first()

    # Example simple threshold-based segmentation (modify for ML-based)
    ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")  # Water Index
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")  # Vegetation Index
    soil_mask = ndvi.lt(0.2).And(ndwi.lt(0.0)).rename("Soil")

    segmented = image.visualize(bands=["B4", "B3", "B2"], min=0, max=3000)
    segmented_url = segmented.getThumbURL({'dimensions': 512, 'format': 'png'})

    return segmented_url

segmented_image_url = segment_image(lat, lon)
st.subheader("📌 Segmented Image")
st.image(segmented_image_url, caption="Segmented Map", use_column_width=True)

# --------- SOIL ANALYSIS ---------
def analyze_soil(lat, lon):
    soil_data = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v01").sample(ee.Geometry.Point(lon, lat), 30).first().getInfo()
    soil_type = soil_data.get("properties", {}).get("b1", "Unknown Soil Type")
    
    soil_recommendations = {
        "Clay": "Suitable for rice, wheat, and cotton.",
        "Sandy": "Best for peanuts, carrots, and watermelons.",
        "Loam": "Ideal for most crops like maize, wheat, and barley.",
        "Silt": "Good for vegetables and fruits like apples.",
        "Unknown Soil Type": "No specific recommendations available."
    }
    return soil_type, soil_recommendations.get(soil_type, "No recommendations available.")

soil_type, crop_suggestion = analyze_soil(lat, lon)
st.subheader("🌱 Soil Analysis")
st.write(f"**Soil Type:** {soil_type}")
st.write(f"**Recommended Crops:** {crop_suggestion}")

# --------- WATER ANALYSIS (Fishing Feasibility) ---------
def analyze_water(lat, lon):
    water_mask = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence")
    water_value = water_mask.sample(ee.Geometry.Point(lon, lat), 30).first().getInfo()
    
    if water_value and "properties" in water_value and "occurrence" in water_value["properties"]:
        water_probability = water_value["properties"]["occurrence"]
        if water_probability > 50:
            return "Water Body Present ✅", "Fishing is Possible 🐟"
        else:
            return "No Significant Water Body Found ❌", "Fishing is Not Feasible"
    return "No Data Available", "No Recommendations"

water_status, fish_feasibility = analyze_water(lat, lon)
st.subheader("💧 Water Analysis")
st.write(f"**Water Status:** {water_status}")
st.write(f"**Fishing Feasibility:** {fish_feasibility}")

# --------- RAINFALL & MOISTURE ANALYSIS ---------
def get_rainfall_moisture(lat, lon):
    rainfall_img = ee.Image("UCSB-CHG/CHIRPS/PENTAD").select("precipitation").reduceRegion(ee.Reducer.mean(), ee.Geometry.Point(lon, lat), 5000).getInfo()
    moisture_img = ee.Image("NASA/SMAP/SPL3SMP_E/005").select("soil_moisture").reduceRegion(ee.Reducer.mean(), ee.Geometry.Point(lon, lat), 5000).getInfo()
    
    rainfall = rainfall_img.get("precipitation", "No Data")
    moisture = moisture_img.get("soil_moisture", "No Data")
    
    return rainfall, moisture

rainfall, moisture = get_rainfall_moisture(lat, lon)
st.subheader("🌧️ Rainfall & Moisture Analysis")
st.write(f"**Average Rainfall:** {rainfall} mm")
st.write(f"**Soil Moisture Content:** {moisture}")

st.success("✅ Analysis Completed!")
