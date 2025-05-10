from presidio_analyzer import AnalyzerEngine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    analyzer = AnalyzerEngine(supported_languages=["en"])
    logger.info("Presidio Analyzer initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Presidio analyzer: {e}")
    raise