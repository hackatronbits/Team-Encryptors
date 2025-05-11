from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern, RecognizerRegistry, EntityRecognizer, RecognizerResult
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer, PhoneRecognizer, EmailRecognizer, IbanRecognizer,
    IpRecognizer, MedicalLicenseRecognizer, UrlRecognizer, UsSsnRecognizer,
    UsBankRecognizer, UsLicenseRecognizer, UsItinRecognizer, UsPassportRecognizer,
    NhsRecognizer, UkNinoRecognizer, SgFinRecognizer, AuAbnRecognizer,
    AuAcnRecognizer, AuTfnRecognizer, AuMedicareRecognizer, InPanRecognizer,
    InAadhaarRecognizer, InVehicleRegistrationRecognizer, InPassportRecognizer,
    InVoterRecognizer, CryptoRecognizer, DateRecognizer, SpacyRecognizer
)
import re
import json
import logging
import os
import spacy
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress Presidio and Faker debug logs
logging.getLogger("presidio-analyzer").setLevel(logging.INFO)
logging.getLogger("faker.factory").setLevel(logging.INFO)

# Config path
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
if not os.path.exists(CONFIG_PATH):
    logger.error(f"Config file '{CONFIG_PATH}' not found.")
    raise FileNotFoundError(f"Config file '{CONFIG_PATH}' not found.")

# PII detection cache
pii_cache = {}

# Initialize Presidio
try:
    logger.info("Initializing Presidio Analyzer...")
    registry = RecognizerRegistry()
    
    # Manually add English-compatible predefined recognizers
    supported_languages = ["en"]
    english_recognizers = [
        CreditCardRecognizer(supported_language="en"),
        PhoneRecognizer(supported_language="en"),
        EmailRecognizer(supported_language="en"),
        IbanRecognizer(supported_language="en"),
        IpRecognizer(supported_language="en"),
        MedicalLicenseRecognizer(supported_language="en"),
        UrlRecognizer(supported_language="en"),
        UsSsnRecognizer(supported_language="en"),
        UsBankRecognizer(supported_language="en"),
        UsLicenseRecognizer(supported_language="en"),
        UsItinRecognizer(supported_language="en"),
        UsPassportRecognizer(supported_language="en"),
        NhsRecognizer(supported_language="en"),
        UkNinoRecognizer(supported_language="en"),
        SgFinRecognizer(supported_language="en"),
        AuAbnRecognizer(supported_language="en"),
        AuAcnRecognizer(supported_language="en"),
        AuTfnRecognizer(supported_language="en"),
        AuMedicareRecognizer(supported_language="en"),
        InPanRecognizer(supported_language="en"),
        InAadhaarRecognizer(supported_language="en"),
        InVehicleRegistrationRecognizer(supported_language="en"),
        InPassportRecognizer(supported_language="en"),
        InVoterRecognizer(supported_language="en"),
        CryptoRecognizer(supported_language="en"),
        DateRecognizer(supported_language="en"),
        SpacyRecognizer(supported_language="en")
    ]
    for recognizer in english_recognizers:
        try:
            registry.add_recognizer(recognizer)
        except Exception as e:
            logger.warning(f"Failed to add recognizer {recognizer.name}: {e}")

    # Custom recognizers
    aadhaar_pattern = Pattern(name="AADHAAR_PATTERN", regex=r'\b\d{4}\s*\-?\s*\d{4}\s*\-?\s*\d{4}\b', score=0.85)
    ssn_pattern = Pattern(name="SSN_PATTERN", regex=r'\b\d{3}\s*\-?\s*\d{2}\s*\-?\s*\d{4}\b', score=0.85)
    custom_id_pattern = Pattern(name="CUSTOM_ID_PATTERN", regex=r'\b[A-Z0-9]{0,2}\d{6,11}\b', score=0.85)
    pan_pattern = Pattern(name="PAN_PATTERN", regex=r'\b[A-Z]{5}\d{4}[A-Z]\b', score=0.85)
    credit_card_pattern = Pattern(name="CREDIT_CARD_PATTERN", regex=r'\b(?:\d{4}\s*\-?\s*){3}\d{4}\b', score=0.7)
    
    aadhaar_recognizer = PatternRecognizer(supported_entity="AADHAAR", patterns=[aadhaar_pattern], supported_language="en")
    ssn_recognizer = PatternRecognizer(supported_entity="SSN", patterns=[ssn_pattern], supported_language="en")
    custom_id_recognizer = PatternRecognizer(supported_entity="CUSTOM_ID", patterns=[custom_id_pattern], supported_language="en")
    pan_recognizer = PatternRecognizer(supported_entity="PAN", patterns=[pan_pattern], supported_language="en")
    credit_card_recognizer = PatternRecognizer(supported_entity="CREDIT_CARD", patterns=[credit_card_pattern], supported_language="en")
    
    registry.add_recognizer(aadhaar_recognizer)
    registry.add_recognizer(ssn_recognizer)
    registry.add_recognizer(custom_id_recognizer)
    registry.add_recognizer(pan_recognizer)
    registry.add_recognizer(credit_card_recognizer)
    
    class CustomSpacyRecognizer(EntityRecognizer):
        def __init__(self):
            super().__init__(
                supported_entities=["ADDRESS", "ORGANIZATION", "LOCATION", "PERSON"],
                supported_language="en",
                name="CustomSpacyRecognizer"
            )
            try:
                self.nlp = spacy.load("en_core_web_lg")
            except:
                logger.warning("en_core_web_lg not found, using en_core_web_sm")
                self.nlp = spacy.load("en_core_web_sm")
        
        def analyze(self, text, entities, nlp_artifacts=None):
            try:
                doc = self.nlp(text)
                results = []
                for ent in doc.ents:
                    if ent.label_ in entities:
                        results.append(RecognizerResult(
                            entity_type=ent.label_,
                            start=ent.start_char,
                            end=ent.end_char,
                            score=0.75
                        ))
                return results
            except Exception as e:
                logger.error(f"CustomSpacyRecognizer failed: {e}")
                return []
    
    registry.add_recognizer(CustomSpacyRecognizer())
    analyzer = AnalyzerEngine(registry=registry, supported_languages=supported_languages)
    logger.info("Presidio Analyzer initialized with support for languages: %s", supported_languages)
