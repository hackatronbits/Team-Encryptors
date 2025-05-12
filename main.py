import logging
import os
import tempfile
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from backend.pdf_loader import extract_pdf_text
from backend.redactor import redact_pii
from backend.pdf_writer import redact_pdf
from backend.pii_detector import CUSTOM_PII_ENTITY_TEMPLATE

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# PII entity labels for validation
PII_ENTITY_LABELS = [entity["label"] for entity in CUSTOM_PII_ENTITY_TEMPLATE]
REDACTION_TYPES = ["black_bar", "white_bar", "random", "masked", "custom"]

# Request model for redaction parameters
class RedactionParams(BaseModel):
    selected_entities: Optional[List[str]] = None
    redaction_type: Optional[str] = "random"
    threshold: Optional[float] = 0.3
    custom_mask_text: Optional[str] = None

# Initialize FastAPI
app = FastAPI(
    title="Secure PDF Redaction API",
    description="API for detecting and redacting PII from PDFs using Presidio.",
    version="1.0.0"
)

@app.post("/redact-pdf/")
async def redact_pdf_endpoint(
    file: UploadFile = File(...),
    params: RedactionParams = RedactionParams()
):
    """
    Upload a PDF, extract text, detect PII, and return a redacted PDF.
    
    Parameters:
    - file: PDF file to process
    - selected_entities: List of PII types to redact (e.g., ["PERSON", "PHONE_NUMBER"])
    - redaction_type: Redaction method (black_bar, white_bar, random, masked, custom)
    - threshold: PII detection confidence threshold (0.1-0.9)
    - custom_mask_text: Text to use for custom redaction method
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Validate file size (max 50MB)
    max_file_size_mb = 50
    if file.size > max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File size exceeds {max_file_size_mb}MB limit.")

    # Validate parameters
    if not params.selected_entities:
        raise HTTPException(status_code=400, detail="At least one PII type must be selected.")
    
    if params.selected_entities:
        invalid_entities = [e for e in params.selected_entities if e not in PII_ENTITY_LABELS]
        if invalid_entities:
            raise HTTPException(status_code=400, detail=f"Invalid PII entities: {invalid_entities}")
    
    if params.redaction_type not in REDACTION_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid redaction type. Must be one of {REDACTION_TYPES}")
    
    if params.threshold and (params.threshold < 0.1 or params.threshold > 0.9):
        raise HTTPException(status_code=400, detail="Threshold must be between 0.1 and 0.9")
    
    if params.redaction_type == "custom" and not params.custom_mask_text:
        raise HTTPException(status_code=400, detail="Custom mask text is required for custom redaction")

    # Save uploaded file to temporary location
    input_path = None
    output_path = None
    try:
        logger.info(f"Processing file: {file.filename}")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=UPLOAD_FOLDER) as temp_input:
            temp_input.write(await file.read())
            input_path = temp_input.name

        # Process PDF
        status_code, extracted_text, ocr_text_pages = extract_pdf_text(input_path)
        if status_code == 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Failed to extract text from PDF. "
                    "If this is a scanned PDF, ensure Poppler is installed and POPPLER_PATH is set. "
                    "See https://github.com/oschwartz10612/poppler-windows for installation."
                )
            )
        
        if ocr_text_pages:
            logger.info("Using OCR-extracted text for PII detection")

        # Redact text (for logging detected PII types)
        redacted_text, pii_entities = redact_pii(
            extracted_text,
            redaction_type=params.redaction_type,
            selected_entities=params.selected_entities,
            threshold=params.threshold,
            custom_mask_text=params.custom_mask_text
        )

        # Create temporary output file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=OUTPUT_FOLDER) as temp_output:
            output_path = temp_output.name

        # Redact PDF
        success = redact_pdf(
            input_path,
            output_path,
            redaction_type=params.redaction_type,
            selected_entities=params.selected_entities,
            threshold=params.threshold,
            custom_mask_text=params.custom_mask_text,
            ocr_text_pages=ocr_text_pages
        )

        if not success:
            raise HTTPException(
                status_code=400,
                detail="No PII detected or redaction failed. Adjust detection sensitivity or PII types."
            )

        logger.info(f"Redacted PDF saved to: {output_path}")
        logger.info(f"Detected PII types: {pii_entities}")
        logger.info(f"File size: {file.size / 1024:.1f} KB")

        # Prepare response
        output_filename = f"redacted_{file.filename}"
        response = FileResponse(
            output_path,
            filename=output_filename,
            media_type="application/pdf"
        )

        return response

    except Exception as e:
        logger.error(f"Redaction failed for {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Clean up files
        if input_path and os.path.exists(input_path):
            try:
                os.unlink(input_path)
                logger.info(f"Cleaned up temporary file: {input_path}")
            except Exception as e:
                logger.error(f"Failed to clean up {input_path}: {e}")
        if output_path and os.path.exists(output_path):
            try:
                os.unlink(output_path)
                logger.info(f"Cleaned up temporary file: {output_path}")
            except Exception as e:
                logger.error(f"Failed to clean up {output_path}: {e}")

@app.get("/")
async def root():
    return {
        "message": "Secure PDF Redaction API is running. Use /redact-pdf/ to process PDFs.",
        "endpoints": {
            "/redact-pdf/": "POST a PDF file to redact PII. Accepts optional parameters for PII types, redaction method, threshold, and custom mask text."
        }
    }