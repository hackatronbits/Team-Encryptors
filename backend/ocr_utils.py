import paddleocr
from pdf2image import convert_from_path
from PIL import Image
import cv2
import numpy as np
import os
import logging
import re
from scipy import ndimage

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress ccache warning (optional)
os.environ["PADDLE_SUPPRESS_CMAKE_WARNING"] = "1"

# Default Poppler path (specific to your system)
DEFAULT_POPPLER_PATH = r"C:\Program Files\poppler-24.08.0\Library\bin"

# Initialize PaddleOCR
try:
    ocr = paddleocr.PaddleOCR(
        use_angle_cls=True,
        lang="en",
        use_gpu=False,  # Set to True if GPU is configured
        det_model_dir=None,
        rec_model_dir=None,
        cls_model_dir=None
    )
except Exception as e:
    logger.error(f"Failed to initialize PaddleOCR: {e}")
    raise RuntimeError(f"PaddleOCR initialization failed: {e}")

def check_image_quality(image):
    """
    Check image quality to ensure OCR accuracy (e.g., detect blur).
    Returns True if quality is sufficient, False otherwise.
    """
    try:
        img = np.array(image)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        threshold = 100  # Adjust based on testing
        if laplacian_var < threshold:
            logger.warning(f"Low image quality detected (Laplacian variance: {laplacian_var})")
            return False
        return True
    except Exception as e:
        logger.error(f"Image quality check failed: {e}")
        return True  # Proceed with OCR to avoid blocking

def preprocess_image(image):
    """
    Advanced preprocessing for PaddleOCR: grayscale, normalization, deskewing, noise reduction, and contrast enhancement.
    """
    try:
        img = np.array(image)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # Noise reduction (Gaussian blur)
        img = cv2.GaussianBlur(img, (3, 3), 0)
        
        # Contrast enhancement (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        img = clahe.apply(img)
        
        # Deskewing (correct text rotation)
        angle = estimate_skew_angle(img)
        if abs(angle) > 0.1:
            img = ndimage.rotate(img, angle, reshape=False, mode='nearest')
        
        # Normalization
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)
        
        return Image.fromarray(img)
    except Exception as e:
        logger.error(f"Image preprocessing failed: {e}")
        return image

