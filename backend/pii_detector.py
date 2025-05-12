import logging
import spacy
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.pattern_recognizer import PatternRecognizer


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Customized PII entity template for educational field
# IMPORTANT: This is the variable name that needs to be consistent with imports
CUSTOM_PII_ENTITY_TEMPLATE = [
    {"label": "PERSON", "description": "Names of individuals"},
    {"label": "PHONE_NUMBER", "description": "Phone numbers"},
    {"label": "DATE_TIME", "description": "Dates and times"},
    {"label": "EMAIL_ADDRESS", "description": "Email addresses"},
    {"label": "SCHOOL", "description": "School or institution names"},
    {"label": "AADHAAR", "description": "Indian Aadhaar numbers"},
    {"label": "PAN", "description": "Indian PAN numbers"},
    {"label": "CREDIT_CARD", "description": "Credit card numbers"}
]

# Cache the analyzer instance for better performance
_analyzer_instance = None

def create_custom_recognizers():
    """Create custom recognizers for educational field PII types"""
    recognizers = []
    
    # School/Institution recognizer
    school_recognizer = PatternRecognizer(
        supported_entity="SCHOOL",
        patterns=[
            {"name": "school_name", "regex": r"\b[A-Z][a-zA-Z\s]+ (?:School|College|University|Institute)\b", "score": 0.7},
            {"name": "school_abbr", "regex": r"\b[A-Z]{2,5}\b(?=\s+(?:University|College|School|Institute))", "score": 0.7}
        ]
    )
    
    # Aadhaar recognizer
    aadhaar_recognizer = PatternRecognizer(
        supported_entity="AADHAAR",
        patterns=[
            {"name": "aadhaar_with_spaces", "regex": r"\b\d{4}\s\d{4}\s\d{4}\b", "score": 0.8},
            {"name": "aadhaar_no_spaces", "regex": r"\b\d{12}\b", "score": 0.6}
        ]
    )
    
    # PAN recognizer
    pan_recognizer = PatternRecognizer(
        supported_entity="PAN",
        patterns=[
            {"name": "pan", "regex": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", "score": 0.8}
        ]
    )
    
    # Enhanced person recognizer (to supplement built-in)
    person_recognizer = PatternRecognizer(
        supported_entity="PERSON",
        patterns=[
            {"name": "full_name", "regex": r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", "score": 0.85}
        ]
    )
    
    # Enhanced phone recognizer
    phone_recognizer = PatternRecognizer(
        supported_entity="PHONE_NUMBER",
        patterns=[
            {"name": "us_phone", "regex": r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "score": 0.85},
            {"name": "india_phone", "regex": r"\b(?:\+91|0)?[789]\d{9}\b", "score": 0.85}
        ]
    )
    
    # Enhanced email recognizer
    email_recognizer = PatternRecognizer(
        supported_entity="EMAIL_ADDRESS",
        patterns=[
            {"name": "email", "regex": r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", "score": 0.85}
        ]
    )
    
    recognizers.extend([
        school_recognizer,
        aadhaar_recognizer, 
        pan_recognizer,
        person_recognizer,
        phone_recognizer,
        email_recognizer
    ])
    
    return recognizers

def initialize_analyzer():
    """Initialize the Presidio analyzer with custom configuration"""
    try:
        # Create NLP engine with spaCy model
        provider = NlpEngineProvider(nlp_configuration={"lang_code": "en", "model_name": "en_core_web_lg"})
        nlp_engine = provider.create_engine()
        
        # Create registry and load predefined recognizers
        registry = RecognizerRegistry()
        registry.load_predefined_recognizers(nlp_engine=nlp_engine)
        
        # Add custom recognizers
        for recognizer in create_custom_recognizers():
            registry.add_recognizer(recognizer)
        
        # Create analyzer with the registry
        analyzer = AnalyzerEngine(registry=registry, nlp_engine=nlp_engine)
        logger.info("Presidio Analyzer initialized successfully")
        return analyzer
    except Exception as e:
        logger.error(f"Error initializing Presidio Analyzer: {str(e)}")
        raise

def get_analyzer():
    """Get or create a cached analyzer instance"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = initialize_analyzer()
    return _analyzer_instance

def detect_pii_entities(text, threshold=0.3, selected_entities=None):
    """
    Detect PII entities in the given text using Presidio.
    
    Args:
        text (str): The text to analyze
        threshold (float): Confidence threshold for entity detection (0.0-1.0)
        selected_entities (list): Optional list of entity types to detect
        
    Returns:
        list: List of tuples (entity_text, entity_type, start_index, end_index)
    """
    if not text or not isinstance(text, str):
        return []
    
    try:
        # Get analyzer
        analyzer = get_analyzer()
        
        # Analyze text with Presidio
        results = analyzer.analyze(
            text=text, 
            language='en',
            entities=selected_entities,
            score_threshold=threshold
        )
        
        # Convert results to our format
        entities = []
        for result in results:
            entity_text = text[result.start:result.end]
            entities.append((
                entity_text,
                result.entity_type,
                result.start,
                result.end
            ))
        
        # If no entities found with Presidio, use fallback regex detection
        if not entities:
            entities = fallback_regex_detection(text, selected_entities)
        
        logger.info(f"Detected {len(entities)} PII entities with threshold {threshold}")
        for entity in entities:
            logger.info(f"Found {entity[1]}: '{entity[0]}'")
        
        return entities
    except Exception as e:
        logger.error(f"Error detecting PII entities: {str(e)}")
        # Use fallback regex detection if Presidio fails
        return fallback_regex_detection(text, selected_entities)

def fallback_regex_detection(text, selected_entities=None):
    """Fallback regex-based detection when Presidio fails"""
    import re
    entities = []
    
    patterns = {
        "PERSON": r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',
        "PHONE_NUMBER": r'\b(?:\+91|0)?[789]\d{9}\b|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
        "EMAIL_ADDRESS": r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
        "CREDIT_CARD": r'\b(?:\d{4}[-\s]?){4}\b',
        "SCHOOL": r'\b[A-Z][a-zA-Z\s]+ (?:School|College|University|Institute)\b',
        "AADHAAR": r'\b\d{4}\s\d{4}\s\d{4}\b|\b\d{12}\b',
        "PAN": r'\b[A-Z]{5}[0-9]{4}[A-Z]\b',
        "DATE_TIME": r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b'
    }
    
    # Filter patterns based on selected entities
    if selected_entities:
        patterns = {k: v for k, v in patterns.items() if k in selected_entities}
    
    for entity_type, pattern in patterns.items():
        for match in re.finditer(pattern, text):
            entities.append((match.group(), entity_type, match.start(), match.end()))
    
    return entities
