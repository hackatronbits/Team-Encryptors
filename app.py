import streamlit as st
import os
import shutil
import re
from datetime import datetime
from PyPDF2 import PdfReader
import traceback
from tqdm import tqdm

try:
    from backend.pdf_loader import extract_text_from_pdf
    from backend.redactor import redact_pii
    from backend.pdf_writer import redact_pdf
except ImportError as e:
    st.error(f"❌ Failed to import backend modules: {e}")
    st.error(f"Traceback: {traceback.format_exc()}")
    st.stop()

# Set page configuration as the first Streamlit command
st.set_page_config(page_title="Secure PDF Redactor", layout="wide")

# Custom CSS for background color, font color, and alignment
st.markdown("""
    <style>
    /* Ensure entire app background is dusky gray */
    .stApp {
        background-color: #6E7271 !important; /* Dusky gray background */
    }
    /* Main container background */
    .main, .stApp > div {
        background-color: #6E7271 !important; /* Dusky gray background */
        padding: 20px;
        border-radius: 10px;
    }
    /* Individual container background */
    .stApp > div > div {
        background-color: #6E7271 !important; /* Dusky gray background for containers */
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    /* File uploader (drag and drop container) background */
    .stFileUploader {
        background-color: #D8D4D5 !important; /* Lighter gray for drag and drop container */
        border: 2px dashed #E8ECEB !important;
        border-radius: 5px;
    }
    /* Font colors and alignment */
    h1, h2, h3 {
        color: #D8D4D5; /* Light gray for headings to contrast with dusky gray */
        text-align: center;
    }
    p, div, span, label {
        color: #E8ECEB; /* Light grayish-white for text to ensure readability */
        text-align: left;
    }
    /* Remove bullet points from markdown list and center-align */
    .stMarkdown ul {
        list-style-type: none;
        padding-left: 0;
        text-align: center;
    }
    .stMarkdown li {
        list-style-type: none;
        text-align: center;
    }
    /* Center-align specific elements */
    .stButton > button, .stFileUploader {
        display: block;
        margin-left: auto;
        margin-right: auto;
        background-color: #1A3C5A; /* Navy blue for buttons */
        color: #E8ECEB; /* Light grayish-white text on buttons */
        border-radius: 5px;
        font-size: 16px;
        padding: 10px 20px;
    }
    .stButton > button:hover {
        background-color: #0F2A44; /* Darker navy blue on hover */
    }
    /* Status messages with professional colors */
    .stSuccess {
        background-color: #A9CBA4; /* Soft green */
        color: #333333; /* Darker text for readability */
        padding: 10px;
        border-radius: 5px;
        text-align: center;
    }
    .stError {
        background-color: #E57373; /* Soft red */
        color: #333333; /* Darker text for readability */
        padding: 10px;
        border-radius: 5px;
        text-align: center;
    }
    .stWarning {
        background-color: #FFE082; /* Soft yellow */
        color: #333333; /* Darker text for readability */
        padding: 10px;
        border-radius: 5px;
        text-align: center;
    }
    /* Text area alignment */
    .stTextArea > div > div > textarea {
        color: #333333;
        background-color: #ffffff;
        border-radius: 5px;
    }
    /* Center markdown descriptions */
    .stMarkdown > div {
        text-align: center;
    }
    /* Checkbox alignment */
    .stCheckbox > label {
        color: #E8ECEB; /* Match text color */
    }
    /* Slider label */
    .stSlider > div > div > div > div {
        color: #E8ECEB; /* Match text color */
    }
    </style>
""", unsafe_allow_html=True)

# Constants
MAX_FILE_SIZE_MB = 10
UPLOAD_DIR = "Uploads"
OUTPUT_DIR = "output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def sanitize_filename(name):
    return re.sub(r'[^\w\-\. ]', '', name)

def log_error(message):
    with open("error_log.txt", "a") as log_file:
        log_file.write(f"{datetime.now()} - {message}\n")
        log_file.write(traceback.format_exc() + "\n")

# Initialize session state
if 'uploaded' not in st.session_state:
    st.session_state.uploaded = False
if 'processed' not in st.session_state:
    st.session_state.processed = False
if 'input_path' not in st.session_state:
    st.session_state.input_path = None
if 'redacted_path' not in st.session_state:
    st.session_state.redacted_path = None
if 'redacted_text' not in st.session_state:
    st.session_state.redacted_text = None
if 'pii_entities' not in st.session_state:
    st.session_state.pii_entities = []
if 'page_count' not in st.session_state:
    st.session_state.page_count = 0
if 'file_key' not in st.session_state:
    st.session_state.file_key = 0

def reset_state():
    st.session_state.uploaded = False
    st.session_state.processed = False
    st.session_state.input_path = None
    st.session_state.redacted_path = None
    st.session_state.redacted_text = None
    st.session_state.pii_entities = []
    st.session_state.page_count = 0
    st.session_state.file_key += 1

