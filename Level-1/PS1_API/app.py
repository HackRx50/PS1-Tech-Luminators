#dependencies
from flask import Flask, request, jsonify
import os
import pandas as pd
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import io

app = Flask(__name__)

