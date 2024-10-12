#dependencies
from flask import Flask, request, jsonify
import os
import pandas as pd
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import io

app = Flask(__name__)

# Load environment variables
load_dotenv('.env')
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
                    if field and field.value:
                        # Check if the field is a CurrencyValue
                        if isinstance(field.value, dict) and "amount" in field.value:
                            item_dict[key] = field.value["amount"]  # Get only the numeric value
                        else:
                            item_dict[key] = field.value  # Keep the value as it is


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

@app.route('/upload', methods=['POST'])
def upload_file():
    # Validate if files are provided
    if 'files' not in request.files:
        return jsonify({"error": "No file part"}), 400

    files = request.files.getlist('files')
    selected_fields = request.form.getlist('selected_fields')

    all_invoices_data = []

    # Process each uploaded file
    for uploaded_file in files:
        if uploaded_file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        # Process the file (PDF or Image)
        document = io.BytesIO(uploaded_file.read())
        df = extract_invoice_line_items(document, uploaded_file.filename, selected_fields)
        all_invoices_data.append(df.to_dict(orient='records'))

    # Combine all the data into a single list of records
    combined_data = [item for sublist in all_invoices_data for item in sublist]

    return jsonify({"data": str(combined_data)}), 200

if __name__ == "__main__":
    app.run(debug=True)