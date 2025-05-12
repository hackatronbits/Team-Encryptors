from faker import Faker
import logging
import random
import os  # Added to fix NameError
from backend.pii_detector import detect_pii_entities

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Faker with configurable locale
FAKER_LOCALE = os.environ.get("FAKER_LOCALE", "en_US")
fake = Faker(FAKER_LOCALE)

def generate_fake_data(entity_type, original_text=None):
    """
    Generates fake data based on PII entity type.
    
    Args:
        entity_type (str): Type of PII entity
        original_text (str): Original text to match format
        
    Returns:
        str: Generated fake data
    """
    try:
        if entity_type == "PERSON":
            return fake.name()
        elif entity_type == "PHONE_NUMBER":
            if original_text and ('+91' in original_text or len(original_text.replace(" ", "")) == 10):
                return "+91" + str(fake.random_int(7000000000, 9999999999))
            else:
                return fake.phone_number()
        elif entity_type == "EMAIL_ADDRESS":
            return fake.email()
        elif entity_type == "CREDIT_CARD":
            return fake.credit_card_number()
        elif entity_type == "DATE_TIME":
            return fake.date()
        elif entity_type == "SCHOOL":
            schools = ["Springfield High School", "Westfield University", "Eastwood College", 
                      "Northern Technical Institute", "Southside Academy"]
            return random.choice(schools)
        elif entity_type == "AADHAAR":
            return f"{fake.random_int(1000, 9999)} {fake.random_int(1000, 9999)} {fake.random_int(1000, 9999)}"
        elif entity_type == "PAN":
            return f"{''.join(fake.random_uppercase_letter() for _ in range(5))}{fake.random_int(1000, 9999)}{fake.random_uppercase_letter()}"
        else:
            return "REDACTED"
    except Exception as e:
        logger.error(f"Failed to generate fake data for {entity_type}: {e}")
        return "REDACTED"

def mask_text(text, mask_char="*"):
    """Generate masked text"""
    return mask_char * len(text)

def redact_pii(text, redaction_type="random", selected_entities=None, threshold=0.3, custom_mask_text=None):
    """
    Redacts PII by replacing with the specified redaction type.
    
    Args:
        text (str): Text to redact
        redaction_type (str): Type of redaction (black_bar, white_bar, random, masked, custom)
        selected_entities (list): List of entity types to redact
        threshold (float): Confidence threshold for PII detection
        custom_mask_text (str): Custom text to use for masking
        
    Returns:
        tuple: (redacted_text, list_of_detected_pii_types)
    """
    if not text or not isinstance(text, str):
        logger.warning("No valid text provided for redaction")
        return text, []
    
    try:
        # Detect entities using Presidio
        entities = detect_pii_entities(text, threshold=threshold, selected_entities=selected_entities)
        if not entities:
            logger.info("No PII entities detected.")
            return text, []

        # Log detected entities
        for entity_text, entity_type, start, end in entities:
            logger.info(f"Redacting: {entity_type} - '{entity_text}' at positions {start}-{end}")

        # Get unique entity types for return value
        pii_types = list(set(entity[1] for entity in entities))
        
        # Sort entities by position (from end to start to maintain indices)
        entities.sort(key=lambda x: x[2], reverse=True)
        
        # Apply redaction based on type
        redacted_text = text
        
        for entity_text, entity_type, start, end in entities:
            if redaction_type == "random":
                replacement = generate_fake_data(entity_type, entity_text)
                # Ensure replacement matches original length
                if len(replacement) > (end - start):
                    replacement = replacement[:end-start]
                elif len(replacement) < (end - start):
                    replacement = replacement.ljust(end-start)
            elif redaction_type == "masked":
                replacement = mask_text(entity_text)
            elif redaction_type == "custom" and custom_mask_text:
                # Repeat custom text to match length if needed
                if len(custom_mask_text) < (end - start):
                    repetitions = (end - start) // len(custom_mask_text) + 1
                    replacement = (custom_mask_text * repetitions)[:end-start]
                else:
                    replacement = custom_mask_text[:end-start]
            elif redaction_type == "black_bar":
                replacement = "█" * (end - start)
            elif redaction_type == "white_bar":
                replacement = " " * (end - start)
            else:
                replacement = "REDACTED"
                if len(replacement) < (end - start):
                    replacement = replacement.ljust(end - start)
                elif len(replacement) > (end - start):
                    replacement = replacement[:end - start]
                
            # Apply replacement
            redacted_text = redacted_text[:start] + replacement + redacted_text[end:]
            logger.info(f"Replaced '{entity_text}' with '{replacement}'")
        
        return redacted_text, pii_types
    except Exception as e:
        logger.error(f"Redaction failed: {e}")
        raise RuntimeError(f"Redaction failed: {e}")