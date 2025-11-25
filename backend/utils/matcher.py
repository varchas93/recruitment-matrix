import re
from typing import List, Dict, Any, Set
from collections import defaultdict
import difflib

# ---- Sample skill map (you can move this to a separate file) ----
# Ideally load a JSON of canonical skills + variants for production.
SKILL_MAP = {
    "Python": ["python3", "py"],
    "SQL": ["mysql", "postgresql", "mariadb", "t-sql", "structured query language"],
    "Excel": ["ms excel", "excel", "pivot table", "vlookup"],
    "Power BI": ["powerbi", "power bi"],
    "Tableau": ["tableau"],
    "Pandas": ["pandas", "pd"],
    "Machine Learning": ["machine learning", "ml", "deep learning"],
    "Data Analysis": ["data analysis", "data analytics"],
    "Communication": ["presentation", "communication", "written communication"]
}

# --------------------------
# Text normalization & patterns
# --------------------------
def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^\w\s+#\+]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def build_skill_patterns(skill_map: dict):
    patterns = {}
    for canonical, variants in skill_map.items():
        all_vars = [canonical.lower()] + [v.lower() for v in variants]
        # sort by length (longer first)
        all_vars = sorted(set(all_vars), key=lambda x: -len(x))
        parts = [r"\b" + re.escape(v) + r"\b" for v in all_vars]
        patterns[canonical] = re.compile("|".join(parts), flags=re.IGNORECASE)
    return patterns

# --------------------------
# Extraction logic
# --------------------------
def extract_skills_from_text(text: str, skill_map: dict = SKILL_MAP, fuzzy_cutoff: float = 0.85):
    norm = normalize_text(text)
    tokens = norm.split()
    patterns = build_skill_patterns(skill_map)
    matches = defaultdict(lambda: {"count": 0, "examples": set(), "score": 0.0})

    # exact matches
    for skill, pat in patterns.items():
        for m in pat.finditer(norm):
            phrase = m.group(0).strip()
            matches[skill]["count"] += 1
            matches[skill]["examples"].add(phrase)
            matches[skill]["score"] += 1.0

    # fuzzy fallback for skills with zero exact matches
    zero_skills = [s for s in skill_map.keys() if matches[s]["count"] == 0]
    n = len(tokens)
    max_ngram = 4
    for i in range(n):
        for l in range(1, max_ngram+1):
            if i + l > n:
                break
            gram = " ".join(tokens[i:i+l])
            if len(gram) < 2:
                continue
            for skill in zero_skills:
                variants = [skill.lower()] + [v.lower() for v in skill_map[skill]]
                best = 0.0
                for v in variants:
                    r = difflib.SequenceMatcher(None, gram, v).ratio()
                    if r > best:
                        best = r
                if best >= fuzzy_cutoff:
                    matches[skill]["count"] += 1
                    matches[skill]["examples"].add(gram)
                    matches[skill]["score"] += 0.6 * best

    # prepare outputs
    matches_out = {}
    ranked = []
    for skill, data in matches.items():
        matches_out[skill] = {
            "count": data["count"],
            "examples": list(data["examples"]),
            "score": round(data["score"], 3)
        }
        if data["count"] > 0:
            ranked.append((skill, round(data["score"], 3), data["count"], list(data["examples"])[:3]))
    ranked.sort(key=lambda x: (-x[1], -x[2], x[0]))

    return {
        "matches": matches_out,
        "ranked": ranked,
        "total_tokens": len(tokens)
    }

# --------------------------
# Matching & scoring
# --------------------------
def _skills_set_from_extraction(extr: dict) -> Set[str]:
    return {skill for skill, meta in extr.get("matches", {}).items() if meta.get("score", 0) > 0}

def calculate_jd_resume_match(resume_results: dict, jd_results: dict) -> dict:
    resume_skills = _skills_set_from_extraction(resume_results)
    jd_skills = _skills_set_from_extraction(jd_results)

    matched = resume_skills & jd_skills
    missing = jd_skills - resume_skills
    extra = resume_skills - jd_skills

    if len(jd_skills) == 0:
        match_percent = 0.0
    else:
        match_percent = round((len(matched) / len(jd_skills)) * 100.0, 2)

    return {
        "resume_skills": sorted(list(resume_skills)),
        "jd_skills": sorted(list(jd_skills)),
        "matched_skills": sorted(list(matched)),
        "missing_skills": sorted(list(missing)),
        "extra_skills": sorted(list(extra)),
        "match_score_percent": match_percent
    }

def progress_bar(percent: float, length: int = 20) -> str:
    """
    Returns a simple unicode progress bar string (length characters).
    """
    try:
        p = max(0.0, min(100.0, float(percent)))
    except:
        p = 0.0
    filled = int(round((p / 100.0) * length))
    bar = "█" * filled + "░" * (length - filled)
    return f"{bar} {p}%"

# --------------------------
# Analyze candidates (JD -> many candidates) - top-level
# --------------------------
def analyze_candidates(jd_text: str, candidates: List[Dict[str, Any]], fuzzy_cutoff: float = 0.85, include_match_breakdown: bool = True) -> dict:
    """
    Runs extraction for JD and each candidate, calculates match percent and returns full details.
    candidates: list of dicts {'name':..., 'text': ...}
    """
    jd_results = extract_skills_from_text(jd_text or "", SKILL_MAP, fuzzy_cutoff=fuzzy_cutoff)
    out = {
        "jd": jd_results,
        "candidates": []
    }

    for cand in candidates:
        name = cand.get("name") or cand.get("filename") or "Candidate"
        text = cand.get("text", "") or ""
        resume_results = extract_skills_from_text(text, SKILL_MAP, fuzzy_cutoff=fuzzy_cutoff)
        match_info = calculate_jd_resume_match(resume_results, jd_results) if include_match_breakdown else {}

        # add progress bar representation
        match_info["progress_bar"] = progress_bar(match_info.get("match_score_percent", 0.0))

        out["candidates"].append({
            "name": name,
            "resume_results": resume_results,
            "match": match_info
        })

    return out

# --------------------------
# match_single_resume helper (keeps compatibility with your old flow)
# --------------------------
def match_single_resume(jd_text: str, jd_skills_list: List[str], resume_path: str, fuzzy_cutoff: float = 0.85) -> dict:
    """
    Keep previous endpoint compatibility: jd_text and jd_skills_list can be provided.
    If jd_skills_list provided, we will create a fake jd_results using them.
    """
    # parse resume file
    # Simple extraction — reuse extract_skills_from_text after reading file
    # We'll try reading the file path (pdf/docx/txt)
    import os
    from utils.parser import extract_text_from_file
    text = extract_text_from_file(resume_path)
    resume_results = extract_skills_from_text(text, SKILL_MAP, fuzzy_cutoff=fuzzy_cutoff)

    if jd_skills_list:
        jd_results = {"matches": {s: {"count": 1, "examples": [], "score": 1.0} for s in jd_skills_list}}
    else:
        jd_results = extract_skills_from_text(jd_text or "", SKILL_MAP, fuzzy_cutoff=fuzzy_cutoff)

    match_info = calculate_jd_resume_match(resume_results, jd_results)
    match_info["progress_bar"] = progress_bar(match_info.get("match_score_percent", 0.0))

    return {
        "resume_results": resume_results,
        "jd_results": jd_results,
        "match": match_info
    }
