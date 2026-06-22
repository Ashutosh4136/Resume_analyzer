# ResumeMatch — Resume Analyzer & Job Description Matcher

A full-stack Django web application that analyzes how well a resume matches a job description using NLP-based keyword extraction and similarity scoring. Built to help job seekers identify missing keywords and optimize their resumes before applying.

---

## Features

- **PDF Resume Upload** — drag-and-drop or click-to-browse upload with validation (PDF only, max 5MB)
- **NLP-Powered Analysis** — extracts unigrams and bigrams from resume and job description text using NLTK, with stopword removal
- **Dual Scoring System**
  - **Standard Match Score** — Jaccard similarity between resume and JD keyword sets
  - **Weighted Match Score** — gives more credit for matching high-value keywords (skills, tools) over generic terms
- **Keyword Categorization** — automatically classifies keywords as Skill, Tool, Qualification, or General
- **Keyword Suggestions with Context** — missing keywords come with a suggested resume section to add them to (e.g. "Add to Skills section")
- **Re-Analysis Without Re-Upload** — edit the job description and re-run analysis on an existing session using the same PDF
- **Multiple Resume Versions** — save and label multiple resumes (e.g. "Backend Role", "Data Role") and pick one at upload time
- **PDF Export** — download a formatted PDF report of any analysis result using ReportLab
- **Score Trend Visualization** — Chart.js line chart on the profile page showing match score history over time
- **Email Notifications** — optional email alert when an analysis completes (console backend in development)
- **Analysis History** — paginated table of past analyses with client-side search/filter by job title or company
- **AJAX Delete** — remove past analyses without a full page reload
- **Empty-State Handling** — friendly error messages for scanned/image-only PDFs or empty job descriptions instead of a misleading 0% score
- **Authentication** — registration, login, logout, and a profile page using Django's built-in auth system
- **Dark UI Theme** — dark background with a light, floating navbar for a modern dashboard feel

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Django |
| Frontend | HTML, CSS, JavaScript, Bootstrap 5 |
| Charts | Chart.js |
| Database | SQLite (Django default) |
| PDF Parsing | pdfplumber |
| NLP | NLTK (tokenization, stopwords, n-grams) |
| PDF Generation | ReportLab |

---

## Project Structure

```
resume_analyzer/
├── manage.py
├── db.sqlite3
├── media/                          # uploaded resumes (gitignored)
├── static/
├── templates/
│   └── base.html                   # dark theme + light navbar layout
├── core/
│   ├── models.py                   # AnalysisSession, KeywordResult, ResumeVersion, UserProfile
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   ├── services.py                 # all NLP logic — extraction, scoring, categorization
│   ├── notifications.py            # email notification logic
│   ├── pdf_export.py               # ReportLab PDF report generation
│   ├── signals.py                  # auto-creates UserProfile on User creation
│   └── templates/core/
│       ├── upload.html
│       ├── results.html
│       ├── reanalyze.html
│       ├── history.html
│       ├── resume_versions.html
│       └── confirm_delete.html
├── users/
│   ├── views.py                    # register, login, logout, profile
│   ├── forms.py
│   ├── urls.py
│   └── templates/users/
│       ├── login.html
│       ├── register.html
│       └── profile.html
└── resume_analyzer/
    ├── settings.py
    └── urls.py
```

---

## Setup Instructions

### 1. Clone and create a virtual environment

```bash
git clone <your-repo-url>
cd resume_analyzer
python -m venv venv

# Windows
venv\Scripts\activate



### 2. Install dependencies

```bash
pip install django pdfplumber nltk reportlab
```

### 3. Download required NLTK data (one-time)

```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('punkt_tab')"
```

> Note: `core/services.py` also attempts to auto-download these on first run if missing.

### 4. Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Create a superuser (optional, for Django admin access)

```bash
python manage.py createsuperuser
```

### 6. Run the development server

```bash
python manage.py runserver
```

Visit **http://127.0.0.1:8000/** in your browser.

---

## Core NLP Pipeline (`core/services.py`)

1. **`extract_text(pdf_path)`** — extracts raw text from a PDF using pdfplumber, returns an empty string on parse failure
2. **`extract_keywords(text)`** — tokenizes text, lowercases, strips punctuation, removes NLTK stopwords, and extracts both unigrams and bigrams
3. **`compute_match_score(resume_keywords, jd_keywords)`** — Jaccard similarity: `|intersection| / |union| × 100`
4. **`compute_weighted_match_score(keyword_results)`** — sums `importance_weight` of matched keywords over total weight, giving skills/tools more influence than generic terms
5. **`categorise_keyword(keyword)`** — pattern-matches keywords into Skill / Tool / Qualification / General categories
6. **`run_analysis(session)`** — orchestrates the full pipeline and persists `KeywordResult` rows; raises `AnalysisError` for unreadable PDFs or empty job descriptions

---

## Key Design Decisions

- **Strict separation of concerns** — all NLP logic lives in `services.py`; views handle only HTTP concerns
- **Idempotent re-analysis** — `run_analysis()` clears old `KeywordResult` rows before recreating them, so re-running analysis never duplicates data
- **Atomic user creation** — `UserProfile` is created within `transaction.atomic()` during registration, and a `post_save` signal guarantees a profile exists even for users created via `createsuperuser` or the admin panel
- **Resilient email delivery** — notification failures are caught and logged silently so they never interrupt the user-facing analysis flow
- **Graceful degradation** — scanned/image-only PDFs and empty job descriptions raise a descriptive `AnalysisError` instead of silently producing a meaningless 0% score

---

## Environment Notes

- **Email**: Development uses Django's console email backend (prints emails to the terminal). To send real emails, update `EMAIL_BACKEND` and SMTP credentials in `settings.py`.
- **Media files**: Uploaded resumes are stored under `media/resumes/`, `media/resume_versions/`, and `media/default_resumes/`. Make sure `MEDIA_ROOT` and `MEDIA_URL` are configured for production (e.g. served via Nginx or cloud storage like S3).
- **Database**: Uses SQLite by default — suitable for development and small deployments. Swap `DATABASES` in `settings.py` for PostgreSQL in production.

---

## Future Improvements

- Async analysis processing with Celery + Redis for large PDFs
- spaCy-based keyword extraction with POS tagging for more accurate noun-phrase detection
- Resume formatting feedback (section detection, length checks, quantifiable achievement detection)
- Side-by-side comparison of one resume against multiple job descriptions

