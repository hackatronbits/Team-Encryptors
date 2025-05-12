import fitz  # PyMuPDF
import logging
import os
from backend.ocr_utils import extract_text_from_scanned_pdf

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_pdf_text(pdf_path):
    """
    Extract text from a PDF file using PyMuPDF, falling back to PaddleOCR for scanned PDFs.
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        tuple: (status_code, text, ocr_text_pages)
            - status_code: 1 (success), 0 (failure)
            - text: Extracted text
            - ocr_text_pages: List of OCR data (empty for text-based PDFs)
    """
    if not os.path.isfile(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        return 0, "", []
    
    try:
        # Validate PDF integrity
        with open(pdf_path, 'rb') as f:
            header = f.read(8)
            if not header.startswith(b'%PDF-'):
                logger.error(f"Invalid PDF file: {pdf_path}")
                return 0, "", []
        
        doc = fitz.open(pdf_path)
        text = ""
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text()
            text += page_text
        
        doc.close()
        logger.info(f"Extracted text from {pdf_path} using PyMuPDF")
        
        # Improved heuristic: Check text density (characters per page)
        avg_text_per_page = len(text.strip()) / max(1, len(doc))
        if avg_text_per_page > 10:  # Threshold for meaningful text
            return 1, text, []
        
        # Fall back to OCR for scanned PDFs
        logger.info(f"Insufficient text extracted from {pdf_path} (avg {avg_text_per_page:.1f} chars/page). Attempting OCR...")
        return extract_text_from_scanned_pdf(pdf_path)
    
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        # Try OCR as a fallback
        logger.info(f"Attempting OCR for {pdf_path}...")
        return extract_text_from_scanned_pdf(pdf_path)

def get_pdf_metadata(pdf_path):
    """
    Get metadata from a PDF file.
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        dict: PDF metadata
    """
    try:
        doc = fitz.open(pdf_path)
        metadata = {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "keywords": doc.metadata.get("keywords", ""),
            "creator": doc.metadata.get("creator", ""),
            "producer": doc.metadata.get("producer", ""),
            "creation_date": doc.metadata.get("creationDate", ""),
            "modification_date": doc.metadata.get("modDate", ""),
            "page_count": len(doc),
            "file_size": os.path.getsize(pdf_path)  # Fixed: Replaced stream_length
        }
        doc.close()
        logger.info(f"Extracted metadata from {pdf_path}")
        return metadata
    except Exception as e:
        logger.error(f"Error getting PDF metadata: {str(e)}")
        return {
            "title": "",
            "author": "",
            "subject": "",
            "keywords": "",
            "creator": "",
            "producer": "",
            "creation_date": "",
            "modification_date": "",
            "page_count": "Unknown",
            "file_size": 0
        }