import os,io
import json
import fitz  # PyMuPDF
import pandas as pd
import openai
import streamlit as st
from dotenv import load_dotenv
from azure.ai.formrecognizer import DocumentAnalysisClient, DocumentTable, DocumentTableCell
from azure.core.credentials import AzureKeyCredential
from io import BytesIO
from PIL import Image
import base64
from typing import List

# Load environment variables
load_dotenv('.env')

# Azure OpenAI configurations
AZURE_OPENAI_VERSION = os.getenv("AZURE_OPENAI_VERSION")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')

# Azure Form Recognizer configurations
FR_ENDPOINT = os.getenv('AZURE_ENDPOINT')
FR_KEY = os.getenv('AZURE_KEY')

endpoint = os.getenv('AZURE_ENDPOINT')
api_key = os.getenv('AZURE_KEY')
custom_model_id = os.getenv('CUSTOM_AZURE_MODEL_ID')

# Initialize the Document Analysis Client
document_analysis_client = DocumentAnalysisClient(
    endpoint=str(FR_ENDPOINT), credential=AzureKeyCredential(str(FR_KEY))
)

# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# Function to convert an image to PDF
def convert_image_to_pdf(image):
    pdf_bytes = BytesIO()
    image.save(pdf_bytes, format='PDF')
    pdf_bytes.seek(0)
    return pdf_bytes.read()

