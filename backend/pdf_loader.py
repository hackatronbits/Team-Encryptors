import fitz
import logging
from backend.ocr_utils import extract_text_from_scanned_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_pdf_text(pdf_path: str) -> str:
    """
    Extract text from a PDF file, using OCR if the PDF is scanned.
    """
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        if len(text.strip()) < 100:
            logger.info("PDF appears to be scanned. Using OCR...")
            success, ocr_text, _ = extract_text_from_scanned_pdf(pdf_path)
            if success:
                return ocr_text
        return text
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        return ""

def get_pdf_metadata(pdf_path: str) -> dict:
    """
    Extract metadata from the PDF.
    """
    try:
        doc = fitz.open(pdf_path)
        metadata = {
            "author": doc.metadata.get("author", ""),
            "title": doc.metadata.get("title", ""),
            "page_count": len(doc),
            "creation_date": doc.metadata.get("creationDate", ""),
            "modification_date": doc.metadata.get("modDate", "")
        }
        doc.close()
        return metadata
    except Exception as e:
        logger.error(f"Metadata extraction failed: {e}")
        return {}

def is_scanned_pdf(pdf_path: str) -> bool:
    """
    Returns True if the PDF appears to be scanned (little or no extractable text).
    """
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return len(text.strip()) < 100
    except Exception as e:
        logger.error(f"Error checking if PDF is scanned: {e}")
        return False
