import os
import tempfile
import streamlit as st
from streamlit_pdf_viewer import pdf_viewer

from backend.pii_detector import SUPPORTED_ENTITIES, detect_pii_entities
from backend.pdf_loader import extract_pdf_text, get_pdf_metadata, is_scanned_pdf
from backend.redactor import redact_pii, highlight_pii
from backend.pdf_writer import redact_pdf

st.set_page_config(page_title="PDF PII Redactor", layout="wide")

# Session state
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'detected_entities_dict' not in st.session_state:
    st.session_state.detected_entities_dict = {}
if 'pdf_path' not in st.session_state:
    st.session_state.pdf_path = None
if 'extracted_text' not in st.session_state:
    st.session_state.extracted_text = ""
if 'redaction_type' not in st.session_state:
    st.session_state.redaction_type = "black_bar"
if 'custom_mask_text' not in st.session_state:
    st.session_state.custom_mask_text = "[REDACTED]"
if 'detection_threshold' not in st.session_state:
    st.session_state.detection_threshold = 0.2
if 'selected_pii_types_to_redact' not in st.session_state:
    st.session_state.selected_pii_types_to_redact = []

with st.sidebar:
    st.header("Settings")
    st.session_state.detection_threshold = st.slider(
        "Detection sensitivity:",
        0.1, 0.9, st.session_state.detection_threshold,
        help="Lower values detect more potential PII but may increase false positives",
        key="detection_threshold_slider_key"
    )
    if st.session_state.step == 2:
        redaction_options = [
            {"id": "black_bar", "name": "Black Bar", "icon": "⬛"},
            {"id": "white_bar", "name": "White Bar", "icon": "⬜"},
            {"id": "random", "name": "Random Values", "icon": "🔄"},
            {"id": "masked", "name": "Masked", "icon": "***"},
            {"id": "numbered", "name": "Numbered", "icon": "🔢"},
            {"id": "custom", "name": "Custom Text", "icon": "✏️"},
            {"id": "partial", "name": "Partial (Show Last 4 Digits)", "icon": "🔒"}
        ]
        redaction_type = st.radio(
            "Redaction method:",
            options=[opt["id"] for opt in redaction_options],
            format_func=lambda x: next((opt["name"] for opt in redaction_options if opt["id"] == x), x),
            key="redaction_type_radio_key"
        )
        st.session_state.redaction_type = redaction_type
        if redaction_type == "custom":
            st.session_state.custom_mask_text = st.text_input(
                "Custom replacement text:",
                value=st.session_state.custom_mask_text,
                key="custom_mask_text_input_key"
            )

st.title("PDF PII Redactor")
st.markdown("Redact PAN, Aadhaar, Credit Card, and more from digital and scanned PDFs.")

if st.session_state.step == 1:
    st.header("Step 1: Upload and Detect PII")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.read())
            st.session_state.pdf_path = tmp_file.name
        metadata = get_pdf_metadata(st.session_state.pdf_path)
        st.write(metadata)
        st.session_state.extracted_text = extract_pdf_text(st.session_state.pdf_path)
        st.text_area("Extracted Text", st.session_state.extracted_text[:2000], height=300)
        if st.button("Detect PII Entities"):
            entities = detect_pii_entities(
                st.session_state.extracted_text,
                threshold=st.session_state.detection_threshold
            )
            entity_dict = {}
            for text, etype, start, end in entities:
                if etype not in entity_dict:
                    entity_dict[etype] = []
                entity_dict[etype].append((text, start, end))
            st.session_state.detected_entities_dict = entity_dict
            st.session_state.step = 2
            st.rerun()

elif st.session_state.step == 2:
    st.header("Step 2: Select PII to Redact & Preview")
    selected_types = {}
    for etype, items in st.session_state.detected_entities_dict.items():
        selected = st.checkbox(etype, value=True, key=f"chk_{etype}")
        selected_types[etype] = selected
    selected_entities = [etype for etype, sel in selected_types.items() if sel]
    st.session_state.selected_pii_types_to_redact = selected_entities
    entities_to_redact_for_preview = []
    for etype in selected_entities:
        for entity_text, start, end in st.session_state.detected_entities_dict.get(etype, []):
            if start < 500:
                entities_to_redact_for_preview.append((entity_text, etype, start, end))
    sample_text = st.session_state.extracted_text[:500]
    st.markdown(highlight_pii(sample_text, entities_to_redact_for_preview), unsafe_allow_html=True)
    redacted_sample, _ = redact_pii(
        sample_text,
        redaction_type=st.session_state.redaction_type,
        selected_entities=selected_entities,
        threshold=st.session_state.detection_threshold,
        custom_mask_text=st.session_state.custom_mask_text
    )
    st.text_area("Redacted Preview", redacted_sample, height=200)
    if st.button("Redact PDF and Show Preview"):
        output_filename = f"redacted_{os.path.basename(st.session_state.pdf_path)}"
        output_path = os.path.join(tempfile.gettempdir(), output_filename)
        full_entities_to_redact = []
        for etype in selected_entities:
            for text, start, end in st.session_state.detected_entities_dict[etype]:
                full_entities_to_redact.append((text, etype, start, end))
        scanned = is_scanned_pdf(st.session_state.pdf_path)
        success = redact_pdf(
            st.session_state.pdf_path,
            output_path,
            redaction_type=st.session_state.redaction_type,
            entities_to_redact=full_entities_to_redact,
            custom_mask_text=st.session_state.custom_mask_text,
            threshold=st.session_state.detection_threshold,
            scanned=scanned
        )
        if success:
            with open(output_path, "rb") as f:
                pdf_bytes = f.read()
            st.success("PDF successfully redacted!")
            pdf_viewer(pdf_bytes, width=900, height=800)
            st.download_button(
                label="Download Redacted PDF",
                data=pdf_bytes,
                file_name=output_filename,
                mime="application/pdf"
            )
        else:
            st.error("Failed to redact PDF. Please try again.")
    if st.button("Back to Upload/Detection"):
        st.session_state.step = 1
        st.session_state.detected_entities_dict = {}
        st.session_state.selected_pii_types_to_redact = []
        st.rerun()
