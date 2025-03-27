import streamlit as st
import ee
import geopandas as gpd
import osmnx as ox
import folium
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim
from rich import print
from rich.table import Table

# Authenticate and initialize GEE
ee.Authenticate()
ee.Initialize()

def get_lat_lon(location_name):
    geolocator = Nominatim(user_agent="geoapi")
    location = geolocator.geocode(location_name)
    if location:
        return location.latitude, location.longitude
    else:
        return None, None

def get_water_body_info(lat, lon, hydrolakes_path):
    point = ee.Geometry.Point(lon, lat)
    water_dataset = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence")
    modis_water = ee.ImageCollection("MODIS/006/MOD44W").mosaic().select("water_mask")
    water_quality = ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY")
    search_area = point.buffer(5000)
    
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
    lakes_gdf = ox.features_from_point((lat, lon), tags={"natural": "water"}, dist=5000)
    if not lakes_gdf.empty and "name" in lakes_gdf.columns:
        lake_name = lakes_gdf.iloc[0]["name"]
    else:
        lakes_gdf = gpd.read_file(hydrolakes_path)
        point_gdf = gpd.GeoDataFrame(geometry=[gpd.points_from_xy([lon], [lat])[0]], crs=lakes_gdf.crs)
        lakes_gdf = lakes_gdf.to_crs(point_gdf.crs)
        lakes_gdf['distance'] = lakes_gdf.geometry.distance(point_gdf.geometry[0])
        nearest_lake = lakes_gdf.loc[lakes_gdf['distance'].idxmin()]
        lake_name = nearest_lake['Lake_name'] if 'Lake_name' in nearest_lake and not nearest_lake.empty else "Unknown"
    
    turbidity = water_quality.filterBounds(search_area).select([
        "lake_total_layer_temperature", "lake_mix_layer_depth", "lake_bottom_temperature"
    ]).mean().reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=search_area,
        scale=500,
        maxPixels=1e13
    )
    turbidity_values = {band: turbidity.get(band).getInfo() if turbidity.get(band) is not None else "No Data" 
                        for band in ["lake_total_layer_temperature", "lake_mix_layer_depth", "lake_bottom_temperature"]}
    jrc_presence = water_info.get("occurrence").getInfo() if water_info else None
    modis_presence = modis_info.get("water_mask").getInfo() if modis_info else None
    
    water_map = folium.Map(location=[lat, lon], zoom_start=13)
    folium.Marker([lat, lon], popup=f"Analyzed Location: {lat}, {lon}", icon=folium.Icon(color="blue")).add_to(water_map)
    folium.Circle([lat, lon], radius=500, color="blue" if jrc_presence and jrc_presence > 5 else "red",
                  fill=True, fill_color="blue" if jrc_presence and jrc_presence > 5 else "red",
                  fill_opacity=0.4, popup=f"Water Presence: {'Detected' if jrc_presence and jrc_presence > 5 else 'Not Detected'}").add_to(water_map)
    
    return {
        "Water Presence": "Water detected (JRC)" if jrc_presence and jrc_presence > 5 else "No water detected",
        "Occurrence % (JRC)": jrc_presence,
        "MODIS Water Mask": modis_presence,
        "Water Body Name": lake_name,
        "Turbidity Indices": turbidity_values,
        "Map": water_map
    }

st.title("Soil and Water Analysis App")
location_name = st.text_input("Enter location name:")
if location_name:
    lat, lon = get_lat_lon(location_name)
    if lat and lon:
        st.success(f"Latitude: {lat}, Longitude: {lon}")
    else:
        st.error("Location not found. Try another name.")
lat_input = st.text_input("Enter Latitude:")
lon_input = st.text_input("Enter Longitude:")
if lat_input and lon_input:
    try:
        lat, lon = float(lat_input), float(lon_input)
        hydrolakes_path = "path_to_hydrolakes.shp"
        result = get_water_body_info(lat, lon, hydrolakes_path)
        st.write(result)
        folium_static(result["Map"])
    except ValueError:
        st.error("Please enter valid latitude and longitude values.")
