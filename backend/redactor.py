from faker import Faker
from backend.pii_detector import detect_pii_entities
import logging
import random

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Faker
fake = Faker()

def generate_fake_data(entity_type, original_length=None):
    """
    Generates fake data based on PII entity type, matching original length if provided.
    """
    try:
        if entity_type == "PERSON":
            text = fake.name()
        elif entity_type == "PHONE_NUMBER":
            text = fake.phone_number()[:15]
        elif entity_type == "EMAIL_ADDRESS":
            text = fake.email()
        elif entity_type == "CREDIT_CARD":
            text = fake.credit_card_number()
        elif entity_type == "ADDRESS":
            text = fake.address().replace("\n", ", ")[:50]
        elif entity_type == "ORGANIZATION":
            text = fake.company()
        elif entity_type == "LOCATION":
            text = fake.city()
        elif entity_type == "AADHAAR":
            text = f"{fake.random_int(1000, 9999)} {fake.random_int(1000, 9999)} {fake.random_int(1000, 9999)}"
        elif entity_type == "SSN":
            text = f"{fake.random_int(100, 999)}-{fake.random_int(10, 99)}-{fake.random_int(1000, 9999)}"
        elif entity_type == "CUSTOM_ID":
            text = f"{fake.random_int(100000, 99999999999)}"
        elif entity_type == "PAN":
            text = f"{''.join(fake.random_uppercase_letter() for _ in range(5))}{fake.random_int(1000, 9999)}{fake.random_uppercase_letter()}"
        else:
            text = "REDACTED"
        
        if original_length:
            text = text[:original_length].ljust(original_length, " ")
        logger.debug(f"Generated fake data for {entity_type}: '{text}'")
        return text
    except Exception as e:
        logger.error(f"Failed to generate fake data for {entity_type}: %s", e)
        return "REDACTED"

def redact_pii(text):
    """
    Redacts PII by replacing with fake data.
    
    Returns: (redacted_text, pii_entity_types)
    """
    try:
        entities = detect_pii_entities(text)
        if not entities:
            logger.debug("No PII entities detected.")
            return text, []

        # Resolve overlapping entities
        non_overlapping = []
        entities.sort(key=lambda x: (x[2], -x[3]))
        last_end = -1
        for entity in entities:
            if entity[2] >= last_end:
                non_overlapping.append(entity)
                last_end = entity[3]
        
        redacted_text = text
        pii_types = set()
        for entity_text, label, start, end in reversed(non_overlapping):
            fake_text = generate_fake_data(label, original_length=len(entity_text))
            redacted_text = redacted_text[:start] + fake_text + redacted_text[end:]
            pii_types.add(label)
            logger.debug(f"Redacted '{entity_text}' ({label}) with '{fake_text}'")

        return redacted_text, list(pii_types)
    except Exception as e:
        logger.error(f"Redaction failed: %s", e)
        raise RuntimeError(f"[Error] Redaction failed: %s", e)