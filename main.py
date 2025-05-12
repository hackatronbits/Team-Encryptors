import logging
import os
import shutil
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from backend.pdf_loader import extract_text_from_pdf
from backend.redactor import redact_pii
from backend.pdf_writer import redact_pdf

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
UPLOAD_FOLDER = "Uploads"
OUTPUT_FOLDER = "output"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Initialize FastAPI
app = FastAPI(
    title="Secure PDF Redaction API",
    description="API for detecting and redacting PII from PDFs using Presidio and GLiNER.",
    version="1.0.0"
)

@app.post("/redact-pdf/")
async def redact_pdf_endpoint(file: UploadFile = File(...)):
    """
    Upload a PDF, extract text, detect PII, and return a redacted PDF.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Save uploaded file
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Process PDF
    try:
        status_code, extracted_text, ocr_text_pages = extract_text_from_pdf(file_path)
        if status_code == 0:
            raise HTTPException(status_code=400, detail="Failed to extract text from PDF")

        redacted_text, pii_entities = redact_pii(extracted_text)
        output_filename = f"redacted_{file.filename}"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        redact_pdf(file_path, output_path, ocr_text_pages)
        logger.info(f"Redacted PDF saved to: {output_path}")

        return FileResponse(
            output_path,
            filename=output_filename,
            media_type="application/pdf"
        )
    except Exception as e:
        logger.error(f"Redaction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Redaction failed: {e}")
    finally:
        # Clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)

@app.get("/")
async def root():
    return {
        "message": "Secure PDF Redaction API is running. Use /redact-pdf/ to process PDFs.",
        "endpoints": {
            "/redact-pdf/": "POST a PDF file to redact PII."
        }
    }