# Function to call Azure OpenAI for LLM response and convert to table
def call_azure_openai(document_text, api_version: str, azure_endpoint: str, azure_deployment: str, api_key: str, file_name: str):
    client = openai.AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=azure_endpoint,
        azure_deployment=azure_deployment,
    )
    prompt = f"""
Extract the following fields from the provided text in JSON format:
1. item_description: The name of the item.
2. item_amount: The total amount for the item, including quantity.
3. item_subcategory: The main category to which the item belongs. If not specified, print it as "None".
4. item_subcategory_total: The total amount for item_subcategory. Total in the middle of the table is also considered as item_subcategory_total. If not available, print it as "None".

Instructions:
- Maintain the order of items as they appear in the invoice.
- Do not ignore duplicate items; include them as they appear.
- If an amount is missing after an item name, treat the item name as a category.
- Ensure each item and its details are properly structured in the JSON output.
        Text: {document_text}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}],
        temperature=0.7,
        response_format={"type": "json_object"}
    )

    response_message = response.choices[0].message.content

    try:
        response_message = json.loads(response_message)
    except json.JSONDecodeError:
        st.write(f'Error decoding response: {response_message}')
        return None

    items = []
    for item in response_message.get("items", []):
        item_dict = {
            "file_name": file_name,
            "item-name": item.get("item_description", ""),
            "item-amount": item.get("item_amount", ""),
            "item-subcategory": item.get("item_subcategory", ""),
            "item-sub-category-total": item.get("item_subcategory_total", "")
        }
        items.append(item_dict)

    df = pd.DataFrame(items)
    return df

def display_pdf(file, width=500, height=600):
    base64_pdf = base64.b64encode(file.getvalue()).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="{width}" height="{height}" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

# Function to highlight 'None' cells in red
def highlight_none(val):
    if val == "None":
        color = 'background-color: red'
    else:
        color = ''
    return color

Row = List[DocumentTableCell]
RawTable = List[Row]

def group_table_by_rows(table: DocumentTable) -> RawTable:
    cells = sorted(table.cells, key=lambda cell: (cell.row_index, cell.column_index))
    curr_row_idx = cells[0].row_index

    rows = []
    curr_row = []
    for cell in cells:
        if cell.row_index != curr_row_idx:
            rows.append(curr_row)
            curr_row = []
            curr_row_idx = cell.row_index
        curr_row.append(cell)
    if curr_row:
        rows.append(curr_row)

    return rows

def clean_cell_content(content: str) -> str:
    # Remove unwanted characters and whitespace
    cleaned_content = content.replace(':unselected:', '').strip()

    # Try to convert to float and round to 2 decimal places if it is a valid number
    try:
        float_value = float(cleaned_content)
        return f"{float_value:.2f}"
    except ValueError:
        return cleaned_content  # Return the original content if conversion fails

def extract_table_title(raw_table) -> str:
    if len(raw_table[0]) == 1:
        return raw_table[0][0].content
    return None

def has_table_title(raw_table) -> bool:
    return len(raw_table[0]) == 1

def tables_to_dataframe(tables: List[DocumentTable]) -> List[pd.DataFrame]:
    if not tables:
        return []

    raw_tables = list(map(group_table_by_rows, tables))
    list_of_pandas_df = []
    list_of_table_titles = []
    
    for raw_table in raw_tables:
        try:
            title = extract_table_title(raw_table)
            list_of_table_titles.append(title)
            if has_table_title(raw_table):
                raw_table = raw_table[1:]
            
            df_table = pd.DataFrame()
            for i, row in enumerate(raw_table):
                row_content = [clean_cell_content(cell.content) for cell in row]
                if i == 0:
                    df_table = pd.DataFrame(columns=row_content)
                else:
                    df_table.loc[i-1] = row_content
            list_of_pandas_df.append(df_table)
        except Exception as e:
            pass
        
    return zip(list_of_table_titles, list_of_pandas_df)

class CustomDocExtractor:
    def __init__(self):
        # Initialize the Document Analysis Client
        self.document_analysis_client = DocumentAnalysisClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(str(api_key))
        )

    def analyze_document(self, document_data: bytes):
        with io.BytesIO(document_data) as document_stream:
            poller = self.document_analysis_client.begin_analyze_document(custom_model_id, document_stream)
            result = poller.result()
            list_of_extracted_tables = result.tables
            list_of_table_df = tables_to_dataframe(list_of_extracted_tables)
        return [result, list_of_table_df]

def main():
    st.set_page_config(page_title="Invoice Item Extractor", layout="wide")
    st.markdown("""
        <style>
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
        button {
            background-color: #00aaff !important;
            color: black !important;
            border-radius: 5px !important;
        }
        .stDataFrame { 
            background-color: #2b2b2b; 
            color: #e0e0e0; 
        }
        .stDataFrame {
            border: 1px solid #00aaff;
        }
        .blue-heading {
            color: #00aaff;
            font-size: 24px;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='header'><h1>📄 Invoice Item Extractor</h1></div>", unsafe_allow_html=True)

    uploaded_files = st.file_uploader("Upload your documents", type=["pdf", "jpeg", "jpg", "png"], accept_multiple_files=True)

    if uploaded_files:
        if len(uploaded_files) == 1:
            st.markdown("<div class='blue-heading'>Extracting information from a Single invoice...</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='blue-heading'>Extracting information from Multiple invoices...</div>", unsafe_allow_html=True)

        all_data = []

        for uploaded_file in uploaded_files:
            if uploaded_file.type == "application/pdf":
                document = uploaded_file.read()
                document_text = extract_text_from_pdf(document)

                if len(uploaded_files) == 1:
                    col1, col2 = st.columns(2)
                    with col1:
                        display_pdf(uploaded_file, width=500, height=600)
            
            else:
                image = Image.open(uploaded_file)
                if uploaded_file.type == "image/png":
                    jpg_bytes = BytesIO()
                    image.convert("RGB").save(jpg_bytes, format="JPEG")
                    jpg_bytes.seek(0)
                    document = jpg_bytes.read()
                else:
                    document = convert_image_to_pdf(image)

                document_text = extract_text_from_pdf(document)

                if len(uploaded_files) == 1:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.image(image, caption="Uploaded Invoice", use_column_width=True)

            result, list_of_table_df = CustomDocExtractor().analyze_document(document)
            document_text = result.content

            st.session_state.result = result
            st.session_state.list_of_table_df = list_of_table_df
            st.session_state.document_text = document_text

            poller = document_analysis_client.begin_analyze_document(
                "prebuilt-invoice", document=document
            )
            prebuilt_result = poller.result()

            st.session_state.prebuilt_result = prebuilt_result

            llm_df = call_azure_openai(
                st.session_state.document_text,
                AZURE_OPENAI_VERSION,
                AZURE_OPENAI_ENDPOINT,
                AZURE_OPENAI_DEPLOYMENT,
                AZURE_OPENAI_API_KEY,
                uploaded_file.name
            )

            if llm_df is not None:
                all_data.append(llm_df)

        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            styled_df = combined_df.style.applymap(highlight_none)

            if len(uploaded_files) > 1:
                st.write("### Combined Extracted Data")
                st.dataframe(styled_df)
            else:
                col2.dataframe(styled_df)

        st.success("Extraction completed successfully.")

if __name__ == "__main__":
    main()
