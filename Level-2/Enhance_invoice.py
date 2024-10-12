import os
import json
import fitz  # PyMuPDF
import pandas as pd
import openai
import streamlit as st
from dotenv import load_dotenv
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from io import BytesIO
from PIL import Image
import base64
import cv2
import numpy as np
from backend import CustomDocExtractor

load_dotenv('.env')

# Azure OpenAI configurations
AZURE_OPENAI_VERSION = os.getenv("AZURE_OPENAI_VERSION")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')

# Azure Form Recognizer configurations
FR_ENDPOINT = os.getenv('AZURE_ENDPOINT')
FR_KEY = os.getenv('AZURE_KEY')

# Initialize the Document Analysis Client
document_analysis_client = DocumentAnalysisClient(
    endpoint=str(FR_ENDPOINT), credential=AzureKeyCredential(str(FR_KEY))
)

def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def convert_image_to_pdf(image):
    pdf_bytes = BytesIO() 
    image.save(pdf_bytes, format='PDF')  
    pdf_bytes.seek(0)  
    return pdf_bytes.read() 

def enhance_image(image):
    # Convert PIL image to numpy array
    img_np = np.array(image)

    # Create a sharpening kernel
    kernel = np.array([[0, -1, 0],
                       [-1, 5, -1],
                       [0, -1, 0]])

    # Apply the sharpening filter
    enhanced_img_np = cv2.filter2D(img_np, -1, kernel)

    # Convert numpy array back to PIL image
    enhanced_image = Image.fromarray(enhanced_img_np)
    return enhanced_image

# Function to call Azure OpenAI for LLM response and convert to table
def call_azure_openai(document_text, api_version: str, azure_endpoint: str, azure_deployment: str, api_key: str, file_name: str):
    client = openai.AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=azure_endpoint,
        azure_deployment=azure_deployment,
    )
    prompt = f"""
        "Extract the following fields from the provided text in JSON format:
        - item_description
        - item_amount (total amount for all quantity)
        - item_subcategory (to which category item belongs if only present for all the items, else NA)
        - item-subcategory-total (subtotal which is present for every sub-category in the invoice, else NA)
        Keep the order as it is in the invoice and do not ignore duplicate values if present"
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

    # Extract the fields from the response and create a table
    items = []
    for item in response_message.get("items", []):  # Assuming items is a list in the response
        item_dict = {
            "file_name": file_name,
            "item-name": item.get("item_description", ""),
            "item-amount": item.get("item_amount", ""),
            "item-subcategory": item.get("item_subcategory", ""),
            "item-sub-category-total": item.get("item_subcategory_total", "")
        }
        items.append(item_dict)

    # Convert to DataFrame
    df = pd.DataFrame(items)
    return df