def estimate_skew_angle(image):
    """
    Estimate the skew angle of text in the image using Hough transform.
    """
    try:
        edges = cv2.Canny(image, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
        if lines is not None:
            angles = []
            for rho, theta in lines[0]:
                angle = (theta * 180 / np.pi) - 90
                if abs(angle) < 45:  # Consider near-horizontal lines
                    angles.append(angle)
            if angles:
                return np.median(angles)
        return 0.0
    except Exception as e:
        logger.warning(f"Skew angle estimation failed: {e}")
        return 0.0

def clean_ocr_text(text):
    """
    Clean OCR-extracted text to improve PII detection with context-aware formatting.
    """
    if not text:
        return ""
    
    try:
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove unwanted characters, preserving PII-relevant ones
        text = re.sub(r'[^\w\s\-@./]', '', text)
        
        # Format specific PII types
        # Aadhaar (12 digits, with or without spaces)
        text = re.sub(r'(\d{4})\s*[-.]?\s*(\d{4})\s*[-.]?\s*(\d{4})', r'\1 \2 \3', text)
        # SSN (XXX-XX-XXXX)
        text = re.sub(r'(\d{3})\s*[-.]?\s*(\d{2})\s*[-.]?\s*(\d{4})', r'\1-\2-\3', text)
        # Credit card (16 digits, with or without spaces/dashes)
        text = re.sub(r'(\d{4})\s*[-.]?\s*(\d{4})\s*[-.]?\s*(\d{4})\s*[-.]?\s*(\d{4})', r'\1 \2 \3 \4', text)
        # PAN (AAAAA9999A)
        text = re.sub(r'([A-Z]{5})\s*(\d{4})\s*([A-Z])', r'\1\2\3', text)
        # Phone numbers (various formats)
        text = re.sub(r'(\+91|0)?\s*([789]\d{2})\s*[-.]?\s*(\d{3})\s*[-.]?\s*(\d{4})', r'\1\2\3\4', text)
        text = re.sub(r'(\d{3})\s*[-.]?\s*(\d{3})\s*[-.]?\s*(\d{4})', r'\1-\2-\3', text)
        # Email addresses
        text = re.sub(r'(\w+\.?\w*)\s*@\s*(\w+\.\w+)', r'\1@\2', text)
        
        return text.strip()
    except Exception as e:
        logger.error(f"Text cleaning failed: {e}")
        return text.strip()

def extract_text_from_scanned_pdf(pdf_path, dpi=200):
    """
    Extracts text from scanned PDF using PaddleOCR with advanced preprocessing.
    
    Args:
        pdf_path (str): Path to the PDF file
        dpi (int): Resolution for PDF-to-image conversion (default: 200)
    
    Returns:
        tuple: (status_code, final_text, ocr_text_pages)
            - status_code: 1 (success), 0 (failure)
            - final_text: Concatenated text from all pages
            - ocr_text_pages: List of page data with text and bounding boxes
    """
    if not os.path.isfile(pdf_path):
        logger.error(f"The file '{pdf_path}' does not exist.")
        return 0, "", []
    
    try:
        # Try environment variable first, fall back to default Poppler path
        POPPLER_PATH = os.environ.get("POPPLER_PATH", DEFAULT_POPPLER_PATH)
        if not os.path.exists(os.path.join(POPPLER_PATH, "pdftoppm.exe")):
            error_msg = (
                f"Poppler not found at '{POPPLER_PATH}'. "
                "Install Poppler and set POPPLER_PATH environment variable or ensure it is installed at "
                "'C:\\Program Files\\poppler-24.08.0\\Library\\bin'. "
                "Download from: https://github.com/oschwartz10612/poppler-windows."
            )
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        logger.info(f"Converting {pdf_path} to images with {dpi} DPI using Poppler at {POPPLER_PATH}...")
        images = convert_from_path(pdf_path, dpi=dpi, poppler_path=POPPLER_PATH)
        
        ocr_text_pages = []
        total_pages = len(images)
        total_confidence = []
        
        for i, image in enumerate(images):
            logger.info(f"Processing Page {i+1}/{total_pages}...")
            
            # Check image quality
            if not check_image_quality(image):
                logger.warning(f"Low quality image on page {i+1}. OCR accuracy may be reduced.")
            
            processed_image = preprocess_image(image)
            
            result = ocr.ocr(np.array(processed_image), cls=True)
            
            page_text = []
            raw_text = ""
            if result and result[0]:
                scale_factor = 72.0 / dpi
                for line in result[0]:
                    bbox, (text, confidence) = line
                    # Adaptive confidence threshold: lower for sparse pages
                    page_conf_threshold = 0.5 if total_confidence else 0.3
                    if confidence > page_conf_threshold:
                        cleaned_text = clean_ocr_text(text.strip())
                        if cleaned_text:
                            x0, y0 = bbox[0][0], bbox[0][1]
                            width = bbox[2][0] - x0
                            height = bbox[2][1] - y0
                            page_text.append({
                                'text': cleaned_text,
                                'left': x0 * scale_factor,
                                'top': y0 * scale_factor,
                                'width': width * scale_factor,
                                'height': height * scale_factor,
                                'conf': confidence
                            })
                            raw_text += cleaned_text + " "
                            total_confidence.append(confidence)
                            logger.debug(f"OCR text: '{cleaned_text}' (conf: {confidence})")
            
            if page_text:
                ocr_text_pages.append({
                    'page': i + 1,
                    'text_data': page_text,
                    'raw_text': clean_ocr_text(raw_text.strip())
                })
            else:
                logger.warning(f"No reliable text on Page {i+1}.")
                ocr_text_pages.append({
                    'page': i + 1,
                    'text_data': [],
                    'raw_text': ""
                })
        
        final_text = "\n".join([page['raw_text'] for page in ocr_text_pages if page['raw_text']])
        if final_text:
            logger.info("OCR extraction completed successfully.")
            return 1, final_text, ocr_text_pages
        logger.warning("No text detected in the document.")
        return 0, "", ocr_text_pages
    
    except FileNotFoundError as e:
        logger.error(f"OCR failed for {pdf_path}: {e}")
        return 0, "", []
    except Exception as e:
        logger.error(f"OCR failed for {pdf_path}: {e}")
        return 0, "", []