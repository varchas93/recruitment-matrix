from .helpers import find_email, find_experience_years
from collections import Counter

def simple_skills_from_text(text, skill_list=None):
    text = (text or "").lower()
    found = []
    if skill_list:
        for s in skill_list:
            if s.lower() in text:
                found.append(s)
    else:
        # naive skill extraction: words that look like skills (fallback)
        tokens = set([t.strip(".,()") for t in text.split()])
        found = list(tokens)[:5]
    return found

def match_single_resume(jd_text, jd_skills, resume_path):
    # parse resume file (docx or pdf) using helpers in parser; but here just a quick wrapper
    from .helpers import extract_text_from_docx, extract_text_from_pdf, safe_read_text
    ext = resume_path.lower()
    if ext.endswith(".docx"):
        text = extract_text_from_docx(resume_path)
    elif ext.endswith(".pdf"):
        text = extract_text_from_pdf(resume_path)
    else:
        text = safe_read_text(resume_path)
    matched = [s for s in jd_skills if s.strip() and s.lower() in (text or "").lower()]
    score = round((len(matched) / len([s for s in jd_skills if s.strip()]) * 100), 2) if jd_skills else 0
    return {
        "email": find_email(text),
        "experience_found": find_experience_years(text),
        "jd_vs_resume_score": score,
        "skills_matched": matched
    }

def analyze_candidates(jd_text, candidates):
    # candidates: list with keys 'name','email','skills','experience','raw_text'
    out_candidates = []
    for c in candidates:
        text = c.get('raw_text','') or ""
        skills_from_text = c.get('skills') or simple_skills_from_text(text, None)
        # if jd_text present, try to extract skill tokens by words split
        jd_skillset = []
        if jd_text:
            # simple JD skill list by common separators
            possible = [s.strip().lower() for s in jd_text.replace("\n",",").split(",") if s.strip()]
            jd_skillset = possible[:50]
        matched = [s for s in (jd_skillset or []) if s and s.lower() in text.lower()]
        match_pct = (len(matched) / len(jd_skillset) * 100) if jd_skillset else 0
        out_candidates.append({
            "name": c.get('name') or '',
            "email": c.get('email') or '',
            "match": round(match_pct,1),
            "missing": [s for s in (jd_skillset or []) if s not in matched][:10]
        })

    # basic aggregates
    total = len(out_candidates)
    avg_match = (sum([c['match'] for c in out_candidates]) / total) if total else 0
    # top missing skills
    all_missing = []
    for c in out_candidates:
        all_missing.extend(c.get('missing',[]))
    top_missing = []
    if all_missing:
        cnt = Counter(all_missing)
        top_missing = [{"skill":k,"count":v} for k,v in cnt.most_common(10)]

    # skill gap by role is a dummy placeholder; real implementation would need role grouping
    skill_gap_by_role = {"labels":["All Roles"], "data":[round(100-avg_match,1)]}

    heatmap = {"rows":[c.get('name','') for c in out_candidates], "cols": jd_skillset[:10] if jd_skillset else [], "values": []}
    for c in out_candidates:
        # fill a row with normalized values for the limited cols
        row=[]
        for s in (heatmap["cols"] or []):
            row.append(1.0 if s in (c.get('missing') or []) else (0.0 if s in (c.get('missing') or []) else 0.8))
        heatmap["values"].append(row)

    payload = {
        "roles_count": 1,
        "profiles_count": total,
        "avg_gap_percent": round(100 - avg_match,1),
        "avg_match_percent": round(avg_match,1),
        "skill_gap_by_role": skill_gap_by_role,
        "top_missing_skills": top_missing,
        "candidates": out_candidates,
        "heatmap": heatmap
    }
    return payload
