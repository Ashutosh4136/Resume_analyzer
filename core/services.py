"""
All NLP / analysis business logic lives here — never in views.py.
"""

import re
import logging
import pdfplumber
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.util import ngrams
from .formatting_checks import run_formatting_checks
from .ai_feedback import generate_ai_feedback

logger = logging.getLogger(__name__)

# Download required NLTK data on first run
def _ensure_nltk_data():
    for resource in ('punkt', 'stopwords', 'punkt_tab'):
        try:
            nltk.data.find(f'tokenizers/{resource}')
        except LookupError:
            nltk.download(resource, quiet=True)

_ensure_nltk_data()

STOP_WORDS = set(stopwords.words('english'))

# A lightweight allow-list of tech/domain terms we never strip even if NLTK
# marks them as stop-words (rare, but good guard-rail).
PRESERVE_TERMS = {
    'c', 'r', 'go', 'ai', 'ml', 'ui', 'ux', 'qa', 'bi',
    'aws', 'gcp', 'sql', 'api', 'git', 'css', 'php',
}


# ---------------------------------------------------------------------------
# 1. PDF text extraction
# ---------------------------------------------------------------------------

def extract_text(pdf_path: str) -> str:
    """
    Extract and return all text from a PDF using pdfplumber.
    Returns an empty string on any parse error.
    """
    try:
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        raw = '\n'.join(text_parts)
        # Collapse excessive whitespace
        clean = re.sub(r'\s+', ' ', raw).strip()
        return clean
    except Exception as exc:
        logger.error("PDF extraction failed for %s: %s", pdf_path, exc)
        return ''


# ---------------------------------------------------------------------------
# 2. Keyword extraction
# ---------------------------------------------------------------------------

def _clean_token(token: str) -> str:
    """Strip punctuation and return lowercase token."""
    return re.sub(r'[^a-z0-9\+\#]', '', token.lower())


def extract_keywords(text: str) -> set:
    """
    Tokenise *text*, remove stop-words, extract unigrams + bigrams.
    Returns a set of keyword strings.
    """
    if not text:
        return set()

    tokens = word_tokenize(text.lower())
    cleaned = [_clean_token(t) for t in tokens]
    # Keep tokens that are non-empty, not pure stop-words (unless preserved),
    # and at least 2 chars long.
    unigrams = {
        t for t in cleaned
        if t and len(t) >= 2 and (t not in STOP_WORDS or t in PRESERVE_TERMS)
    }

    # Bigrams from the *original* cleaned token list (preserves phrase meaning)
    raw_bigrams = ngrams(cleaned, 2)
    bigram_set = {
        f"{a} {b}"
        for a, b in raw_bigrams
        if a and b
        and len(a) >= 2 and len(b) >= 2
        and a not in STOP_WORDS
        and b not in STOP_WORDS
    }

    return unigrams | bigram_set


# ---------------------------------------------------------------------------
# 3. Match score
# ---------------------------------------------------------------------------

def compute_match_score(resume_keywords: set, jd_keywords: set) -> float:
    """
    Jaccard similarity: |intersection| / |union| * 100
    Returns a float in [0, 100]. Returns 0.0 if both sets are empty.
    """
    if not resume_keywords and not jd_keywords:
        return 0.0
    union = resume_keywords | jd_keywords
    intersection = resume_keywords & jd_keywords
    return round(len(intersection) / len(union) * 100, 2)


# ---------------------------------------------------------------------------
# 4. Category heuristic
# ---------------------------------------------------------------------------

_SKILL_PATTERNS = re.compile(
    r'\b(python|java|javascript|typescript|react|angular|vue|django|flask|'
    r'fastapi|node|express|spring|sql|nosql|postgres|mysql|mongodb|redis|'
    r'docker|kubernetes|aws|gcp|azure|terraform|ci/cd|git|linux|bash|'
    r'machine learning|deep learning|nlp|data science|tensorflow|pytorch|'
    r'scikit|pandas|numpy|excel|tableau|power bi|spark|hadoop|kafka)\b',
    re.I,
)

_TOOL_PATTERNS = re.compile(
    r'\b(jira|confluence|slack|github|gitlab|bitbucket|jenkins|ansible|'
    r'figma|photoshop|illustrator|vs code|postman|swagger)\b',
    re.I,
)

