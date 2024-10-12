import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
import io
import base64

# Load environment variables
load_dotenv('.env')

# Azure Form Recognizer configurations
FR_ENDPOINT = os.getenv('AZURE_ENDPOINT')
FR_KEY = os.getenv('AZURE_KEY')

document_analysis_client = DocumentAnalysisClient(
    endpoint=FR_ENDPOINT, credential=AzureKeyCredential(FR_KEY)
)

# Full invoice extractor function
def full_invoice_extractor():
    st.markdown(
        "<div class='header'><h1>📄 Full Invoice Extractor</h1></div>",
        unsafe_allow_html=True,
    )

    # Upload multiple files (JPEG, JPG, PNG, PDF)
    uploaded_files = st.file_uploader(
        "Upload your invoice(s) (JPEG, JPG, PNG, PDF)",
        type=["jpeg", "jpg", "png", "pdf"],
        accept_multiple_files=True,
    )
    if uploaded_files:
        for uploaded_file in uploaded_files:
            # Create two columns for layout
            col1, col2 = st.columns(2)
            file_name = uploaded_file.name
            file_type = uploaded_file.type

            with col1:
                if file_type == "application/pdf":
                    # Display the PDF in the Streamlit app
                        display_pdf(uploaded_file, width=500, height=600)
                else:
                    # Display the uploaded image
                    st.image(uploaded_file, caption=file_name)