except Exception as e:
    logger.error(f"Failed to initialize Presidio: %s", e)
    raise RuntimeError(f"[Error] Failed to initialize Presidio: %s", e)

# Load PII entities
try:
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    PII_ENTITIES = config["pii_entities"]
    valid_entities = [
        "PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD",
        "ADDRESS", "ORGANIZATION", "LOCATION", "AADHAAR", "SSN", "CUSTOM_ID", "PAN"
    ]
    for entity in PII_ENTITIES:
        if entity not in valid_entities:
            logger.warning(f"Unknown PII entity in config: %s", entity)
except Exception as e:
    logger.warning(f"Failed to load config: %s", e)
    PII_ENTITIES = valid_entities

def detect_pii_entities(text):
    """
    Detects PII using Presidio and regex, with caching.
    """
    if not isinstance(text, str):
        raise ValueError("[Error] Input text must be a string.")
    if not text.strip():
        return []

    # Check cache
    cache_key = text
    if cache_key in pii_cache:
        logger.debug(f"Cache hit for text: '{text[:100]}...'")
        return pii_cache[cache_key]

    entities = []
    start_time = time.time()
    try:
        logger.debug(f"Running Presidio PII detection on: '{text[:100]}...'")
        results = analyzer.analyze(text=text, entities=[e for e in PII_ENTITIES if e in valid_entities], language="en")
        for result in results:
            if result.score >= 0.6:
                entity_text = text[result.start:result.end]
                entities.append((entity_text, result.entity_type, result.start, result.end))
        logger.debug(f"Presidio detection took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Presidio analysis failed: %s", e)

    patterns = {
        "AADHAAR": r'\b\d{4}\s*\-?\s*\d{4}\s*\-?\s*\d{4}\b',
        "SSN": r'\b\d{3}\s*\-?\s*\d{2}\s*\-?\s*\d{4}\b',
        "CUSTOM_ID": r'\b[A-Z0-9]{0,2}\d{6,11}\b',
        "PAN": r'\b[A-Z]{5}\d{4}[A-Z]\b',
        "CREDIT_CARD": r'\b(?:\d{4}\s*\-?\s*){3}\d{4}\b'
    }
    for label, pattern in patterns.items():
        for match in re.finditer(pattern, text):
            entities.append((match.group(), label, match.start(), match.end()))

    unique_entities = list({(text, label, start, end): (text, label, start, end) 
                           for text, label, start, end in entities}.values())
    unique_entities.sort(key=lambda x: x[2])
    logger.debug(f"Final entities: {unique_entities}")
    
    # Cache result
    pii_cache[cache_key] = unique_entities
    if len(pii_cache) > 1000:
        pii_cache.pop(next(iter(pii_cache)))
    
    return unique_entities
