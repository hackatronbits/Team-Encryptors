import fitz  # PyMuPDF
import os
import logging
from backend.redactor import generate_fake_data, mask_text
from backend.pii_detector import detect_pii_entities

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def draw_redaction(page, rect, redaction_type, text=None, font_size=11, custom_mask_text=None):
    """
    Draw redaction on a PDF page.
    
    Args:
        page: PyMuPDF page object
        rect: Rectangle coordinates (x0, y0, x1, y1)
        redaction_type: Type of redaction (black_bar, white_bar, random, masked, custom)
        text: Text to insert (for random and masked types)
        font_size: Font size for inserted text
        custom_mask_text: Custom text to use for masking
    """
    try:
        # Dynamically adjust font size based on rectangle height
        adjusted_font_size = min(font_size, rect.height * 0.8)
        
        if redaction_type == "black_bar":
            page.draw_rect(rect, color=(0, 0, 0), fill=(0, 0, 0), overlay=True)
        elif redaction_type == "white_bar":
            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
        elif redaction_type == "custom" and custom_mask_text:
            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
            page.insert_text(
                point=(rect[0], rect[1] + adjusted_font_size/2),
                text=custom_mask_text,
                fontsize=adjusted_font_size,
                color=(0, 0, 0)
            )
        elif text and (redaction_type == "random" or redaction_type == "masked"):
            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
            page.insert_text(
                point=(rect[0], rect[1] + adjusted_font_size/2),
                text=text,
                fontsize=adjusted_font_size,
                color=(0, 0, 0)
            )
        logger.info(f"Applied {redaction_type} redaction to rectangle {rect}")
    except Exception as e:
        logger.error(f"Error applying redaction: {e}")

def find_text_instances(page, text_to_find):
    """
    Find all instances of text on a page and return their rectangles.
    Includes partial and case-insensitive matching as fallback.
    """
    try:
        text_instances = page.search_for(text_to_find)
        if not text_instances:
            normalized_text = ' '.join(text_to_find.split())
            text_instances = page.search_for(normalized_text)
        if not text_instances:
            text_instances = page.search_for(text_to_find.lower())
        if not text_instances:
            text_instances = page.search_for(text_to_find.upper())
        if not text_instances:
            # Partial match as last resort
            words = text_to_find.split()
            if words:
                text_instances = page.search_for(words[0])
        return text_instances
    except Exception as e:
        logger.error(f"Error finding text instances for '{text_to_find}': {e}")
        return []

def redact_pdf(input_pdf, output_pdf, redaction_type="random", selected_entities=None, threshold=0.3, custom_mask_text=None, ocr_text_pages=None):
    """
    Redact PII in a PDF file using Presidio for detection.
    
    Args:
        input_pdf (str): Path to input PDF
        output_pdf (str): Path to save redacted PDF
        redaction_type (str): Type of redaction (black_bar, white_bar, random, masked, custom)
        selected_entities (list): List of entity types to redact
        threshold (float): Confidence threshold for PII detection
        custom_mask_text (str): Custom text to use for masking
        ocr_text_pages (list): OCR data with bounding boxes (for scanned PDFs)
    
    Returns:
        bool: True if redactions were applied, False otherwise
    """
    try:
        # Validate PDF
        with open(input_pdf, 'rb') as f:
            if not f.read(8).startswith(b'%PDF-'):
                logger.error(f"Invalid PDF file: {input_pdf}")
                return False
        
        doc = fitz.open(input_pdf)
        redactions_applied = False
        
        if ocr_text_pages:
            # Scanned PDF: Use OCR bounding boxes
            logger.info("Processing scanned PDF with OCR data")
            for page_data in ocr_text_pages:
                page_num = page_data['page'] - 1
                page = doc.load_page(page_num)
                page_text = page_data['raw_text']
                
                entities = detect_pii_entities(
                    page_text,
                    threshold=threshold,
                    selected_entities=selected_entities
                )
                
                if not entities:
                    logger.info(f"No entities found on page {page_num+1}")
                    continue
                
                logger.info(f"Found {len(entities)} entities on page {page_num+1}")
                
                for entity_text, entity_type, start, end in entities:
                    # Find matching OCR text segments
                    for text_data in page_data['text_data']:
                        if entity_text in text_data['text']:
                            rect = fitz.Rect(
                                text_data['left'],
                                text_data['top'],
                                text_data['left'] + text_data['width'],
                                text_data['top'] + text_data['height']
                            )
                            replacement = None
                            if redaction_type == "random":
                                replacement = generate_fake_data(entity_type, entity_text)
                                if len(replacement) > len(entity_text):
                                    replacement = replacement[:len(entity_text)]
                            elif redaction_type == "masked":
                                replacement = mask_text(entity_text)
                            elif redaction_type == "custom":
                                replacement = custom_mask_text
                            
                            draw_redaction(page, rect, redaction_type, text=replacement, custom_mask_text=custom_mask_text)
                            logger.info(f"Redacted '{entity_text}' ({entity_type}) on page {page_num+1}")
                            redactions_applied = True
        else:
            # Text-based PDF: Use text search
            for page_num in range(len(doc)):
                logger.info(f"Processing page {page_num+1}/{len(doc)}")
                page = doc.load_page(page_num)
                page_text = page.get_text()
                
                entities = detect_pii_entities(
                    page_text,
                    threshold=threshold,
                    selected_entities=selected_entities
                )
                
                if not entities:
                    logger.info(f"No entities found on page {page_num+1}")
                    continue
                
                logger.info(f"Found {len(entities)} entities on page {page_num+1}")
                
                for entity_text, entity_type, start, end in entities:
                    text_instances = find_text_instances(page, entity_text)
                    
                    if not text_instances:
                        logger.warning(f"Could not find text '{entity_text}' on page {page_num+1}")
                        continue
                    
                    replacement = None
                    if redaction_type == "random":
                        replacement = generate_fake_data(entity_type, entity_text)
                        if len(replacement) > len(entity_text):
                            replacement = replacement[:len(entity_text)]
                    elif redaction_type == "masked":
                        replacement = mask_text(entity_text)
                    elif redaction_type == "custom":
                        replacement = custom_mask_text
                    
                    for rect in text_instances:
                        draw_redaction(page, rect, redaction_type, text=replacement, custom_mask_text=custom_mask_text)
                        logger.info(f"Redacted '{entity_text}' ({entity_type}) on page {page_num+1}")
                        redactions_applied = True
        
        doc.save(output_pdf, garbage=4, deflate=True, clean=True)
        doc.close()
        
        if redactions_applied:
            logger.info(f"Successfully redacted PDF and saved to {output_pdf}")
            return True
        else:
            logger.warning("No redactions were applied to the PDF")
            return False
    
    except Exception as e:
        logger.error(f"Error redacting PDF: {e}")
        return False