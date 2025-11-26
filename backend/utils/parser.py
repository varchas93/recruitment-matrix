# utils/parser.py
import os
import zipfile
import tempfile
from typing import List
from pypdf import PdfReader
import docx

def extract_text_from_pdf(path: str) -> str:
    text_parts = []
    try:
        reader = PdfReader(path)
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                text_parts.append(txt)
    except Exception as e:
        # Print error to logs (Render will capture)
        print(f"PDF parsing error for {path}: {e}")
    return "\n".join(text_parts)

def extract_text_from_docx(path: str) -> str:
    try:
        doc = docx.Document(path)
        return "\n".join([p.text for p in doc.paragraphs if p.text])
    except Exception as e:
        print(f"DOCX parsing error for {path}: {e}")
        return ""

def extract_text_from_txt(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as rf:
            return rf.read()
    except Exception as e:
        print(f"TXT read error for {path}: {e}")
        return ""

def extract_text_from_file(path: str) -> str:
    path = os.path.abspath(path)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    elif ext in (".docx", ".doc"):
        return extract_text_from_docx(path)
    elif ext == ".txt":
        return extract_text_from_txt(path)
    else:
        return ""

def parse_jd_file(path: str) -> str:
    return extract_text_from_file(path) or ""

def _extract_from_zip(zip_path: str, out_dir: str) -> List[str]:
    saved = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(out_dir)
            for fname in z.namelist():
                full = os.path.join(out_dir, fname)
                if os.path.isfile(full):
                    saved.append(full)
    except Exception as e:
        print(f"Zip extraction error for {zip_path}: {e}")
    return saved

def extract_email(text):
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    match = re.search(email_pattern, text)
    return match.group(0) if match else None
def parse_resumes_upload(paths: list, upload_dir: str) -> list:
    candidates = []
    tmpdir = tempfile.mkdtemp(dir=upload_dir)
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        if ext == ".zip":
            extracted = _extract_from_zip(p, tmpdir)
            for e in extracted:
                text = extract_text_from_file(e)
                if text:
                    candidates.append({"name": os.path.basename(e), "text": text})
        else:
            text = extract_text_from_file(p)
            if text:
                candidates.append({"name": os.path.basename(p), "text": text})
    return candidates
