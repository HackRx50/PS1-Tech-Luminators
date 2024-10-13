# import io
# import os

# from azure.ai.formrecognizer import DocumentAnalysisClient
# from azure.core.credentials import AzureKeyCredential
# from dotenv import load_dotenv

# from transform.table_processing import tables_to_dataframe

# load_dotenv()

# # Azure Form Recognizer credentials
# endpoint = os.getenv('AZURE_ENDPOINT')
# api_key = os.getenv('AZURE_KEY')
# custom_model_id = os.getenv('CUSTOM_AZURE_MODEL_ID')


# class CustomDocExtractor:
#     def __init__(self):
#         # Initialize the Document Analysis Client
#         self.document_analysis_client = DocumentAnalysisClient(
#             endpoint=endpoint,
#             credential=AzureKeyCredential(str(api_key))
#         )

#     def analyze_document(self, document_data: bytes):
#         with io.BytesIO(document_data) as document_stream:
#             poller = self.document_analysis_client.begin_analyze_document(custom_model_id, document_stream)
#             result = poller.result()
#             list_of_extracted_tables = result.tables
#             list_of_table_df = tables_to_dataframe(list_of_extracted_tables)
#         return [result, list_of_table_df]


import io
import os
import pandas as pd
from azure.ai.formrecognizer import DocumentAnalysisClient, DocumentTable, DocumentTableCell
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
from typing import List

load_dotenv()

# Azure Form Recognizer credentials
endpoint = os.getenv('AZURE_ENDPOINT')
api_key = os.getenv('AZURE_KEY')
custom_model_id = os.getenv('CUSTOM_AZURE_MODEL_ID')

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
