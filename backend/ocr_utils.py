import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import cv2
import numpy as np
import os
import logging
import re

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set Tesseract path
TESSERACT_PATH = os.environ.get("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if not os.path.exists(TESSERACT_PATH):
    logger.error(f"Tesseract not found at {TESSERACT_PATH}.")
    raise FileNotFoundError(f"Tesseract not found at {TESSERACT_PATH}")
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

def preprocess_image(image, use_fallback=False):
    """
    Preprocess image for better OCR accuracy.
    """
    img = np.array(image)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if use_fallback:
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        kernel = np.ones((3,3), np.uint8)
        thresh = cv2.dilate(thresh, kernel, iterations=1)
        thresh = cv2.erode(thresh, kernel, iterations=1)
    
    denoised = cv2.fastNlMeansDenoising(thresh)
    return Image.fromarray(cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB))

def clean_ocr_text(text):
    """
    Clean OCR-extracted text to improve PII detection.
    """
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s\-@.]', '', text)
    text = re.sub(r'(\d{4})\s*\-?\s*(\d{4})\s*\-?\s*(\d{4})', r'\1 \2 \3', text)  # Aadhaar
    text = re.sub(r'(\d{3})\s*\-?\s*(\d{2})\s*\-?\s*(\d{4})', r'\1-\2-\3', text)  # SSN
    text = re.sub(r'(\d{4})\s*\-?\s*(\d{4})\s*\-?\s*(\d{4})\s*\-?\s*(\d{4})', r'\1 \2 \3 \4', text)  # Credit card
    text = re.sub(r'([A-Z]{5})\s*(\d{4})\s*([A-Z])', r'\1\2\3', text)  # PAN
    return text.strip()

def extract_text_from_scanned_pdf(pdf_path, dpi=300):
    """
    Extracts text from scanned PDF using OCR with image preprocessing.
    """
    if not os.path.isfile(pdf_path):
        logger.error(f"The file '{pdf_path}' does not exist.")
        return 0, "", []
    
    try:
        POPPLER_PATH = os.environ.get("POPPLER_PATH")
        if not POPPLER_PATH:
            POPPLER_PATH = r"C:\Users\sunny\Anaconda3\envs\final_pdf_redactor\Library\bin"
            if not os.path.exists(os.path.join(POPPLER_PATH, "pdftoppm.exe")):
                POPPLER_PATH = r"C:\Program Files\poppler-24.08.0\Library\bin"
                if not os.path.exists(os.path.join(POPPLER_PATH, "pdftoppm.exe")):
                    logger.error(f"Poppler not found at {POPPLER_PATH}.")
                    return 0, "", []
        
        logger.info(f"Converting {pdf_path} to images with {dpi} DPI...")
        images = convert_from_path(pdf_path, dpi=dpi, poppler_path=POPPLER_PATH)
        
        ocr_text_pages = []
        total_pages = len(images)
        
        for i, image in enumerate(images):
            logger.info(f"Processing Page {i+1}/{total_pages}...")
            
            for attempt_dpi in [dpi, 400, 600]:
                processed_image = preprocess_image(image)
                ocr_data = pytesseract.image_to_data(
                    processed_image, lang="eng", output_type=pytesseract.Output.DICT
                )
                
                page_text = []
                for j, text in enumerate(ocr_data['text']):
                    if text.strip() and float(ocr_data['conf'][j]) > 20:
                        scale_factor = 72.0 / attempt_dpi
                        cleaned_text = clean_ocr_text(text.strip())
                        page_text.append({
                            'text': cleaned_text,
                            'left': ocr_data['left'][j] * scale_factor,
                            'top': ocr_data['top'][j] * scale_factor,
                            'width': ocr_data['width'][j] * scale_factor,
                            'height': ocr_data['height'][j] * scale_factor,
                            'conf': ocr_data['conf'][j]
                        })
                        logger.debug(f"OCR text: '{cleaned_text}' (conf: {ocr_data['conf'][j]})")
                
                if page_text:
                    break
                
                logger.warning(f"No text on Page {i+1} with DPI {attempt_dpi}. Retrying with fallback preprocessing...")
                processed_image = preprocess_image(image, use_fallback=True)
                ocr_data = pytesseract.image_to_data(
                    processed_image, lang="eng", output_type=pytesseract.Output.DICT
                )
                for j, text in enumerate(ocr_data['text']):
                    if text.strip() and float(ocr_data['conf'][j]) > 20:
                        scale_factor = 72.0 / attempt_dpi
                        cleaned_text = clean_ocr_text(text.strip())
                        page_text.append({
                            'text': cleaned_text,
                            'left': ocr_data['left'][j] * scale_factor,
                            'top': ocr_data['top'][j] * scale_factor,
                            'width': ocr_data['width'][j] * scale_factor,
                            'height': ocr_data['height'][j] * scale_factor,
                            'conf': ocr_data['conf'][j]
                        })
                        logger.debug(f"OCR text (fallback): '{cleaned_text}' (conf: {ocr_data['conf'][j]})")
                
                if page_text:
                    break
            
            if page_text:
                raw_text = clean_ocr_text(pytesseract.image_to_string(processed_image, lang="eng"))
                ocr_text_pages.append({
                    'page': i + 1,
                    'text_data': page_text,
                    'raw_text': raw_text
                })
            else:
                logger.warning(f"No reliable text on Page {i+1} after retries.")
        
        final_text = "\n".join([page['raw_text'] for page in ocr_text_pages])
        if final_text:
            logger.info("OCR extraction completed successfully.")
            return 1, final_text, ocr_text_pages
        logger.warning("No text detected in the document.")
        return 0, "", []
    
    except Exception as e:
        logger.error(f"OCR failed for {pdf_path}: %s", e)
        return 0, "", []