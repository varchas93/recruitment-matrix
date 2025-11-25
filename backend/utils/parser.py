import os
import zipfile
import tempfile
from typing import List
import pdfplumber
import docx

def extract_text_from_pdf(path: str) -> str:
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text()
            if txt:
                text_parts.append(txt)
    return "\n".join(text_parts)

def extract_text_from_docx(path: str) -> str:
    doc = docx.Document(path)
    return "\n".join([p.text for p in doc.paragraphs if p.text])

def extract_text_from_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as rf:
        return rf.read()

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
    """
    Parse a JD file (pdf/docx/txt) and return plain text.
    """
    return extract_text_from_file(path) or ""

def _extract_from_zip(zip_path: str, out_dir: str) -> List[str]:
    saved = []
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(out_dir)
        for fname in z.namelist():
            full = os.path.join(out_dir, fname)
            if os.path.isfile(full):
                saved.append(full)
    return saved

def parse_resumes_upload(paths: list, upload_dir: str) -> list:
    """
    paths: list of file paths (pdf/docx/txt/zip)
    Returns: list of candidate dicts: {'name': filename, 'text': extracted_text}
    """
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
