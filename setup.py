import os
import sys
import logging
import spacy.util
import paddleocr

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default Poppler path
DEFAULT_POPPLER_PATH = r"C:\Program Files\poppler-24.08.0\Library\bin"

def check_poppler():
    """Check if Poppler is installed and POPPLER_PATH is set."""
    poppler_path = os.environ.get("POPPLER_PATH", DEFAULT_POPPLER_PATH)
    if not os.path.exists(os.path.join(poppler_path, "pdftoppm.exe")):
        logger.error(
            f"Poppler not found at '{poppler_path}'. "
            "Install Poppler and set POPPLER_PATH environment variable or ensure it is installed at "
            "'C:\\Program Files\\poppler-24.08.0\\Library\\bin'. "
            "Download from: https://github.com/oschwartz10612/poppler-windows."
        )
        return False
    logger.info(f"Poppler found at: {poppler_path}")
    return True

def check_spacy_model():
    """Check if spaCy model 'en_core_web_lg' is installed."""
    if not spacy.util.is_package("en_core_web_lg"):
        logger.error(
            "spaCy model 'en_core_web_lg' not found. Install with: python -m spacy download en_core_web_lg"
        )
        return False
    logger.info("spaCy model 'en_core_web_lg' found")
    return True

def check_paddleocr():
    """Check if PaddleOCR initializes correctly."""
    try:
        paddleocr.PaddleOCR(
            use_angle_cls=True,
            lang="en",
            use_gpu=False,
            det_model_dir=None,
            rec_model_dir=None,
            cls_model_dir=None
        )
        logger.info("PaddleOCR initialized successfully")
        return True
    except Exception as e:
        logger.error(f"PaddleOCR initialization failed: {e}")
        return False

def main():
    """Run all dependency checks."""
    logger.info("Checking dependencies for PDF PII Redactor...")
    all_checks_passed = True
    
    if not check_poppler():
        all_checks_passed = False
    if not check_spacy_model():
        all_checks_passed = False
    if not check_paddleocr():
        all_checks_passed = False
    
    if all_checks_passed:
        logger.info("All dependency checks passed. You can run the application.")
    else:
        logger.error("One or more dependency checks failed. Please resolve the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()