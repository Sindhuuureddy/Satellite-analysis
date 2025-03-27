import json
import ee
import streamlit as st
import folium
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim

# Load credentials from Streamlit secrets
service_account = st.secrets["gcp"]["gcp_service_account"]
json_credentials = json.loads(st.secrets["gcp"]["gcp_service_account"])
credentials = ee.ServiceAccountCredentials(service_account, key_data=json.dumps(json_credentials))

# Initialize Earth Engine
ee.Initialize(credentials)

def get_lat_lon(location_name):
    """Convert location name to latitude and longitude."""
    geolocator = Nominatim(user_agent="geoapi")
    location = geolocator.geocode(location_name)
    if location:
        return location.latitude, location.longitude
    return None, None

# Water Analysis Function
def analyze_water(latitude, longitude):
    point = ee.Geometry.Point([longitude, latitude])
    image = ee.ImageCollection("COPERNICUS/S2").filterBounds(point).first()
    
    ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')
    water_mask = ndwi.gt(0.1)
    
    water_dataset = ee.FeatureCollection("projects/sat-io/open-datasets/JRC_GlobalSurfaceWater")
    water_present = water_dataset.filterBounds(point).size().getInfo() > 0
    
    water_name_dataset = ee.FeatureCollection("users/giswqs/openstreetmap_waterbodies")
    water_name = water_name_dataset.filterBounds(point).first().get('name').getInfo()
    
    fishing_possible = "Yes" if water_present else "No"
    
    return water_present, water_name, fishing_possible

# Soil Analysis Function
def analyze_soil(latitude, longitude):
    point = ee.Geometry.Point([longitude, latitude])
    soil_data = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02")
    soil_texture = soil_data.select("b0")
    sample = soil_texture.sample(point, 30).first()
    soil_class = sample.get("b0").getInfo() if sample else None
    
    soil_types = {
        1: "Sand", 2: "Loamy Sand", 3: "Sandy Loam", 4: "Silt Loam",
        5: "Sandy Clay Loam", 6: "Clay Loam", 7: "Silty Clay Loam",
        8: "Sandy Clay", 9: "Silty Clay", 10: "Clay"
    }
    
    soil_type = soil_types.get(soil_class, "Unknown Soil Type")
    
    moisture_dataset = ee.ImageCollection("NASA_USDA/HSL/SMAP10KM_soil_moisture").first()
    moisture = moisture_dataset.sample(point, 30).first().get("soil_moisture").getInfo()
    
    return soil_type, moisture

# Streamlit UI
st.title("Satellite Image Segmentation & Analysis")
location_name = st.text_input("Enter Location:")

if location_name:
    lat, lon = get_lat_lon(location_name)
    if lat and lon:
        st.write(f"**Coordinates:** {lat}, {lon}")
        
        # Perform Analysis
        water_present, water_name, fishing_possible = analyze_water(lat, lon)
        soil_type, moisture = analyze_soil(lat, lon)
        
        # Display Results
        st.subheader("Water Analysis")
        st.write(f"**Water body detected:** {water_present}")
        st.write(f"**Water body name:** {water_name if water_name else 'Unknown'}")
        st.write(f"**Fishing possible:** {fishing_possible}")
        
        st.subheader("Soil Analysis")
        st.write(f"**Soil Type:** {soil_type}")
        st.write(f"**Soil Moisture:** {moisture}")
        
        # Map Visualization
        m = folium.Map(location=[lat, lon], zoom_start=12)
        folium.Marker([lat, lon], popup=location_name).add_to(m)
        folium_static(m)
    else:
        st.error("Location not found. Please enter a valid location.")