_QUAL_PATTERNS = re.compile(
    r'\b(bachelor|master|phd|mba|degree|certification|certified|diploma|'
    r'years experience|agile|scrum|kanban|pmp|aws certified)\b',
    re.I,
)


def categorise_keyword(keyword: str) -> str:
    if _SKILL_PATTERNS.search(keyword):
        return 'skill'
    if _TOOL_PATTERNS.search(keyword):
        return 'tool'
    if _QUAL_PATTERNS.search(keyword):
        return 'qualification'
    return 'general'


# ---------------------------------------------------------------------------
# 5. Importance weight heuristic
# ---------------------------------------------------------------------------

def importance_weight(keyword: str, category: str) -> float:
    weights = {'skill': 1.5, 'tool': 1.2, 'qualification': 1.3, 'general': 1.0}
    base = weights.get(category, 1.0)
    # Bigrams are usually more specific → slight boost
    if ' ' in keyword:
        base += 0.2
    return round(base, 2)


# ---------------------------------------------------------------------------
# 6. Weighted match score
# ---------------------------------------------------------------------------

def compute_weighted_match_score(keyword_results) -> float:
    """
    Weighted match score: sum of importance_weight for matched keywords
    divided by sum of importance_weight for all JD keywords, * 100.

    Unlike plain Jaccard, this gives more credit for matching high-value
    keywords (skills) than low-value ones (general terms).

    `keyword_results` is an iterable of KeywordResult-like objects with
    `.found_in_resume` and `.importance_weight` attributes.
    """
    keyword_results = list(keyword_results)
    if not keyword_results:
        return 0.0

    total_weight = sum(kr.importance_weight for kr in keyword_results)
    if total_weight == 0:
        return 0.0

    matched_weight = sum(kr.importance_weight for kr in keyword_results if kr.found_in_resume)
    return round(matched_weight / total_weight * 100, 2)


# ---------------------------------------------------------------------------
# 7. Master analysis pipeline
# ---------------------------------------------------------------------------

class AnalysisError(Exception):
    """Raised when analysis cannot proceed meaningfully."""
    pass


def run_analysis(session) -> None:
    """
    Full pipeline:
      1. Extract text from the uploaded PDF.
      2. Extract keywords from both resume and JD.
      3. Compute Jaccard + weighted match scores.
      4. Persist KeywordResult rows.
      5. Generate qualitative AI feedback (Groq) — never blocks on failure.
      6. Save everything to the session.

    Raises AnalysisError if the PDF has no extractable text or the JD
    has no usable keywords.
    """
    from .models import KeywordResult

    pdf_path = session.resume_file.path
    resume_text = extract_text(pdf_path)

    if not resume_text or len(resume_text.strip()) < 30:
        raise AnalysisError(
            "We couldn't read any text from this PDF. It may be a scanned "
            "image rather than a text-based PDF. Try exporting your resume "
            "directly from Word/Google Docs as a PDF, or run it through an "
            "OCR tool first."
        )

    jd_text = session.job_description
    resume_kw = extract_keywords(resume_text)
    jd_kw = extract_keywords(jd_text)

    if not jd_kw:
        raise AnalysisError(
            "We couldn't extract any meaningful keywords from the job "
            "description. Please make sure it's not empty or just a few words."
        )

    score = compute_match_score(resume_kw, jd_kw)
    session.match_score = score

    # Clear old keyword rows first — important for re-analysis
    KeywordResult.objects.filter(session=session).delete()

    kw_objects = []
    for kw in jd_kw:
        cat = categorise_keyword(kw)
        kw_objects.append(KeywordResult(
            session=session,
            keyword=kw,
            found_in_resume=(kw in resume_kw),
            category=cat,
            importance_weight=importance_weight(kw, cat),
        ))

    created = KeywordResult.objects.bulk_create(kw_objects)

        # Weighted score computed from the same in-memory objects (no extra query)
    session.weighted_score = compute_weighted_match_score(created)

        # Resume formatting/quality checks — pure heuristics, no API call
    session.formatting_feedback = run_formatting_checks(resume_text)

        # Qualitative AI feedback via Groq — never raises, returns '' on failure
    session.ai_feedback = generate_ai_feedback(
            resume_text=resume_text,
            job_description=jd_text,
            job_title=session.job_title,
            company_name=session.company_name,
        )

    session.save(update_fields=[
            'match_score', 'weighted_score', 'formatting_feedback', 'ai_feedback'
        ])