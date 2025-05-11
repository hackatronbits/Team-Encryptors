import fitz  # PyMuPDF
from backend.ocr_utils import extract_text_from_scanned_pdf 
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_path):
    """
    Extracts text from a PDF. Falls back to OCR if no digital text is found.
    """
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: %s", pdf_path)
        raise FileNotFoundError(f"[Error] PDF file not found: %s", pdf_path)
    
    all_text = ""
    ocr_data = []
    
    try:
        # Attempt digital text extraction
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    all_text += text + "\n"
        
        if all_text.strip():
            logger.info("[✔] Digital text extracted.")
            return 1, all_text, []
        
        # Fallback to OCR
        logger.info("[ℹ] No digital text found, attempting OCR...")
        status_code, ocr_text, ocr_data = extract_text_from_scanned_pdf(pdf_path)
        
        if status_code == 0 and not ocr_text.strip():
            logger.info("Retrying OCR with DPI=400...")
            status_code, ocr_text, ocr_data = extract_text_from_scanned_pdf(pdf_path, dpi=400)
        
        if status_code == 1 and ocr_text.strip():
            logger.info("[✔] OCR text extracted.")
            return 1, ocr_text, ocr_data
        logger.error("[❌] OCR extraction failed.")
        return 0, "", []
    
    except fitz.FileDataError:
        logger.error(f"[Error] Corrupted or invalid PDF: %s", pdf_path)
        raise RuntimeError(f"[Error] Corrupted or invalid PDF: %s", pdf_path)
    except Exception as e:
        logger.error(f"[Error] Failed to process PDF: %s", e)
        raise RuntimeError(f"[Error] Failed to process PDF: %s", e)
