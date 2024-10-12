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

# Initialize the Document Analysis Client
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

            with col2:
                try:
                    st.write(f"### Extracted Features from {uploaded_file.name}")

                    # Read the file bytes
                    document = uploaded_file.read()

                    # Analyze using Prebuilt Invoice Model
                    poller = document_analysis_client.begin_analyze_document(
                        "prebuilt-invoice", document=document
                    )
                    prebuilt_result = poller.result()

                    # Extract general fields
                    for doc in prebuilt_result.documents:
                        for field_name, field in doc.fields.items():
                            if field.value_type != "list":  # Exclude the 'Items' field for now
                                st.write(f"**{field_name}:** {field.value}")

                    # Extract items into a DataFrame
                    items = []
                    for doc in prebuilt_result.documents:
                        if "Items" in doc.fields:
                            for item in doc.fields["Items"].value:
                                item_dict = {
                                    "Description": item.value.get("Description").value if item.value.get("Description") else None,
                                    "Quantity": item.value.get("Quantity").value if item.value.get("Quantity") else None,
                                    "Unit": item.value.get("Unit").value if item.value.get("Unit") else None,
                                    "Unit Price": item.value.get("UnitPrice").value.amount if item.value.get("UnitPrice") else None,
                                    "Amount": item.value.get("Amount").value.amount if item.value.get("Amount") else None,
                                }
                                items.append(item_dict)

                    # Display DataFrame if items are extracted
                    if items:
                        df = pd.DataFrame(items)
                        st.dataframe(df)

                except Exception as e:
                    st.write(f"Error processing invoice {uploaded_file.name}: {e}")

def process_file(uploaded_file, selected_fields):
    # Process the file (PDF or Image)
    file_name = uploaded_file.name
    file_type = uploaded_file.type

    if file_type == "application/pdf":
        # Handle PDF file
        document = io.BytesIO(uploaded_file.read())
    else:
        # Handle image file
        document = uploaded_file.read()

def display_pdf(file, width=500, height=600):
    # Encode the PDF to base64
    base64_pdf = base64.b64encode(file.getvalue()).decode('utf-8')
    # Display the PDF in an iframe
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="{width}" height="{height}" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

# Main application logic
def main():
    # Set the page config for a custom layout
    st.set_page_config(
        page_title="Invoice & Document Extraction Tool", layout="wide"
    )

    st.markdown("""
        <style>
        /* General style */
        .main {
            background-color: #1f1f1f;
            color: #e0e0e0;
            font-family: 'Roboto', sans-serif;
        }
        .header {
            text-align: center;
            padding: 20px;
            color: #00aaff;
        }
        h1 {
            font-weight: 600;
            font-size: 36px;
        }

        /* Styling checkboxes in a single row */
        .stCheckbox > div {
            display: inline-block;
            margin-right: 15px;
        }

        /* Customize buttons */
        button {
            background-color: #00aaff !important;
            color: black !important;
            border-radius: 5px !important;
        }

        /* Customize the data frame */
        .stDataFrame { 
            background-color: #2b2b2b; 
            color: #e0e0e0; 
        }

        /* Hover effect for the file uploader */
        .stFileUploader:hover {
            box-shadow: 0px 0px 15px rgba(0, 170, 255, 0.7);
        }

        /* Modern border */
        .stDataFrame {
            border: 1px solid #00aaff;
        }

        /* Align the additional field checkboxes inline */
        .inline-checkbox {
            display: flex;
            justify-content: flex-start;
            gap: 20px;
            margin-top: 10px;
            margin-bottom: 20px;
        }

        /* Style for headings */
        .blue-heading {
            color: #00aaff;
            font-size: 24px;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)

    # Call the full invoice extractor function
    full_invoice_extractor()

if __name__ == "__main__":
    main()