# Main content
with st.container():
    st.title("🔒 Secure PDF Redactor")

    # Wrap the markdown in a centered div for precise alignment
    st.markdown("""
    <div style="text-align: center;">
        Upload a PDF (digital or scanned). Click 'Start Redaction' to:<br>
        <ul>
            <li>Extract all text</li>
            <li>Detect Personally Identifiable Information (PII)</li>
            <li>Redact PII with fake data and save a secure PDF</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🧹 Clear All Uploaded/Generated Files"):
        if st.checkbox("✔️ Confirm file deletion"):
            try:
                shutil.rmtree(UPLOAD_DIR)
                shutil.rmtree(OUTPUT_DIR)
                os.makedirs(UPLOAD_DIR, exist_ok=True)
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                reset_state()
                st.success("🧼 All files cleared.")
            except Exception as e:
                log_error(f"Cleanup error: {e}")
                st.error(f"❌ Failed to clear files: {e}")
        else:
            st.warning("⚠️ Please confirm file deletion.")

    if st.button("🔄 Reset"):
        reset_state()
        st.success("🔄 State reset. Upload a new PDF.")

    uploaded_file = st.file_uploader("📄 Upload PDF", type=["pdf"], key=f"uploader_{st.session_state.file_key}")

    if uploaded_file:
        try:
            if uploaded_file.size == 0:
                st.error("❌ Uploaded file is empty.")
                reset_state()
                st.stop()

            if uploaded_file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
                st.error(f"❌ File too large. Max size is {MAX_FILE_SIZE_MB} MB.")
                reset_state()
                st.stop()

            file_name = sanitize_filename(uploaded_file.name)
            if not file_name.lower().endswith(".pdf"):
                st.error("❌ Invalid file type. Please upload a PDF.")
                reset_state()
                st.stop()

            if ".." in file_name or file_name.startswith("/"):
                st.error("❌ Invalid filename detected.")
                reset_state()
                st.stop()

            try:
                reader = PdfReader(uploaded_file, strict=True)
                if not reader.pages:
                    raise ValueError("PDF has no pages.")
            except Exception as e:
                st.error("❌ Invalid or corrupted PDF file.")
                log_error(f"PDF validation failed: {e}")
                reset_state()
                st.stop()

            uploaded_file.seek(0)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            input_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{file_name}")
            output_path = os.path.join(OUTPUT_DIR, f"redacted_{timestamp}_{file_name}")

            with open(input_path, "wb") as f:
                f.write(uploaded_file.read())
            st.success("✅ File uploaded successfully.")

            st.session_state.input_path = input_path
            st.session_state.redacted_path = output_path
            st.session_state.page_count = len(reader.pages)
            st.session_state.uploaded = True
            st.session_state.processed = False

            st.info(f"📄 PDF contains {st.session_state.page_count} pages.")

        except Exception as e:
            log_error(f"Upload error: {e}")
            st.error(f"⚠️ Error: {e}")
            reset_state()

    # Redaction button
    if st.session_state.uploaded and not st.session_state.processed:
        preview_length = st.slider("Select preview length (characters):", 500, 5000, 2000)
        if st.button("🚀 Start Redaction"):
            try:
                with st.spinner("🔍 Extracting text and detecting PII..."):
                    status_code, extracted_text, ocr_text_pages = extract_text_from_pdf(st.session_state.input_path)
                    if status_code == 0:
                        st.error("❌ Failed to extract text. The PDF may be corrupted or OCR may have failed.")
                        reset_state()
                        st.stop()

                if extracted_text.strip():
                    redacted_text, pii_entities = redact_pii(extracted_text)
                    st.session_state.redacted_text = redacted_text
                    st.session_state.pii_entities = pii_entities
                    
                    st.subheader("📑 Redacted Text Preview")
                    preview = redacted_text[:preview_length] + "..." if len(redacted_text) > preview_length else redacted_text
                    st.text_area("Redacted Text:", preview, height=300)

                    with st.expander("📄 View Original Extracted Text"):
                        original_preview = extracted_text[:preview_length] + "..." if len(extracted_text) > preview_length else extracted_text
                        st.text_area("Original Extracted Text", original_preview, height=300)

                    st.info(f"🔐 Detected PII types: {', '.join(pii_entities) if pii_entities else 'None'}")

                    with st.spinner("✏️ Applying redactions to PDF..."):
                        redact_pdf(st.session_state.input_path, st.session_state.redacted_path, ocr_text_pages)
                        st.session_state.processed = True

                else:
                    st.warning("🧠 No text found. Ensure OCR is set up correctly for scanned PDFs.")
                    reset_state()
                    st.stop()

            except Exception as e:
                log_error(f"Redaction error: {e}")
                st.error(f"⚠️ Error: {e}")
                reset_state()

    # Display download buttons if processing is complete
    if st.session_state.processed and st.session_state.redacted_path and os.path.exists(st.session_state.redacted_path):
        st.success("✅ PDF redacted successfully.")
        col1, col2 = st.columns(2)
        with col1:
            with open(st.session_state.redacted_path, "rb") as redacted_file:
                st.download_button(
                    "⬇️ Download Redacted PDF",
                    redacted_file,
                    file_name=os.path.basename(st.session_state.redacted_path),
                    mime="application/pdf",
                    key=f"download_pdf_{st.session_state.file_key}"
                )
        with col2:
            st.download_button(
                "📤 Download Redacted Text",
                st.session_state.redacted_text.encode("utf-8"),
                file_name="redacted_text.txt",
                key=f"download_text_{st.session_state.file_key}"
            )
    elif st.session_state.processed:
        st.error("❌ Redacted PDF not found.")
        log_error("Redacted PDF missing.")
        reset_state()

# Footer
st.markdown("---")
st.caption("Made with ❤️ using Python, Presidio, OCR, and Streamlit.")