import fitz  # PyMuPDF
from backend.pii_detector import detect_pii_entities
from backend.redactor import generate_fake_data
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Font path
FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "DejaVuSans.ttf")
font_name = "helv"
try:
    if os.path.exists(FONT_PATH):
        pdfmetrics.registerFont(TTFont("DejaVuSans", FONT_PATH))
        font_name = "DejaVuSans"
        logger.info("DejaVuSans font registered for reportlab.")
    else:
        logger.warning(f"Font file {FONT_PATH} not found. Using default font.")
except Exception as e:
    logger.warning(f"Failed to register DejaVuSans font: %s", e)
    font_name = "helv"

def merge_spans(spans):
    """
    Merge adjacent text spans to prevent PII splitting.
    """
    if not spans:
        return []
    
    merged = []
    current_text = spans[0]["text"]
    current_bbox = list(spans[0]["bbox"])
    current_size = spans[0]["size"]
    
    for span in spans[1:]:
        if (span["bbox"][1] == current_bbox[1] and
            abs(span["bbox"][0] - current_bbox[2]) < 5):
            current_text += " " + span["text"]
            current_bbox[2] = span["bbox"][2]
            current_size = min(current_size, span["size"])
        else:
            merged.append({
                "text": current_text,
                "bbox": current_bbox,
                "size": current_size
            })
            current_text = span["text"]
            current_bbox = list(span["bbox"])
            current_size = span["size"]
    
    merged.append({
        "text": current_text,
        "bbox": current_bbox,
        "size": current_size
    })
    return merged

