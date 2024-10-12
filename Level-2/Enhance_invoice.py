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
