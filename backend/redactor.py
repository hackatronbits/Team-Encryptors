from faker import Faker
import logging
import random
from typing import List, Tuple, Optional
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import RecognizerResult, OperatorConfig
from backend.pii_detector import detect_pii_entities

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
fake = Faker()
anonymizer = AnonymizerEngine()

def generate_fake_data(entity_type, original_text=None):
    if entity_type == "PERSON":
        return fake.name()
    elif entity_type == "PHONE_NUMBER":
        return fake.phone_number()
    elif entity_type == "EMAIL_ADDRESS":
        return fake.email()
    elif entity_type == "CREDIT_CARD":
        return fake.credit_card_number()
    elif entity_type == "DATE_TIME":
        return fake.date()
    elif entity_type == "LOCATION":
        return fake.city()
    elif entity_type == "ORGANIZATION":
        return fake.company()
    elif entity_type == "PAN":
        return "ABCDE1234F"
    elif entity_type == "AADHAAR":
        return "1234 5678 9012"
    else:
        return "REDACTED"

def partial_redact(value, entity_type=None):
    import re
    # Remove non-digits for Aadhaar/Credit Card, spaces for PAN
    stripped = re.sub(r'\D', '', value) if entity_type in ["AADHAAR", "CREDIT_CARD"] else re.sub(r'\s+', '', value)
    if entity_type == "AADHAAR" and len(stripped) == 12:
        # Aadhaar: mask first 8, keep last 4, format as **** **** 1234
        masked = '**** **** ' + stripped[-4:]
        return masked
    elif entity_type == "CREDIT_CARD" and len(stripped) == 16:
        # Credit card: mask first 12, keep last 4, format as **** **** **** 1234
        masked = '**** **** **** ' + stripped[-4:]
        return masked
    elif entity_type == "PAN":
        # PAN: mask all but last 4
        if len(stripped) <= 4:
            return stripped
        return '*' * (len(stripped)-4) + stripped[-4:]
    else:
        # Default: mask all but last 4
        if len(stripped) <= 4:
            return stripped
        return '*' * (len(stripped)-4) + stripped[-4:]

def highlight_pii(text: str, entities: List[Tuple[str, str, int, int]]) -> str:
    if not entities:
        return f"<p>{text}</p>"
    entities = sorted(entities, key=lambda x: x[2], reverse=True)
    entity_colors = {}
    highlighted_text = text
    for entity_text, entity_type, start, end in entities:
        if entity_type not in entity_colors:
            hue = random.randint(0, 360)
            entity_colors[entity_type] = f"hsl({hue}, 80%, 80%)"
        color = entity_colors[entity_type]
        highlight = f'<span style="background-color: {color}; padding: 0 2px; border-radius: 3px;" title="{entity_type}">{entity_text}</span>'
        highlighted_text = highlighted_text[:start] + highlight + highlighted_text[end:]
    legend = "<div style='margin-top: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 5px;'><strong>Entity Types:</strong><br>"
    for entity_type, color in entity_colors.items():
        legend += f"<span style='display: inline-block; margin-right: 15px;'><span style='background-color: {color}; padding: 0 5px; border-radius: 3px;'>{entity_type}</span></span>"
    legend += "</div>"
    return f"<p>{highlighted_text}</p>{legend}"

def redact_pii(
    text: str,
    redaction_type: str = "random",
    selected_entities: Optional[List[str]] = None,
    threshold: float = 0.2,
    custom_mask_text: Optional[str] = None
):
    entities = detect_pii_entities(text, threshold=threshold, selected_entities=selected_entities)
    if not entities:
        logger.info("No PII entities detected.")
        return text, []
    pii_types = list(set(entity[1] for entity in entities))
    anonymizer = AnonymizerEngine()
    presidio_results = [
        RecognizerResult(entity_type=entity_type, start=start, end=end, score=1.0)
        for _, entity_type, start, end in entities
    ]
    operators = {}
    if redaction_type == "partial":
        # Manual redaction for PAN, AADHAAR, CREDIT_CARD
        entities = sorted(entities, key=lambda x: x[2], reverse=True)
        redacted_text = text
        for entity_text, entity_type, start, end in entities:
            if entity_type in ["PAN", "AADHAAR", "CREDIT_CARD"]:
                replacement = partial_redact(entity_text, entity_type)
            else:
                replacement = "*" * (end-start)
            redacted_text = redacted_text[:start] + replacement + redacted_text[end:]
        return redacted_text, pii_types
    if redaction_type == "random":
        for entity_type in pii_types:
            operators[entity_type] = OperatorConfig("replace", {"new_value": generate_fake_data(entity_type)})
    elif redaction_type == "masked":
        for entity_type in pii_types:
            operators[entity_type] = OperatorConfig("mask", {"masking_char": "*", "chars_to_mask": -1})
    elif redaction_type == "custom" and custom_mask_text:
        for entity_type in pii_types:
            operators[entity_type] = OperatorConfig("replace", {"new_value": custom_mask_text})
    elif redaction_type == "black_bar" or redaction_type == "white_bar":
        for entity_type in pii_types:
            operators[entity_type] = OperatorConfig("redact")
    elif redaction_type == "numbered":
        entity_counters = {}
        for _, entity_type, _, _ in entities:
            if entity_type not in entity_counters:
                entity_counters[entity_type] = 0
            entity_counters[entity_type] += 1
        redacted_text = text
        entities.sort(key=lambda x: x[2], reverse=True)
        for entity_text, entity_type, start, end in entities:
            entity_counters[entity_type] -= 1
            count_number = entity_counters[entity_type] + 1
            replacement = f"{entity_type} {count_number}".ljust(end - start)
            redacted_text = redacted_text[:start] + replacement + redacted_text[end:]
        return redacted_text, pii_types
    else:
        for entity_type in pii_types:
            operators[entity_type] = OperatorConfig("replace", {"new_value": "REDACTED"})
    anonymized_result = anonymizer.anonymize(
        text=text,
        analyzer_results=presidio_results,
        operators=operators
    )
    return anonymized_result.text, pii_types
