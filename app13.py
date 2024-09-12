import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from PIL import Image

# Load environment variables
load_dotenv('.env')

# Azure Form Recognizer configurations
FR_ENDPOINT = os.getenv('AZURE_ENDPOINT')
FR_KEY = os.getenv('AZURE_KEY')

# Initialize the Document Analysis Client
document_analysis_client = DocumentAnalysisClient(
    endpoint=FR_ENDPOINT, credential=AzureKeyCredential(FR_KEY)
)

def extract_invoice_line_items(image):
    # Start analysis using the prebuilt invoice model
    poller = document_analysis_client.begin_analyze_document(
        "prebuilt-invoice", document=image
    )
    prebuilt_result = poller.result()

    # Extract line items into a list
    items = []
    for document in prebuilt_result.documents:
        if "Items" in document.fields:
            for item in document.fields["Items"].value:
                item_dict = {}
                for key, field in item.value.items():
                    if field and field.value:  # Ensure field is not None and has a value
                        item_dict[key] = field.value
                items.append(item_dict)

    # Convert to DataFrame
    df = pd.DataFrame(items)
    return df

def main():
    st.title("Invoice Line Item Extractor")

    # Upload an image
    uploaded_file = st.file_uploader("Upload your invoice image", type=["jpeg", "jpg", "png"])

    if uploaded_file is not None:
        # Display the heading immediately after uploading
        st.write("## Extracting the Features")

        st.write("Extracting line items from the invoice...")
        image = uploaded_file.read()

        # Display the image and the extracted table side by side
        col1, col2 = st.columns(2)

        with col1:
            # Show the uploaded image in the first column
            st.image(uploaded_file, caption='Uploaded Invoice Image', use_column_width=True)

        with col2:
            # Extract and display invoice line items in the second column
            df = extract_invoice_line_items(image)
            st.dataframe(df)

if __name__ == "__main__":
    main()
