import os
import re
import shutil
from typing import Dict, List

import fitz  # PyMuPDF
import spacy
import pytesseract
from pdf2image import convert_from_path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, ImageDraw

# ----------------------------
# Constants and Directory Setup
# ----------------------------
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ----------------------------
# Initialize FastAPI App
# ----------------------------
app = FastAPI(
    title="Advanced PDF Redaction API",
    description=(
        "API for detecting and redacting PII from PDFs. Redaction can be performed in two modes: "
        "default (redact all detected PII) or advanced (skip redacting any text in an exclusions list)."
    ),
    version="1.0.0",
)

# ----------------------------
# Load SpaCy Model
# ----------------------------
try:
    nlp = spacy.load("en_core_web_lg")
except OSError:
    raise ImportError("SpaCy model 'en_core_web_lg' not found. Run: python -m spacy download en_core_web_lg")

# ----------------------------
# PII Detection Configuration
# ----------------------------
# List of entity labels to be redacted via SpaCy NER.
PII_LABELS = ["PERSON", "GPE", "ORG", "DATE", "LOC", "NORP", "FAC"]

# Regex patterns for additional PII detection.
# Added patterns:
# - "PAN": Matches India’s PAN numbers (5 letters, 4 digits, 1 letter).
# - "LONG_ALPHANUM": Matches words with 11 or more characters that contain at least one letter and one digit.
REGEX_PATTERNS = {
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "PAN": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    "AADHAR": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
    "PIN_7DIGIT": r"\b\d{7}\b",
    
    "LONG_ALPHANUM": r"\b(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]{11,}\b",
    "LONG_ALPHANUM_2": r"\b(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]{10,}\b",
   
    
    "BANK_ACC": r"\b\d{9,18}\b",
    "IFSC": r"\b[A-Z]{4}0[A-Z0-9]{6}\b"
}



# ----------------------------
# Utility Functions
# ----------------------------
def extract_text_from_pdf_digital(pdf_path: str) -> str:
    """
    Extract text from a digital (text-based) PDF using PyMuPDF.
    """
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            page_text = page.get_text("text")
            text += page_text + "\n"
        return text
    except Exception as e:
        raise RuntimeError(f"Error extracting digital text: {str(e)}")

def extract_text_via_ocr(pdf_path: str) -> str:
    """
    Extract text from a scanned PDF using OCR (via pdf2image and pytesseract).
    """
    try:
        images = convert_from_path(pdf_path)
        text = "\n".join([pytesseract.image_to_string(img) for img in images])
        return text
    except Exception as e:
        raise RuntimeError(f"OCR extraction failed: {str(e)}")

def detect_pii(text: str) -> Dict[str, List[str]]:
    """
    Detect PII from the given text using both SpaCy NER and regex matching.
    Returns a dictionary with:
       "NER": Mapping of entity type to list of detected items.
       "REGEX": Mapping of regex key (EMAIL, PHONE, SSN, PAN, LONG_ALPHANUM) to list of matches.
    """
    doc = nlp(text)
    pii_data = {"NER": {}, "REGEX": {}}
    
    # Detect using SpaCy NER
    for ent in doc.ents:
        if ent.label_ in PII_LABELS:
            pii_data["NER"].setdefault(ent.label_, []).append(ent.text)
    
    # Detect using Regex patterns
    for key, pattern in REGEX_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            pii_data["REGEX"][key] = matches

    return pii_data

def redact_pdf_digital(input_path: str, output_path: str, pii_data: Dict[str, List[str]], exclusions: List[str] = None) -> None:
    """
    Redact PII from a digital PDF using PyMuPDF.
    In advanced mode, any detected PII text that exactly matches one of the provided exclusions
    (case-insensitive) will be skipped.
    """
    exclusions = [ex.lower() for ex in exclusions] if exclusions else []
    doc = fitz.open(input_path)
    
    for page in doc:
        for group in ["NER", "REGEX"]:
            for category, items in pii_data.get(group, {}).items():
                for pii_text in items:
                    if pii_text and pii_text.strip():
                        if any(pii_text.strip().lower() == ex for ex in exclusions):
                            continue
                        areas = page.search_for(pii_text)
                        for rect in areas:
                            page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()
    doc.save(output_path)

def redact_pdf_scanned(input_path: str, output_path: str, pii_data: Dict[str, List[str]], exclusions: List[str] = None) -> None:
    """
    Redact PII from a scanned PDF using image-level processing.
    For each page converted to an image, pecified word bounding boxes are redacted
    when a detected PII (or a match from the LONG_ALPHANUM pattern) is found,
    unless it is excluded (in advanced mode).
    """
    exclusions = [ex.lower() for ex in exclusions] if exclusions else []
    images = convert_from_path(input_path)
    redacted_images = []

    pij_set = set()
    for group in pii_data.values():
        for category in group:
            for item in group[category]:
                if any(item.strip().lower() == ex for ex in exclusions):
                    continue
                pij_set.add(item.lower().strip())

    for img in images:
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        draw = ImageDraw.Draw(img)
        n_boxes = len(ocr_data['level'])
        for i in range(n_boxes):
            word = ocr_data['text'][i].strip().lower()
            if word:
                if any(pii in word for pii in pij_set):
                    x, y, w, h = (
                        ocr_data['left'][i],
                        ocr_data['top'][i],
                        ocr_data['width'][i],
                        ocr_data['height'][i],
                    )
                    draw.rectangle(((x, y), (x + w, y + h)), fill="black")
        redacted_images.append(img)
    
    redacted_images[0].save(output_path, save_all=True, append_images=redacted_images[1:])

# ----------------------------
# API Endpoint for Redacting PDFs
# ----------------------------
@app.post("/redact-pdf/")
async def redact_pdf_endpoint(
    file: UploadFile = File(...),
    redaction_type: str = Form(default="default"),  # "default" or "advanced"
    exclusions: str = Form(default="")  # Comma-separated list for advanced mode
):
    """
    Uploads a PDF, extracts text, detects PII (including long mixed alphanumeric words),
    and returns a redacted PDF.
    In 'advanced' mode, provide exclusions (comma-separated) who will not be redacted if a match is exact.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Save the uploaded file
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Try digital text extraction first, with OCR fallback if necessary.
    try:
        text = extract_text_from_pdf_digital(file_path)
        if len(text.strip()) < 50:
            raise ValueError("Insufficient digital text; switching to OCR")
        is_digital = True
    except Exception:
        is_digital = False
        text = extract_text_via_ocr(file_path)
    
    # Detect PII using both SpaCy and regex (including the LONG_ALPHANUM pattern)
    pii_data = detect_pii(text)
    
    output_filename = f"redacted_{file.filename}"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)
    
    exclusion_list = []
    if redaction_type.lower() == "advanced" and exclusions:
        exclusion_list = [ex.strip() for ex in exclusions.split(",") if ex.strip()]
    
    try:
        if is_digital:
            redact_pdf_digital(file_path, output_path, pii_data, exclusions=exclusion_list)
        else:
            redact_pdf_scanned(file_path, output_path, pii_data, exclusions=exclusion_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redaction failed: {str(e)}")
    
    return FileResponse(output_path, filename=output_filename)

# ----------------------------
# Root Endpoint
# ----------------------------
@app.get("/")
async def root():
    return JSONResponse({
        "message": "Advanced PDF Redaction API is running. Use /redact-pdf/ to process your PDF.",
        "usage": {
            "redaction_type": "default or advanced",
            "exclusions": "Comma-separated text for advanced mode (optional)"
        }
    })