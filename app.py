# SecurePDF Redactor Streamlit App with Educational Background
import streamlit as st
import os
import shutil
import re
from datetime import datetime
from PyPDF2 import PdfReader
import traceback

try:
    from backend.pdf_loader import extract_text_from_pdf
    from backend.redactor import redact_pii
    from backend.pdf_writer import redact_pdf
except ImportError as e:
    st.error(f"Failed to import required modules. Traceback: {traceback.format_exc()}")
    st.stop()

# Constants
MAX_FILE_SIZE_MB = 10
UPLOAD_DIR = "Uploads"
OUTPUT_DIR = "output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def sanitize_filename(name):
    return re.sub(r'[^\w\-. ]', '', name)

def log_error(message):
    with open("error_log.txt", "a") as log_file:
        log_file.write(f"{datetime.now()} - {message}\n")
        log_file.write(traceback.format_exc() + "\n")

# Initialize session state
for key in ["uploaded", "processed", "input_path", "redacted_path", "redacted_text", "pii_entities", "page_count", "file_key"]:
    if key not in st.session_state:
        st.session_state[key] = False if key in ["uploaded", "processed"] else None if "path" in key else [] if key == "pii_entities" else 0

def reset_state():
    for key in ["uploaded", "processed", "input_path", "redacted_path", "redacted_text", "pii_entities", "page_count"]:
        st.session_state[key] = False if key in ["uploaded", "processed"] else None if "path" in key else [] if key == "pii_entities" else 0
    st.session_state.file_key += 1

# Page setup
st.set_page_config(page_title="Secure PDF Redactor", layout="wide")

# Add educational background image or color
page_bg_img = f"""
<style>
[data-testid="stAppViewContainer"] {{
    background-image: url("https://st5.depositphotos.com/10456914/68745/i/600/depositphotos_687458728-stock-photo-open-book-books-gray-concrete.jpg");
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    background-attachment: fixed;
}}
[data-testid="stHeader"] {{
    background: rgba(255,255,255,0.8);
}}
[data-testid="stSidebar"] {{
    background: rgba(255,255,255,0.8);
}}
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)

st.title("🎓🔒 Secure PDF Redactor - Education Edition")
st.markdown("""
Upload a **PDF** (digital or scanned). Click 'Start Redaction' to:

* Extract all text
* Detect Personally Identifiable Information (PII)
* Redact PII with fake data and save a secure PDF
""")

if st.button("🧹 Clear All Uploaded/Generated Files"):
    if st.checkbox("✔️ Confirm file deletion"):
        try:
            shutil.rmtree(UPLOAD_DIR)
            shutil.rmtree(OUTPUT_DIR)
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            st.success("🧼 All files cleared.")
        except Exception as e:
            log_error(f"Cleanup error: {e}")
            st.error(f"❌ Failed to clear files: {e}")

if st.button("🔄 Reset"):
    reset_state()
    st.success("🔄 State reset. Upload a new PDF.")

uploaded_file = st.file_uploader("📄 Upload PDF", type=["pdf"], key=f"uploader_{st.session_state.file_key}")

if uploaded_file:
    try:
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

        reader = PdfReader(uploaded_file, strict=True)
        if not reader.pages:
            raise ValueError("PDF has no pages.")

        uploaded_file.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        input_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{file_name}")
        output_path = os.path.join(OUTPUT_DIR, f"redacted_{timestamp}_{file_name}")

        with open(input_path, "wb") as f:
            f.write(uploaded_file.read())

        st.success("✅ File uploaded successfully.")
        st.session_state.update({
            "input_path": input_path,
            "redacted_path": output_path,
            "page_count": len(reader.pages),
            "uploaded": True,
            "processed": False
        })

        st.info(f"📄 PDF contains {len(reader.pages)} pages.")

    except Exception as e:
        log_error(f"Upload error: {e}")
        st.error(f"⚠️ Error: {e}")
        reset_state()

if st.session_state.uploaded and not st.session_state.processed:
    try:
        preview_length = st.slider("📜 Select preview length (characters):", 500, 5000, 2000)
        with st.spinner("🔍 Extracting text and detecting PII..."):
            status_code, extracted_text, ocr_text_pages = extract_text_from_pdf(st.session_state.input_path)
            if status_code == 0:
                st.error("❌ Failed to extract text. PDF may be corrupted or OCR failed.")
                reset_state()
                st.stop()

            redacted_text, pii_entities = redact_pii(extracted_text)
            st.session_state.update({
                "redacted_text": redacted_text,
                "pii_entities": pii_entities
            })

            st.subheader("📑 Redacted Text Preview")
            preview = redacted_text[:preview_length] + "..." if len(redacted_text) > preview_length else redacted_text
            st.text_area("Redacted Text:", preview, height=300)

            with st.expander("📄 View Original Extracted Text"):
                original_preview = extracted_text[:preview_length] + "..." if len(extracted_text) > preview_length else extracted_text
                st.text_area("Original Extracted Text", original_preview, height=300)

            with st.spinner("✏️ Applying redaction to PDF..."):
                redact_pdf(st.session_state.input_path, st.session_state.redacted_path, ocr_text_pages or [])
                st.session_state.processed = True

    except Exception as e:
        log_error(f"Redaction error: {e}")
        st.error(f"⚠️ Error: {e}")
        reset_state()

if st.session_state.processed and st.session_state.redacted_path and os.path.exists(st.session_state.redacted_path):
    st.success("✅ PDF redacted successfully.")
    col1, col2 = st.columns(2)
    with col1:
        with open(st.session_state.redacted_path, "rb") as redacted_file:
            st.download_button("⬇️ Download Redacted PDF", redacted_file, file_name=os.path.basename(st.session_state.redacted_path), mime="application/pdf")
    with col2:
        st.download_button("📤 Download Redacted Text", st.session_state.redacted_text.encode("utf-8"), file_name="redacted_text.txt")
elif st.session_state.processed:
    st.error("❌ Redacted PDF not found.")
    log_error("Redacted PDF missing.")
    reset_state()
