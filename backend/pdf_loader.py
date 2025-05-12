import fitz  # PyMuPDF
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_pdf_text(pdf_path):
    """
    Extract text from a PDF file using PyMuPDF.
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        str: Extracted text
    """
    try:
        doc = fitz.open(pdf_path)
        text = ""
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text()
        
        doc.close()
        logger.info(f"Successfully extracted text from {pdf_path}")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        return ""

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
            "file_size": doc.stream_length
        }
        doc.close()
        return metadata
    except Exception as e:
        logger.error(f"Error getting PDF metadata: {str(e)}")
        return {}