def redact_pdf(input_path, output_path, ocr_data=None):
    """
    Redacts PII in the PDF while preserving layout.
    """
    try:
        doc = fitz.open(input_path)
        logger.info("PDF opened successfully.")
        
        pdf_font_name = font_name
        font_buffer = None
        if font_name == "DejaVuSans":
            try:
                with open(FONT_PATH, "rb") as font_file:
                    font_buffer = font_file.read()
                font = fitz.Font(fontbuffer=font_buffer, fontname="DejaVuSans")
                if not font.is_writable:
                    raise ValueError("DejaVuSans font is not writable.")
                logger.info("DejaVuSans font loaded for PyMuPDF.")
            except Exception as e:
                logger.error(f"Failed to load DejaVuSans for PyMuPDF: %s. Using helv.", e)
                pdf_font_name = "helv"
                font_buffer = None
        
        is_scanned = bool(ocr_data)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            logger.info(f"Processing page {page_num + 1} of {len(doc)}.")
            
            if is_scanned:
                page_data = next((p for p in ocr_data if p['page'] == page_num + 1), None)
                if not page_data:
                    logger.warning(f"No OCR data for page {page_num + 1}.")
                    continue
                
                for item in page_data['text_data']:
                    text = item['text']
                    bbox = (item['left'], item['top'], item['left'] + item['width'], item['top'] + item['height'])
                    rect = fitz.Rect(bbox)
                    
                    entities = detect_pii_entities(text)
                    if not entities:
                        continue
                    
                    page.draw_rect(rect, fill=(1, 1, 1), overlay=True)
                    
                    font_size = max(6, min(12, item['height'] * 0.6))
                    logger.debug(f"Scanned: Font size {font_size}, bbox {bbox} for text: '{text}'")
                    
                    redacted_text = text
                    for entity_text, label, _, _ in entities:
                        fake_text = generate_fake_data(label, len(entity_text))
                        redacted_text = redacted_text.replace(entity_text, fake_text)
                        logger.debug(f"Scanned: Replacing '{entity_text}' with '{fake_text}'")
                    
                    for attempt in range(3):
                        try:
                            logger.debug(f"Attempt {attempt + 1} to insert '{redacted_text}' with font {pdf_font_name}")
                            if pdf_font_name == "DejaVuSans" and font_buffer:
                                page.insert_textbox(
                                    rect,
                                    redacted_text,
                                    fontfile=FONT_PATH,
                                    fontsize=font_size,
                                    color=(0, 0, 0),
                                    align=0,
                                    overlay=True
                                )
                            else:
                                page.insert_textbox(
                                    rect,
                                    redacted_text,
                                    fontname="helv",
                                    fontsize=font_size,
                                    color=(0, 0, 0),
                                    align=0,
                                    overlay=True
                                )
                            logger.info(f"Inserted redacted text '{redacted_text}' on page {page_num + 1}")
                            break
                        except Exception as e:
                            logger.error(f"Text insertion attempt {attempt + 1} failed: %s", e)
                            if attempt < 2:
                                font_size *= 0.8
                                rect = fitz.Rect(bbox[0], bbox[1] - 2, bbox[2], bbox[3] + 2)
                                logger.warning(f"Retrying with font size {font_size}, adjusted bbox {rect}")
                            else:
                                logger.error(f"Final insertion failed, using REDACTED: %s", e)
                                page.insert_textbox(
                                    rect,
                                    "REDACTED",
                                    fontname="helv",
                                    fontsize=font_size,
                                    color=(0, 0, 0),
                                    align=0,
                                    overlay=True
                                )
            else:
                blocks = page.get_text("dict")["blocks"]
                for block in blocks:
                    if "lines" not in block:
                        continue
                    
                    for line in block["lines"]:
                        merged_spans = merge_spans(line["spans"])
                        for span in merged_spans:
                            original_text = span["text"]
                            if not original_text.strip():
                                continue
                            
                            entities = detect_pii_entities(original_text)
                            if not entities:
                                continue
                            
                            rect = fitz.Rect(span["bbox"])
                            page.draw_rect(rect, fill=(1, 1, 1), overlay=True)
                            
                            font_size = max(6, min(12, span["size"] * 0.8))
                            logger.debug(f"Digital: Font size {font_size}, bbox {rect} for text: '{original_text}'")
                            
                            redacted_text = original_text
                            for entity_text, label, _, _ in entities:
                                fake_text = generate_fake_data(label, len(entity_text))
                                redacted_text = redacted_text.replace(entity_text, fake_text)
                                logger.debug(f"Digital: Replacing '{entity_text}' with '{fake_text}'")
                            
                            for attempt in range(3):
                                try:
                                    logger.debug(f"Attempt {attempt + 1} to insert '{redacted_text}' with font {pdf_font_name}")
                                    if pdf_font_name == "DejaVuSans" and font_buffer:
                                        page.insert_textbox(
                                            rect,
                                            redacted_text,
                                            fontfile=FONT_PATH,
                                            fontsize=font_size,
                                            color=(0, 0, 0),
                                            align=0,
                                            overlay=True
                                        )
                                    else:
                                        page.insert_textbox(
                                            rect,
                                            redacted_text,
                                            fontname="helv",
                                            fontsize=font_size,
                                            color=(0, 0, 0),
                                            align=0,
                                            overlay=True
                                        )
                                    logger.info(f"Inserted redacted text '{redacted_text}' on page {page_num + 1}")
                                    break
                                except Exception as e:
                                    logger.error(f"Text insertion attempt {attempt + 1} failed: %s", e)
                                    if attempt < 2:
                                        font_size *= 0.8
                                        rect = fitz.Rect(rect[0], rect[1] - 2, rect[2], rect[3] + 2)
                                        logger.warning(f"Retrying with font size {font_size}, adjusted bbox {rect}")
                                    else:
                                        logger.error(f"Final insertion failed, using REDACTED: %s", e)
                                        page.insert_textbox(
                                            rect,
                                            "REDACTED",
                                            fontname="helv",
                                            fontsize=font_size,
                                            color=(0, 0, 0),
                                            align=0,
                                            overlay=True
                                        )
        
        doc.save(output_path, garbage=4, deflate=True, clean=True)
        doc.close()
        logger.info(f"Redacted PDF saved to: {output_path}")
    except Exception as e:
        logger.error(f"Failed to redact PDF: %s", e)
        raise