import streamlit as st
import os
import tempfile
import time
from PIL import Image
import io
import logging

from backend.pii_detector import CUSTOM_PII_ENTITY_TEMPLATE
from backend.pdf_loader import extract_pdf_text, get_pdf_metadata
from backend.redactor import redact_pii
from backend.pdf_writer import redact_pdf

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page configuration
st.set_page_config(
    page_title="Educational PDF PII Redactor",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS (fixed invalid color)
st.markdown("""
<style>
    .main .block-container {padding-top: 1.5rem;}
    h1 {margin-bottom: 1rem; color: #1E3A8A; font-size: 2.2rem;}
    h2 {color: #1E3A8A; font-size: 1.5rem;}
    .stRadio > div {flex-direction: row;}
    .stRadio > div > label {margin-right: 1.5rem; font-size: 0.9rem;}
    .pii-options {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 5px;
        font-size: 0.85rem;
    }
    .stCheckbox label p {font-size: 0.85rem !important;}
    .stButton button {background-color: #1E3A8A; color: white;}
    .stButton button:hover {background-color: #2563EB;}
    .footer {font-size: 0.8rem; color: #6B7280; text-align: center; margin-top: 2rem;}
    .info-box {
        background-color: #F3F4F6;
        padding: 1rem;
        border-radius: 5px;
        margin-bottom: 1rem;
    }
    .stTabs [data-baseweb="tab-list"] {gap: 2px;}
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        white-space: pre-wrap;
        background-color: #F3F4F6;
        border-radius: 4px 4px 0 0;
        gap: 1px;
        padding-top: 8px;
        padding-bottom: 8px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1E3A8A;
        color: white;
    }
    .redaction-methods {
        display: flex;
        flex-direction: column;
        gap: 5px;
    }
    .redaction-method {
        display: flex;
        align-items: center;
        padding: 8px;
        border: 1px solid #E5E7EB;
        border-radius: 4px;
        cursor: pointer;
    }
    .redaction-method.selected {
        border-color: #1E3A8A;
        background-color: #EFF6FF;
    }
    .redaction-method-icon {
        margin-right: 10px;
        font-size: 1.2rem;
    }
    .redaction-method-text {
        flex: 1;
    }
    .redaction-method-desc {
        font-size: 0.8rem;
        color: #6B7280;
    }
</style>
""", unsafe_allow_html=True)

# Title and description
st.title("Educational Document PII Redactor")
st.markdown("Securely redact personally identifiable information from educational documents and records.")

# Sidebar for configuration
with st.sidebar:
    st.header("Redaction Settings")
    
    st.subheader("Select PII Types to Redact")
    select_all = st.checkbox("Select All PII Types", value=True, key="select_all")
    
    st.markdown('<div class="pii-options">', unsafe_allow_html=True)
    
    selected_entities = []
    for entity_info in CUSTOM_PII_ENTITY_TEMPLATE:
        if st.checkbox(
            f"{entity_info['label']} - {entity_info['description']}",
            value=select_all,
            key=f"entity_{entity_info['label']}"
        ):
            selected_entities.append(entity_info['label'])
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    if not selected_entities:
        st.error("Please select at least one PII type to redact.")
    
    st.subheader("Redaction Method")
    redaction_options = [
        {"id": "black_bar", "name": "Black Bar", "icon": "⬛", "desc": "Cover with black rectangles"},
        {"id": "white_bar", "name": "White Bar", "icon": "⬜", "desc": "Cover with white space"},
        {"id": "random", "name": "Random Values", "icon": "🔄", "desc": "Replace with fake data"},
        {"id": "masked", "name": "Masked", "icon": "***", "desc": "Replace with asterisks"},
        {"id": "custom", "name": "Custom Text", "icon": "✏️", "desc": "Replace with your text"}
    ]
    
    redaction_type = st.radio(
        "Select how to redact PII:",
        options=[opt["id"] for opt in redaction_options],
        format_func=lambda x: next((opt["name"] for opt in redaction_options if opt["id"] == x), x),
        key="redaction_type_radio",
        horizontal=False
    )
    
    custom_mask_text = None
    if redaction_type == "custom":
        custom_mask_text = st.text_input(
            "Enter custom text to replace PII:",
            value="[REDACTED]",
            key="custom_mask_text"
        )
    
    with st.expander("Advanced Options"):
        detection_threshold = st.slider(
            "Detection Sensitivity:",
            min_value=0.1,
            max_value=0.9,
            value=0.3,
            step=0.1,
            help="Lower values detect more PII but may include false positives",
            key="threshold_slider"
        )
        
        optimize_size = st.checkbox("Optimize output file size", value=True, key="optimize_size_checkbox")

# Main content area
uploaded_file = st.file_uploader("Upload an educational document (PDF)", type="pdf", key="pdf_uploader")

if uploaded_file:
    # Validate file size (e.g., max 50MB)
    max_file_size_mb = 50
    if uploaded_file.size > max_file_size_mb * 1024 * 1024:
        st.error(f"File size exceeds {max_file_size_mb}MB limit.")
    else:
        pdf_path = None
        output_pdf = None
        try:
            logger.info(f"Uploading file: {uploaded_file.name}")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(uploaded_file.read())
                pdf_path = temp_file.name
            
            metadata = get_pdf_metadata(pdf_path)
            
            st.markdown('<div class="info-box">', unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                st.write(f"**Document Name:**  \n{uploaded_file.name}")
            with col2:
                st.write(f"**Pages:**  \n{metadata.get('page_count', 'Unknown')}")
            with col3:
                st.write(f"**Size:**  \n{metadata.get('file_size', 0) / 1024:.1f} KB")
            st.markdown('</div>', unsafe_allow_html=True)
            
            tab1, tab2 = st.tabs(["📝 Preview", "🔒 Redact & Download"])
            
            with tab1:
                st.subheader("Document Preview")
                
                if not selected_entities:
                    st.error("Please select at least one PII type in the sidebar.")
                else:
                    with st.spinner("Extracting text from document..."):
                        status_code, text, ocr_text_pages = extract_pdf_text(pdf_path)
                    
                    if status_code == 0:
                        st.error(
                            "Failed to extract text from the document. "
                            "If this is a scanned PDF, ensure Poppler is installed and POPPLER_PATH is set. "
                            "See https://github.com/oschwartz10612/poppler-windows for installation."
                        )
                    else:
                        if ocr_text_pages:
                            st.warning("This appears to be a scanned PDF. Text was extracted using OCR.")
                        
                        st.write("**Original Text Sample:**")
                        st.text_area("", value=text[:1000] + ("..." if len(text) > 1000 else ""), height=150, key="original_text_area")
                        
                        if st.button("Generate Redacted Preview", key="preview_button"):
                            with st.spinner("Detecting and redacting PII..."):
                                redacted_text, detected_pii_types = redact_pii(
                                    text,
                                    redaction_type=redaction_type,
                                    selected_entities=selected_entities,
                                    threshold=detection_threshold,
                                    custom_mask_text=custom_mask_text
                                )
                            
                            st.write("**Redacted Text Sample:**")
                            st.text_area("", value=redacted_text[:1000] + ("..." if len(redacted_text) > 1000 else ""), height=150, key="redacted_text_area")
                            
                            if detected_pii_types:
                                st.success(f"Detected PII types: {', '.join(detected_pii_types)}")
                                
                                pii_counts = {}
                                for pii_type in detected_pii_types:
                                    pii_counts[pii_type] = pii_counts.get(pii_type, 0) + 1
                                
                                st.write("**PII Detection Summary:**")
                                for pii_type, count in pii_counts.items():
                                    st.write(f"- {pii_type}: {count} instance(s)")
                            else:
                                st.info("No PII detected in the document.")
            
            with tab2:
                st.subheader("Redact Document")
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write("Click the button below to redact the PDF and download the result.")
                    
                    if st.button("Redact PDF", type="primary", key="redact_button"):
                        if not selected_entities:
                            st.error("Please select at least one PII type in the sidebar.")
                        else:
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            status_text.text("Starting redaction process...")
                            progress_bar.progress(10)
                            
                            output_pdf = pdf_path.replace(".pdf", "_redacted.pdf")
                            
                            status_text.text("Detecting PII entities...")
                            progress_bar.progress(30)
                            
                            success = redact_pdf(
                                pdf_path,
                                output_pdf,
                                redaction_type=redaction_type,
                                selected_entities=selected_entities,
                                threshold=detection_threshold,
                                custom_mask_text=custom_mask_text,
                                ocr_text_pages=ocr_text_pages
                            )
                            
                            progress_bar.progress(80)
                            status_text.text("Finalizing redacted document...")
                            
                            if success:
                                with open(output_pdf, "rb") as f:
                                    redacted_pdf_data = f.read()
                                
                                progress_bar.progress(100)
                                status_text.text("Redaction complete!")
                                
                                st.success("PDF redacted successfully!")
                                st.download_button(
                                    label="Download Redacted PDF",
                                    data=redacted_pdf_data,
                                    file_name=f"redacted_{uploaded_file.name}",
                                    mime="application/pdf",
                                    key="download_button"
                                )
                                
                                original_size = os.path.getsize(pdf_path)
                                redacted_size = os.path.getsize(output_pdf)
                                
                                st.info(f"Original file size: {original_size/1024:.1f} KB\nRedacted file size: {redacted_size/1024:.1f} KB")
                            else:
                                progress_bar.progress(100)
                                status_text.text("Redaction failed or no PII found.")
                                st.warning(
                                    "No PII was detected or redaction process failed. "
                                    "Try adjusting the detection sensitivity or selecting different PII types."
                                )
                
                with col2:
                    st.write("**Redaction Type:**")
                    redaction_examples = {
                        "black_bar": "John Doe → █████████",
                        "white_bar": "John Doe → [blank space]",
                        "random": "John Doe → Jane Smith",
                        "masked": "John Doe → *********",
                        "custom": f"John Doe → {custom_mask_text if custom_mask_text else '[REDACTED]'}"
                    }
                    st.code(redaction_examples[redaction_type])
                    
                    st.write("**Selected PII Types:**")
                    if selected_entities:
                        st.code("\n".join(selected_entities))
                    else:
                        st.warning("No PII types selected")
        
        finally:
            # Ensure temporary files are cleaned up
            if pdf_path and os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                    logger.info(f"Cleaned up temporary file: {pdf_path}")
                except Exception as e:
                    logger.error(f"Failed to clean up {pdf_path}: {e}")
            if output_pdf and os.path.exists(output_pdf):
                try:
                    os.remove(output_pdf)
                    logger.info(f"Cleaned up temporary file: {output_pdf}")
                except Exception as e:
                    logger.error(f"Failed to clean up {output_pdf}: {e}")

# Footer
st.markdown('<div class="footer">', unsafe_allow_html=True)
st.markdown("Educational PDF PII Redactor - Securely redact sensitive information from educational documents")
st.markdown("</div>", unsafe_allow_html=True)