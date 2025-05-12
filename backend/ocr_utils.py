import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import cv2
import numpy as np
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TESSERACT_PATH = os.environ.get("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    logger.warning(f"Tesseract not found at {TESSERACT_PATH}. OCR may not work properly.")

def preprocess_image(image):
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    _, thresh = cv2.threshold(denoised, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh)

def extract_text_from_scanned_pdf(pdf_path, dpi=300):
    try:
        images = convert_from_path(pdf_path, dpi=dpi)
        ocr_text = ""
        ocr_data_pages = []
        for img in images:
            processed = preprocess_image(img)
            text = pytesseract.image_to_string(processed, lang="eng")
            ocr_data = pytesseract.image_to_data(processed, lang="eng", output_type=pytesseract.Output.DICT)
            ocr_text += text + "\n"
            ocr_data_pages.append((img, ocr_data))
        return True, ocr_text, ocr_data_pages
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return False, "", []
