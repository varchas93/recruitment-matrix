import re
from docx import Document
import io

def extract_text_from_docx(path):
    try:
        doc = Document(path)
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception:
        return ""

def extract_text_from_pdf(path):
    # lightweight PDF reader using PyPDF2
    try:
        from PyPDF2 import PdfReader
        r = PdfReader(path)
        texts = []
        for page in r.pages:
            texts.append(page.extract_text() or "")
        return "\n".join(texts)
    except Exception:
        return ""

def safe_read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""

# reuse some regex helpers (email, experience)
EMAIL_RE = re.compile(r"[a-zA-Z0-9+._%-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
def find_email(text):
    m = EMAIL_RE.search(text or "")
    return m.group(0) if m else ""

def find_experience_years(text):
    m = re.search(r"(\d+)\+?\s*(years|year|yrs)", (text or "").lower())
    if m:
        try: return int(m.group(1))
        except: return 0
    return 0
