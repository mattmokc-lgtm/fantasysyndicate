import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from PIL import Image
from io import BytesIO
import requests
import math
import os
import boto3
import base64
import numpy as np

# # -------------------------
# # UI: Banner renderer
# # -------------------------
# R2_ENDPOINT = st.secrets["R2_ENDPOINT"] 
# R2_ACCESS_KEY_ID = st.secrets["R2_ACCESS_KEY_ID"]
# R2_SECRET_ACCESS_KEY = st.secrets["R2_SECRET_ACCESS_KEY"]
# R2_BUCKET = st.secrets["R2_BUCKET"]
# R2S3 = st.secrets["R2S3"]
# R2_DIR = st.secrets["R2_DIR"]


# # Initialize S3 client
# s3 = boto3.client(
#     R2S3,
#     endpoint_url=R2_ENDPOINT,
#     aws_access_key_id=R2_ACCESS_KEY_ID,
#     aws_secret_access_key=R2_SECRET_ACCESS_KEY,
# )

# # Build object key
# object_key = f"{R2_DIR}/FS.png"

# def render_banner():
#     try:
#         response = s3.get_object(Bucket=R2_BUCKET, Key=object_key)
#         image_data = response["Body"].read()
#         encoded_image = base64.b64encode(image_data).decode()
#         image_src = f"data:image/png;base64,{encoded_image}"
#     except s3.exceptions.NoSuchKey:
#         # Handle case where image isn't found
#         image_src = "" # Use an empty src if no image is available
#         st.error(f"Image {object_key} not found in R2 bucket for banner.")
#         logo_size = "120px" 


# render_banner()
# st.title("Welcome to the Fantasy Syndicate App")
# st.write(f"Hello, **{st.session_state.get('name', '')}**!")

# st.write("Use the sidebar to navigate the application.")
# -------------------------
# UI: Banner renderer
# -------------------------
R2_ENDPOINT = st.secrets["R2_ENDPOINT"] 
R2_ACCESS_KEY_ID = st.secrets["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = st.secrets["R2_SECRET_ACCESS_KEY"]
R2_BUCKET = st.secrets["R2_BUCKET"]
R2S3 = st.secrets["R2S3"]
R2_DIR = st.secrets["R2_DIR"]

# Initialize S3 client
s3 = boto3.client(
    R2S3,
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
)

# Build object key
object_key = f"{R2_DIR}/FS.png"


# Function to retrieve and encode image as base64
def get_encoded_image_src(bucket_name, key):
    try:
        response = s3.get_object(Bucket=bucket_name, Key=key)
        image_data = response["Body"].read()
        encoded_image = base64.b64encode(image_data).decode()
        image_src = f"data:image/png;base64,{encoded_image}"
        return image_src
    except s3.exceptions.NoSuchKey:
        st.error(f"Image {key} not found in R2 bucket for banner.")
        return None
    except Exception as e:
        st.error(f"An error occurred while fetching image: {e}")
        return None

# --- Main App Layout ---

# Create two columns for the title and the logo
col_title, col_logo = st.columns([3.5, 2]) # Adjust the ratio [3, 1] as needed for positioning

with col_logo:
    # Get the image source string
    image_src = get_encoded_image_src(R2_BUCKET, object_key)
    
    if image_src:
        # Use HTML/Markdown to display the base64 image and control its size/alignment
        # Align right and set a max height/width (e.g., 100px)
        st.markdown(
            f'<div style="display: flex; justify-content: flex-end;">'
            f'<img src="{image_src}" style="max-height: 300px; max-width: 300px;">'
            f'</div>',
            unsafe_allow_html=True
        )

with col_title:
    st.title("Welcome to Fantasy Syndicate")
    st.write(f"Hello, **{st.session_state.get('name', '')}**!")
    st.write("Use the sidebar to navigate the application.")

