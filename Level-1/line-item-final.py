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

def extract_invoice_line_items(document, file_name, selected_fields):
    # Start analysis using the prebuilt invoice model
    poller = document_analysis_client.begin_analyze_document(
        "prebuilt-invoice", document=document
    )
    prebuilt_result = poller.result()

    # Extract line items into a list
    items = []
    for document in prebuilt_result.documents:
        if "Items" in document.fields:
            for item in document.fields["Items"].value:
                item_dict = {"file_name": file_name}
                for key, field in item.value.items():
                    if field and field.value and (key in selected_fields or key in ["Description", "Amount"]):
                        item_dict[key] = field.value
                items.append(item_dict)

    df = pd.DataFrame(items)
    df = df.rename(columns={"Description": "item_name", "Amount": "item_amount"})

    # Ensure "item_name" and "item_amount" are always included in the selected fields
    selected_fields = ["item_name", "item_amount"] + selected_fields

    # Ensure all selected columns are in the dataframe, and fill missing columns with NaN
    for field in selected_fields:
        if field not in df.columns:
            df[field] = pd.NA  # Use pd.NA for missing fields

    # Return the dataframe with selected columns
    selected_columns = ["file_name"] + selected_fields
    df = df[selected_columns]

    return df

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

    # Extract and return the DataFrame
    df = extract_invoice_line_items(document, file_name, selected_fields)
    return df, file_type, uploaded_file

def display_pdf(file, width=500, height=600):
    # Encode the PDF to base64
    base64_pdf = base64.b64encode(file.getvalue()).decode('utf-8')
    # Display the PDF in an iframe
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="{width}" height="{height}" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def main():
    # Set the page config for a custom layout
    st.set_page_config(page_title="Invoice Line Item Extractor", layout="wide")

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

    # Header
    st.markdown("<div class='header'><h1>📄 Invoice Line Item Extractor</h1></div>", unsafe_allow_html=True)

    # Upload multiple files (images or PDFs)
    uploaded_files = st.file_uploader("Upload your invoice(s) (images or PDFs)", type=["jpeg", "jpg", "png", "pdf"], accept_multiple_files=True)

    if uploaded_files:
        # Determine and display heading based on the number of uploaded files
        if len(uploaded_files) == 1:
            st.markdown("<div class='blue-heading'>Extracting information from a Single invoice...</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='blue-heading'>Extracting information from Multiple invoices...</div>", unsafe_allow_html=True)

        # Define the fields available for extraction
        available_fields = ["Quantity", "Date", "ProductCode"]

        st.write("Please select the additional fields you want to extract:")

        # Create a horizontal layout for checkboxes using CSS
        cols = st.columns(3)  # Create 3 columns for checkboxes
        selected_fields = []

        # Create checkboxes in three columns
        for i, field in enumerate(available_fields):
            with cols[i % 3]:  # Distribute the checkboxes across three columns
                if st.checkbox(field, value=False):
                    selected_fields.append(field)

        if not selected_fields:
            st.info("No additional fields selected. Only 'Description' and 'Amount' will be extracted.")

        # Button to start extraction
        if st.button("Start Extraction"):
            # Add a progress bar and start a spinner
            with st.spinner('Decoding your invoice, one line at a time...'):
                progress_bar = st.progress(0)
                total_files = len(uploaded_files)

                all_invoices_data = []

                for idx, uploaded_file in enumerate(uploaded_files):
                    # Process each file and show progress
                    df, file_type, uploaded_file = process_file(uploaded_file, selected_fields)
                    all_invoices_data.append(df)

                    # Update the progress bar
                    progress_percentage = (idx + 1) / total_files
                    progress_bar.progress(progress_percentage)

                # Combine all the data into a single DataFrame if there are multiple files
                if len(uploaded_files) > 1:
                    combined_df = pd.concat(all_invoices_data, ignore_index=True)
                    st.dataframe(combined_df)
                else:
                    # Display the individual DataFrame if only one invoice is processed
                    file_name = uploaded_file.name
                    # Create columns for displaying the PDF and data side by side
                    cols = st.columns(2)  # Equal width for PDF and table
                    with cols[0]:
                        if file_type == "application/pdf":
                            # Display the PDF in the Streamlit app
                            display_pdf(uploaded_file, width=500, height=600)
                        else:
                            # Display the uploaded image
                            st.image(uploaded_file, caption=file_name)
                    with cols[1]:
                        st.dataframe(all_invoices_data[0])  # Display the extracted data

                # Display success message
                st.success("Extraction completed successfully!")

if __name__ == "__main__":
    main()
