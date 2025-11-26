import os
import zipfile
import tempfile
from typing import List
from pypdf import PdfReader  # USE pypdf instead of pdfplumber
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
        print("PDF parsing error:", e)
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
