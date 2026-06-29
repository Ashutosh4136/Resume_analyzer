"""
Heuristic-based resume formatting feedback.
No AI/LLM calls — pure pattern matching and rule-based checks on the
extracted resume text. Lives separately from services.py since this
analyzes resume *quality*, not resume-to-JD *matching*.
"""

import re

# ---------------------------------------------------------------------------
# Section detection patterns
# ---------------------------------------------------------------------------

SECTION_PATTERNS = {
    'contact': re.compile(r'\b(email|phone|linkedin|github|portfolio)\b', re.I),
    'summary': re.compile(r'\b(summary|objective|profile|about me)\b', re.I),
    'experience': re.compile(r'\b(experience|employment|work history|professional experience)\b', re.I),
    'education': re.compile(r'\b(education|academic|degree|university|college)\b', re.I),
    'skills': re.compile(r'\b(skills|technical skills|core competencies|technologies)\b', re.I),
    'projects': re.compile(r'\b(projects|portfolio|personal projects)\b', re.I),
    'certifications': re.compile(r'\b(certifications?|licenses?|credentials)\b', re.I),
}

RECOMMENDED_SECTIONS = ['contact', 'summary', 'experience', 'education', 'skills']

# ---------------------------------------------------------------------------
# Quantifiable achievement detection
# ---------------------------------------------------------------------------

QUANT_PATTERNS = re.compile(
    r'(\d+(\.\d+)?\s?%|'
    r'\$\s?\d+[kKmM]?|'
    r'\b\d+(\.\d+)?x\b|'
    r'\b\d+\+?\s?(users|customers|clients|members|engineers|developers|'
    r'projects|hours|days|weeks|months|years|requests|transactions|'
    r'records|servers|countries|teams|reports)\b)',
    re.I,
)

ACTION_VERBS = {
    'led', 'built', 'developed', 'designed', 'created', 'implemented',
    'launched', 'managed', 'improved', 'increased', 'reduced', 'optimized',
    'automated', 'architected', 'spearheaded', 'delivered', 'streamlined',
    'engineered', 'drove', 'scaled', 'achieved', 'transformed',
}

WEAK_OPENERS = {
    'responsible for', 'worked on', 'helped with', 'involved in',
    'assisted with', 'tasked with', 'in charge of',
}

# ---------------------------------------------------------------------------
# Length thresholds
# ---------------------------------------------------------------------------

MIN_WORD_COUNT = 200
MAX_WORD_COUNT_1PAGE = 600
MAX_WORD_COUNT_2PAGE = 1100


def detect_sections(text: str) -> dict:
    return {
        name: bool(pattern.search(text))
        for name, pattern in SECTION_PATTERNS.items()
    }


def missing_recommended_sections(section_results: dict) -> list:
    return [s for s in RECOMMENDED_SECTIONS if not section_results.get(s, False)]


def check_length(text: str) -> dict:
    word_count = len(text.split())

    if word_count < MIN_WORD_COUNT:
        classification = 'too_short'
        message = (
            f"Your resume content is quite short ({word_count} words). "
            "Consider adding more detail to your experience and projects."
        )
    elif word_count <= MAX_WORD_COUNT_1PAGE:
        classification = 'concise'
        message = f"Good length — approximately 1 page ({word_count} words)."
    elif word_count <= MAX_WORD_COUNT_2PAGE:
        classification = 'standard'
        message = f"Standard length — approximately 1-2 pages ({word_count} words)."
    else:
        classification = 'too_long'
        message = (
            f"Your resume is quite long ({word_count} words, likely 3+ pages). "
            "Consider trimming to focus on your most relevant and recent experience."
        )

    return {
        'word_count': word_count,
        'classification': classification,
        'message': message,
    }


def count_quantifiable_achievements(text: str) -> dict:
    matches = QUANT_PATTERNS.findall(text)
    count = len(matches)

    if count == 0:
        message = (
            "No quantifiable achievements detected. Try adding numbers — "
            "e.g. \"reduced load time by 40%\" or \"managed a team of 5\" — "
            "to make your impact concrete."
        )
        level = 'none'
    elif count <= 2:
        message = f"Found {count} quantifiable achievement(s). Adding a few more would strengthen your resume."
        level = 'low'
    elif count <= 5:
        message = f"Found {count} quantifiable achievements — good use of metrics."
        level = 'good'
    else:
        message = f"Found {count} quantifiable achievements — excellent use of measurable impact."
        level = 'excellent'

    return {'count': count, 'level': level, 'message': message}


def check_action_verbs_and_weak_phrases(text: str) -> dict:
    lower_text = text.lower()

    found_action_verbs = sorted({v for v in ACTION_VERBS if re.search(rf'\b{v}\b', lower_text)})
    found_weak_phrases = sorted({p for p in WEAK_OPENERS if p in lower_text})

    if found_weak_phrases:
        message = (
            f"Found {len(found_weak_phrases)} weak phrase(s) like "
            f"\"{found_weak_phrases[0]}\" — replace with strong action verbs "
            f"(e.g. \"led\", \"built\", \"improved\") to sound more impactful."
        )
    elif len(found_action_verbs) >= 5:
        message = f"Strong use of action verbs ({len(found_action_verbs)} distinct verbs found)."
    else:
        message = "Consider starting more bullet points with strong action verbs (e.g. \"led\", \"built\", \"designed\")."

    return {
        'action_verbs_found': found_action_verbs,
        'weak_phrases_found': found_weak_phrases,
        'message': message,
    }


def check_contact_info(text: str) -> dict:
    has_email = bool(re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text))
    has_phone = bool(re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text))

    issues = []
    if not has_email:
        issues.append("No email address detected.")
    if not has_phone:
        issues.append("No phone number detected.")

    return {
        'has_email': has_email,
        'has_phone': has_phone,
        'issues': issues,
    }


def run_formatting_checks(text: str) -> dict:
    """
    Master function — runs all formatting checks and returns a single
    JSON-serializable dict to store on AnalysisSession.formatting_feedback.
    """
    sections = detect_sections(text)
    missing_sections = missing_recommended_sections(sections)

    length_info = check_length(text)
    quant_info = count_quantifiable_achievements(text)
    verbs_info = check_action_verbs_and_weak_phrases(text)
    contact_info = check_contact_info(text)

    score = 100
    score -= len(missing_sections) * 10
    if length_info['classification'] in ('too_short', 'too_long'):
        score -= 10
    if quant_info['level'] == 'none':
        score -= 15
    elif quant_info['level'] == 'low':
        score -= 5
    if verbs_info['weak_phrases_found']:
        score -= 5 * min(len(verbs_info['weak_phrases_found']), 3)
    score -= len(contact_info['issues']) * 10
    score = max(0, min(100, score))

    return {
        'formatting_score': score,
        'sections_detected': sections,
        'missing_sections': missing_sections,
        'length': length_info,
        'quantifiable_achievements': quant_info,
        'action_verbs': verbs_info,
        'contact_info': contact_info,
    }