import json
import ee
import streamlit as st

# Function to load secrets safely
def load_secrets():
    try:
        creds = st.secrets["gcp"]
        service_account = creds["client_email"]
        private_key = creds["private_key"].replace("\\n", "\n")
        
        credentials = {
            "type": creds["type"],
            "project_id": creds["project_id"],
            "private_key_id": creds["private_key_id"],
            "private_key": private_key,
            "client_email": service_account,
            "client_id": creds["client_id"],
            "auth_uri": creds["auth_uri"],
            "token_uri": creds["token_uri"],
            "auth_provider_x509_cert_url": creds["auth_provider_x509_cert_url"],
            "client_x509_cert_url": creds["client_x509_cert_url"],
        }
        return service_account, credentials
    except KeyError as e:
        st.error(f"Missing key in secrets: {e}")
        st.stop()

# Load credentials
service_account, json_credentials = load_secrets()

# Initialize Earth Engine
try:
    credentials = ee.ServiceAccountCredentials(service_account, key_data=json.dumps(json_credentials))
    ee.Initialize(credentials)
    st.success("✅ Google Earth Engine initialized successfully.")
except Exception as e:
    st.error(f"❌ Failed to initialize Google Earth Engine: {e}")
    st.stop()

# Function placeholders for soil and water analysis
def analyze_soil():
    st.write("Soil analysis coming soon...")
    # TODO: Integrate Colab-based soil analysis logic here

def analyze_water():
    st.write("Water analysis coming soon...")
    # TODO: Integrate Colab-based water analysis logic here

# Streamlit App UI
st.title("Satellite Image Analysis App")
location = st.text_input("Enter Location:")
if st.button("Analyze"):
    if location:
        analyze_soil()
        analyze_water()
    else:
        st.error("Please enter a valid location.")

