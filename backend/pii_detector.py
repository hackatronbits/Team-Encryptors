import logging
from typing import List, Optional, Tuple

from presidio_analyzer import (
    AnalyzerEngine,
    RecognizerRegistry,
    PatternRecognizer,
    Pattern,
)
from presidio_analyzer.nlp_engine import NlpEngineProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPPORTED_ENTITIES = [
    "PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD", "DATE_TIME",
    "LOCATION", "ORGANIZATION", "PAN", "AADHAAR"
]

_analyzer_instance = None

def initialize_analyzer():
    try:
        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}]
        }
        provider = NlpEngineProvider(nlp_configuration=nlp_config)
        nlp_engine = provider.create_engine()
        registry = RecognizerRegistry()
        registry.load_predefined_recognizers(nlp_engine=nlp_engine)
        # PAN: 5 letters, 4 digits, 1 letter (e.g., ABCDE1234F)
        pan_pattern = Pattern("pan_card", r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", 0.85)
        pan_recognizer = PatternRecognizer(supported_entity="PAN", patterns=[pan_pattern])
        registry.add_recognizer(pan_recognizer)
        # Aadhaar: 12 digits, often with spaces (e.g., 1234 5678 9012)
        aadhaar_pattern = Pattern("aadhaar_card", r"\b\d{4}\s?\d{4}\s?\d{4}\b", 0.85)
        aadhaar_recognizer = PatternRecognizer(supported_entity="AADHAAR", patterns=[aadhaar_pattern])
        registry.add_recognizer(aadhaar_recognizer)
        analyzer = AnalyzerEngine(registry=registry, nlp_engine=nlp_engine)
        logger.info("Presidio Analyzer initialized successfully")
        return analyzer
    except Exception as e:
        logger.error(f"Error initializing Presidio Analyzer: {str(e)}")
        raise

def get_analyzer():
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = initialize_analyzer()
    return _analyzer_instance

def detect_pii_entities(
    text: str,
    threshold: float = 0.2,
    selected_entities: Optional[List[str]] = None
) -> List[Tuple[str, str, int, int]]:
    if not text or not isinstance(text, str):
        return []
    try:
        analyzer = get_analyzer()
        results = analyzer.analyze(
            text=text,
            language='en',
            entities=selected_entities,
            score_threshold=threshold
        )
        entities = []
        for result in results:
            entity_text = text[result.start:result.end]
            entities.append((entity_text, result.entity_type, result.start, result.end))
        logger.info(f"Detected {len(entities)} PII entities with threshold {threshold}")
        return entities
    except Exception as e:
        logger.error(f"Error detecting PII entities: {str(e)}")
        return []
