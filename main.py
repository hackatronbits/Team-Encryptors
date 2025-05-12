import os
import re
import shutil
from typing import Dict, List

import fitz  # PyMuPDF (For digital PDF processing)
import spacy
import pytesseract
from pdf2image import convert_from_path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, ImageDraw
from fastapi.middleware.cors import CORSMiddleware

# ----------------------------
# Setup & Configurations
# ----------------------------
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ----------------------------
# Initialize FastAPI App
# ----------------------------
app = FastAPI(title="PDF Redaction API")

# ✅ Enable CORS for Frontend Integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Load SpaCy Model
# ----------------------------
try:
    nlp = spacy.load("en_core_web_lg")  # Large model for better accuracy
except OSError:
    raise ImportError("SpaCy model not found! Install with: python -m spacy download en_core_web_lg")

# ----------------------------
# Expanded PII Detection Configuration
# ----------------------------
PII_LABELS = ["PERSON", "GPE", "ORG", "DATE", "LOC", "NORP", "FAC","DOB","AGE","EMAIL","PHONE","SSN","PAN","AADHAR","BANK_ACC","CREDIT_CARD","IP_ADDRESS" ]
# These labels can be expanded based on the specific needs of the application.

REGEX_PATTERNS = {
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "PAN": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    "AADHAR": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
    "BANK_ACC": r"\b\d{9,18}\b",
    "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){4}\b",
    "IP_ADDRESS": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
}

# ----------------------------
# Utility Functions
# ----------------------------
def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text from a digital PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    return "\n".join([page.get_text("text") for page in doc])

def detect_pii(text: str) -> Dict[str, List[str]]:
    """Detects PII in text using SpaCy NER & Regex matching."""
    doc = nlp(text)
    pii_data = {"NER": {}, "REGEX": {}}
    
    for ent in doc.ents:
        if ent.label_ in PII_LABELS:
            pii_data["NER"].setdefault(ent.label_, []).append(ent.text)
    
    for key, pattern in REGEX_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            pii_data["REGEX"][key] = matches

    return pii_data

def redact_pdf_digital(input_path: str, output_path: str, pii_data: Dict[str, List[str]]) -> None:
    """Redacts detected PII from a digital PDF."""
    doc = fitz.open(input_path)
    
    for page in doc:
        for group in ["NER", "REGEX"]:
            for category, items in pii_data[group].items():
                for pii_text in items:
                    areas = page.search_for(pii_text)
                    for rect in areas:
                        page.add_redact_annot(rect, fill=(0, 0, 0))  # Black out
        page.apply_redactions()
    
    doc.save(output_path)

@app.post("/redact-pdf/")
async def redact_pdf_endpoint(file: UploadFile = File(...)):
    """Uploads a PDF, detects PII, and returns a redacted PDF."""
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    text = extract_text_from_pdf(file_path)
    pii_data = detect_pii(text)
    output_filename = f"redacted_{file.filename}"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    redact_pdf_digital(file_path, output_path, pii_data)  # ✅ Apply redaction

    return JSONResponse({"filename": output_filename})

@app.get("/output/{filename}")
async def serve_file(filename: str):
    """Serves redacted PDFs for download."""
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)

@app.get("/")
async def root():
    return JSONResponse({"message": "PDF Redaction API is running!"})