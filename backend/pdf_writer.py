import fitz
import logging
from typing import List, Tuple, Optional
from backend.redactor import generate_fake_data, partial_redact
from backend.ocr_utils import extract_text_from_scanned_pdf
from PIL import ImageDraw

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def draw_redaction(page, rect, redaction_type, text=None, font_size=11, custom_mask_text=None):
    try:
        if redaction_type == "black_bar":
            page.draw_rect(rect, color=(0, 0, 0), fill=(0, 0, 0), overlay=True)
        elif redaction_type == "white_bar":
            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
        elif redaction_type == "custom" and custom_mask_text:
            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
            page.insert_text(rect.tl, text=custom_mask_text, fontsize=font_size, color=(0, 0, 0))
        elif redaction_type == "masked":
            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
            page.insert_text(rect.tl, text="*" * len(text), fontsize=font_size, color=(0, 0, 0))
        elif redaction_type == "numbered" and text:
            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
            page.insert_text(rect.tl, text=text, fontsize=font_size, color=(0, 0, 0))
        elif redaction_type == "random":
            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
            page.insert_text(rect.tl, text=text, fontsize=font_size, color=(0, 0, 0))
        elif redaction_type == "partial":
            # For digital PDFs, partial redaction is handled in redactor.py and not needed here.
            pass
        logger.info(f"Redacted {rect} with {redaction_type}")
    except Exception as e:
        logger.error(f"Drawing redaction failed: {e}")

def find_text_instances(page, text_to_find):
    try:
        text_instances = page.search_for(text_to_find)
        return text_instances
    except Exception as e:
        logger.error(f"Finding text instances failed: {e}")
        return []

def redact_pdf(
    input_pdf,
    output_pdf,
    redaction_type,
    entities_to_redact,
    custom_mask_text=None,
    threshold=0.2,
    scanned=False
):
    """
    Redact PII in a PDF based on detected entities.
    For scanned PDFs, use OCR bounding boxes and draw on images.
    For digital PDFs, redact text layer as before.
    """
    if not scanned:
        # Digital PDF: redact as before
        try:
            doc = fitz.open(input_pdf)
            redactions_applied = False
            entity_counters = {}
            if redaction_type == "numbered":
                for _, entity_type, _, _ in entities_to_redact:
                    if entity_type not in entity_counters:
                        entity_counters[entity_type] = 0
                    entity_counters[entity_type] += 1
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                for entity_text, entity_type, start, end in entities_to_redact:
                    text_instances = find_text_instances(page, entity_text)
                    replacement_text = None
                    if redaction_type == "random":
                        replacement_text = generate_fake_data(entity_type, entity_text)
                        if replacement_text and len(replacement_text) > len(entity_text):
                            replacement_text = replacement_text[:len(entity_text)]
                    elif redaction_type == "masked":
                        replacement_text = "*" * len(entity_text)
                    elif redaction_type == "numbered":
                        entity_counters[entity_type] -= 1
                        count_number = entity_counters[entity_type] + 1
                        replacement_text = f"{entity_type} {count_number}"
                    elif redaction_type == "custom":
                        replacement_text = custom_mask_text
                    elif redaction_type == "partial" and entity_type in ["PAN", "AADHAAR", "CREDIT_CARD"]:
                        replacement_text = partial_redact(entity_text, entity_type)
                    for rect in text_instances:
                        draw_redaction(
                            page=page,
                            rect=rect,
                            redaction_type=redaction_type,
                            text=replacement_text,
                            custom_mask_text=custom_mask_text
                        )
                        redactions_applied = True
            doc.save(output_pdf, garbage=4, deflate=True)
            doc.close()
            return redactions_applied
        except Exception as e:
            logger.error(f"PDF redaction failed: {e}")
            return False
    else:
        # Scanned PDF: redact on images using OCR bounding boxes
        try:
            success, _, ocr_data_pages = extract_text_from_scanned_pdf(input_pdf)
            if not success:
                return False
            from PIL import Image
            import re
            redacted_images = []
            for img, ocr_data in ocr_data_pages:
                draw = ImageDraw.Draw(img)
                for i, word in enumerate(ocr_data["text"]):
                    orig = word.strip()
                    if not orig:
                        continue
                    for entity_text, entity_type, _, _ in entities_to_redact:
                        # For partial, match last 4 digits/letters
                        if (
                            redaction_type == "partial"
                            and entity_type in ["PAN", "AADHAAR", "CREDIT_CARD"]
                            and orig[-4:] == entity_text.strip()[-4:]
                        ) or (orig == entity_text.strip()):
                            x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
                            if redaction_type == "black_bar":
                                draw.rectangle([x, y, x + w, y + h], fill="black")
                            elif redaction_type == "white_bar":
                                draw.rectangle([x, y, x + w, y + h], fill="white")
                            elif redaction_type == "masked":
                                draw.rectangle([x, y, x + w, y + h], fill="white")
                                draw.text((x, y), "*" * len(orig), fill="black")
                            elif redaction_type == "random":
                                draw.rectangle([x, y, x + w, y + h], fill="white")
                                draw.text((x, y), generate_fake_data(entity_type), fill="black")
                            elif redaction_type == "custom" and custom_mask_text:
                                draw.rectangle([x, y, x + w, y + h], fill="white")
                                draw.text((x, y), custom_mask_text, fill="black")
                            elif redaction_type == "numbered":
                                draw.rectangle([x, y, x + w, y + h], fill="white")
                                draw.text((x, y), f"{entity_type}", fill="black")
                            elif redaction_type == "partial" and entity_type in ["PAN", "AADHAAR", "CREDIT_CARD"]:
                                masked = partial_redact(orig, entity_type)
                                draw.rectangle([x, y, x + w, y + h], fill="white")
                                draw.text((x, y), masked, fill="black")
                redacted_images.append(img.convert("RGB"))
            # Save all images as PDF
            if redacted_images:
                redacted_images[0].save(output_pdf, save_all=True, append_images=redacted_images[1:])
                return True
            return False
        except Exception as e:
            logger.error(f"Image-based PDF redaction failed: {e}")
            return False
