#!/usr/bin/env python3
"""
Build content-index.json from free educational content sources.

Usage (lokal):
    pip install requests
    python scripts/fetch_content_index.py

Output: content-index.json im Repo-Root (BuchTutorLegal/)
DocWorm laedt es von:
    https://raw.githubusercontent.com/FalkoGuderian/BuchTutorLegal/main/content-index.json
"""

import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

# Windows-Console auf UTF-8 zwingen
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TODAY = date.today().isoformat()
OUT = Path(__file__).parent.parent / "content-index.json"
HEADERS = {"User-Agent": "DocWorm-ContentIndexer/1.0 (open-source educational project)"}
TIMEOUT = 20


# ---------------------------------------------------------------------------
# DocWorm-Kategorien (decken die UI-Chips in app.html ab)
# ---------------------------------------------------------------------------

CAT_MATH      = "cat_math_science"
CAT_CS        = "cat_cs_tech"
CAT_BUSINESS  = "cat_business"
CAT_LANG      = "cat_languages"
CAT_HEALTH    = "cat_health"
CAT_HUM       = "cat_humanities"
CAT_ARTS      = "cat_arts"
CAT_EDU       = "cat_education"

# domain (intern) → DocWorm-Kategorie
DOMAIN_TO_CAT = {
    "mathematics":      CAT_MATH,
    "science":          CAT_MATH,
    "physics":          CAT_MATH,
    "biology":          CAT_HEALTH,    # Anatomie/Physiologie eher Gesundheit
    "computer-science": CAT_CS,
    "business":         CAT_BUSINESS,
    "economics":        CAT_BUSINESS,
    "social-sciences":  CAT_HUM,
    "humanities":       CAT_HUM,
    "study-skills":     CAT_EDU,
}

# Title-Heuristik fuer domain="general" oder unbekannte domains
# Patterns sind absichtlich substring-tolerant (kein \b am Wortende), damit z. B.
# "macro" in "Macroeconomics" matcht und Lokalisierungen (calculo, fizyka) greifen.
TITLE_PATTERNS = [
    # Mathe/Naturwiss (EN + ES + PL + DE)
    (r"(?i)\b(calculus|c[áa]lculo|prealgebra|precalculus|prec[áa]lculo|algebra|trigonometry|geometry|statistics|estad[íi]stica|statistik|analysis|analisis|wahrscheinlich)", CAT_MATH),
    (r"(?i)\b(contemporary mathematics|mathematics|matem[áa]tica|matematik|mathematik)",                                                                                  CAT_MATH),
    (r"(?i)\b(physics|f[íi]sica|fizyka|physik|chemistry|qu[íi]mica|chemie|astronomy|geology|microbiology)",                                                              CAT_MATH),
    (r"(?i)\b(biology|biologia)",                                                                                                                                          CAT_MATH),
    # Gesundheit
    (r"(?i)\b(anatomy|physiology|nursing|nurses|nutrition|nutricion|zywienie|żywienie|psychiatric|mental health|population health|pharmacology|behavioral neuroscience|lifespan)", CAT_HEALTH),
    # CS/Tech
    (r"(?i)\b(python|programming|programmierung|computer science|informatik|data structures|algorithms|principles of data science|information systems|additive manufacturing|latex|elektrotechnik)", CAT_CS),
    # Business/Wirtschaft
    (r"(?i)\b(economics|economia|ekonomia|microeconomic|macroeconomic|mikroekonomia|makroekonomia|micro|macro|management|accounting|finance|marketing|business law|business ethics|entrepreneurship|organizational behavior|intellectual property|introduction to business)", CAT_BUSINESS),
    # Humanities/Gesellschaft
    (r"(?i)\b(history|history?a|government|sociology|psychology|psychologia|philosophy|political|anthropology|life,? liberty)", CAT_HUM),
    # Sprachen/Literatur
    (r"(?i)\b(english|writing|literature|composition|rhetoric|workplace)",                                                      CAT_LANG),
    # Padagogik
    (r"(?i)\b(college success|preparing for college|study skills|learning|education|teaching)",                                CAT_EDU),
]


def derive_category(domain: str, title: str, tags) -> str:
    """Bilde (domain, title, tags) deterministisch auf eine DocWorm-Kategorie ab."""
    cat = DOMAIN_TO_CAT.get((domain or "").lower())
    if cat:
        return cat
    t = (title or "").lower()
    for pat, c in TITLE_PATTERNS:
        if re.search(pat, t):
            return c
    # Tag-Heuristik (z. B. arXiv-categories als Backup)
    tag_str = " ".join(tags or []).lower()
    for pat, c in TITLE_PATTERNS:
        if re.search(pat, tag_str):
            return c
    return CAT_EDU


# ---------------------------------------------------------------------------
# OpenStax (CMS-API, kein Key noetig, CC-BY-4.0)
# ---------------------------------------------------------------------------

OPENSTAX_DOMAIN_MAP = {
    "Math":             "mathematics",
    "Science":          "science",
    "Social Sciences":  "social-sciences",
    "Humanities":       "humanities",
    "Business":         "business",
    "Computer Science": "computer-science",
    "College Success":  "study-skills",
}


# Bekannte OpenStax-Buecher als Fallback (slug → Metadaten)
OPENSTAX_FALLBACK = [
    ("calculus-volume-1",           "Calculus Volume 1",           "mathematics",      ["calculus", "Math"]),
    ("calculus-volume-2",           "Calculus Volume 2",           "mathematics",      ["calculus", "Math"]),
    ("calculus-volume-3",           "Calculus Volume 3",           "mathematics",      ["calculus", "Math"]),
    ("university-physics-volume-1", "University Physics Volume 1", "science",          ["physics", "Science"]),
    ("university-physics-volume-2", "University Physics Volume 2", "science",          ["physics", "Science"]),
    ("university-physics-volume-3", "University Physics Volume 3", "science",          ["physics", "Science"]),
    ("algebra-and-trigonometry-2e", "Algebra and Trigonometry",    "mathematics",      ["algebra", "Math"]),
    ("precalculus-2e",              "Precalculus",                 "mathematics",      ["precalculus", "Math"]),
    ("statistics",                  "Introductory Statistics",     "mathematics",      ["statistics", "Math"]),
    ("chemistry-2e",                "Chemistry",                   "science",          ["chemistry", "Science"]),
    ("biology-2e",                  "Biology",                     "science",          ["biology", "Science"]),
    ("anatomy-and-physiology",      "Anatomy and Physiology",      "science",          ["anatomy", "Science"]),
    ("psychology-2e",               "Psychology",                  "social-sciences",  ["psychology", "Social Sciences"]),
    ("sociology-3e",                "Sociology",                   "social-sciences",  ["sociology", "Social Sciences"]),
    ("economics-3e",                "Economics",                   "business",         ["economics", "Business"]),
    ("microeconomics-3e",           "Principles of Microeconomics","business",         ["microeconomics", "Business"]),
    ("macroeconomics-3e",           "Principles of Macroeconomics","business",         ["macroeconomics", "Business"]),
    ("principles-of-management",    "Principles of Management",    "business",         ["management", "Business"]),
    ("introduction-to-philosophy",  "Introduction to Philosophy",  "humanities",       ["philosophy", "Humanities"]),
    ("us-history",                  "U.S. History",                "humanities",       ["history", "Humanities"]),
    ("introduction-to-python-programming", "Introduction to Python Programming", "computer-science", ["python", "Computer Science"]),
]


# Bücher ohne PDF und ohne Mehrwert gegenüber einer neueren Edition überspringen.
# college-physics-courseware  → nur interaktives Produkt, kein PDF
# life-liberty-and-pursuit-happiness → OpenStax bietet kein PDF an
# marketing-podstawy / zywienie → polnische Editionen, kein API-Zugang
# introduction-sociology → leitet auf 3e weiter, die bereits im Index ist
OPENSTAX_SKIP_SLUGS = {
    "college-physics-courseware",
    "life-liberty-and-pursuit-happiness",
    "marketing-podstawy",
    "zywienie",
    "introduction-sociology",
}

def fetch_openstax() -> list[dict]:
    # Mehrere bekannte Endpoints versuchen
    api_candidates = [
        "https://openstax.org/api/v2/pages/?type=books.Book&fields=title,slug,subjects&limit=200",
        "https://openstax.org/apps/cms/api/v2/pages/?type=books.Book&fields=*&limit=200",
    ]
    raw = None
    for url in api_candidates:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                raw = r.json()
                break
        except Exception:
            pass

    if raw is None:
        print("[openstax]     API nicht erreichbar - nutze Fallback-Liste")
        return _openstax_from_fallback()

    books = raw.get("items", raw.get("results", raw)) if isinstance(raw, dict) else raw
    if not books:
        print("[openstax]     Leere API-Antwort - nutze Fallback-Liste")
        return _openstax_from_fallback()

    entries = []
    for book in books:
        meta = book.get("meta", {}) or {}
        slug = meta.get("slug") or book.get("slug") or ""
        if not slug:
            continue
        if slug in OPENSTAX_SKIP_SLUGS:
            continue

        title = book.get("title") or book.get("book_title") or slug

        subjects = book.get("subjects", []) or []
        subject_names = []
        for s in subjects:
            if isinstance(s, dict):
                subject_names.append(s.get("subject_name") or s.get("name") or "")
            elif isinstance(s, str):
                subject_names.append(s)
        subject_names = [s for s in subject_names if s]

        domain_raw = subject_names[0] if subject_names else ""
        domain = OPENSTAX_DOMAIN_MAP.get(domain_raw, domain_raw.lower() or "general")

        pdf_url = (
            book.get("book_pdf_url")
            or book.get("pdf_url")
            or book.get("high_resolution_pdf_url")
        )

        entries.append({
            "id":       f"openstax-{slug}",
            "title":    title,
            "source":   "openstax",
            "domain":   domain,
            "category": derive_category(domain, title, subject_names),
            "tags":     subject_names,
            "language": "en",
            "webUrl":   f"https://openstax.org/details/books/{slug}",
            "pdfUrl":   pdf_url,
            "license":  "CC-BY-4.0",
            "updated":  TODAY,
        })

    print(f"[openstax]     {len(entries):3d} Buecher")
    return entries or _openstax_from_fallback()


def _openstax_from_fallback() -> list[dict]:
    entries = []
    for slug, title, domain, tags in OPENSTAX_FALLBACK:
        entries.append({
            "id":       f"openstax-{slug}",
            "title":    title,
            "source":   "openstax",
            "domain":   domain,
            "category": derive_category(domain, title, tags),
            "tags":     tags,
            "language": "en",
            "webUrl":   f"https://openstax.org/details/books/{slug}",
            "pdfUrl":   None,
            "license":  "CC-BY-4.0",
            "updated":  TODAY,
        })
    print(f"[openstax]     {len(entries):3d} Buecher (Fallback)")
    return entries


# ---------------------------------------------------------------------------
# arXiv (Atom-API, kein Key noetig)
# ---------------------------------------------------------------------------

ARXIV_CATEGORIES = [
    ("cs.AI",      "computer-science", ["AI", "machine learning"]),
    ("cs.LG",      "computer-science", ["machine learning", "deep learning"]),
    ("math.CA",    "mathematics",      ["calculus", "analysis"]),
    ("math.ST",    "mathematics",      ["statistics", "probability"]),
    ("physics.ed-ph", "physics",       ["physics", "education"]),
    ("q-bio.NC",   "biology",          ["neuroscience"]),
    ("econ.GN",    "economics",        ["economics"]),
]

ARXIV_API = "https://export.arxiv.org/api/query"


def fetch_arxiv(max_per_category: int = 15) -> list[dict]:
    entries = []
    for cat, domain, tags in ARXIV_CATEGORIES:
        params = {
            "search_query": f"cat:{cat}",
            "sortBy":       "submittedDate",
            "sortOrder":    "descending",
            "max_results":  max_per_category,
        }
        try:
            r = requests.get(ARXIV_API, params=params, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
        except Exception as e:
            print(f"[arxiv:{cat}] Fehler: {e}")
            continue

        ids    = re.findall(r"<id>http://arxiv\.org/abs/([^<]+)</id>", r.text)
        titles = re.findall(r"<title>([^<]+)</title>", r.text)[1:]  # [0] ist Feed-Titel

        for arxiv_id, title in zip(ids, titles):
            arxiv_id = arxiv_id.strip()
            title    = title.strip().replace("\n", " ")
            safe_id  = arxiv_id.replace("/", "-")
            entries.append({
                "id":       f"arxiv-{safe_id}",
                "title":    title,
                "source":   "arxiv",
                "domain":   domain,
                "category": derive_category(domain, title, tags + [cat]),
                "tags":     tags + [cat],
                "language": "en",
                "webUrl":   f"https://arxiv.org/abs/{arxiv_id}",
                "pdfUrl":   f"https://arxiv.org/pdf/{arxiv_id}",
                "license":  "arXiv non-exclusive",
                "updated":  TODAY,
            })

    print(f"[arxiv]        {len(entries):3d} Paper")
    return entries


# ---------------------------------------------------------------------------
# Wikibooks Deutsch (MediaWiki API, CC-BY-SA-3.0)
# ---------------------------------------------------------------------------

WIKIBOOKS_DE_TITLES = [
    "Mathematik",
    "Physik",
    "Chemie",
    "Biologie",
    "Informatik",
    "Programmierung in Python",
    "LaTeX",
    "Statistik",
    "Lineare Algebra",
    "Analysis",
    "Elektrotechnik",
    "Astronomie",
]

WIKIBOOKS_DE_API = "https://de.wikibooks.org/w/api.php"


def _wikibooks_de_entry(title: str, abstract: str = "") -> dict:
    slug = title.replace(" ", "_")
    return {
        "id":       f"wikibooks-de-{slug.lower().replace('_', '-')}",
        "title":    title,
        "source":   "wikibooks-de",
        "domain":   "general",
        "category": derive_category("general", title, ["deutsch"]),
        "tags":     ["deutsch"],
        "language": "de",
        "webUrl":   f"https://de.wikibooks.org/wiki/{slug}",
        "pdfUrl":   f"https://de.wikibooks.org/api/rest_v1/page/pdf/{slug}",
        "abstract": abstract,
        "license":  "CC-BY-SA-3.0",
        "updated":  TODAY,
    }


def fetch_wikibooks_de() -> list[dict]:
    abstracts: dict[str, str] = {}
    for title in WIKIBOOKS_DE_TITLES:
        params = {
            "action":      "query",
            "titles":      title,
            "prop":        "extracts",
            "exintro":     True,
            "explaintext": True,
            "format":      "json",
        }
        try:
            r = requests.get(WIKIBOOKS_DE_API, params=params, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            for page in r.json().get("query", {}).get("pages", {}).values():
                abstracts[title] = (page.get("extract") or "")[:200]
        except Exception:
            pass
        finally:
            time.sleep(1)

    entries = [_wikibooks_de_entry(t, abstracts.get(t, "")) for t in WIKIBOOKS_DE_TITLES]
    print(f"[wikibooks-de] {len(entries):3d} Buecher ({len(abstracts)} mit Abstract)")
    return entries


# ---------------------------------------------------------------------------
# Wikibooks Englisch (MediaWiki API, CC-BY-SA-3.0)
# ---------------------------------------------------------------------------

WIKIBOOKS_EN_TITLES = [
    "Calculus",
    "Linear Algebra",
    "Algebra",
    "Statistics",
    "Physics Study Guide",
    "Chemistry",
    "Biology",
    "Astronomy",
    "Electronics",
    "Python Programming",
    "Computer Programming",
    "LaTeX",
    "Introduction to Philosophy",
    "Economics",
    "Human Physiology",
    "Psychology",
    "Sociology",
    "History of Western Civilization",
    "English Grammar",
]

WIKIBOOKS_EN_API = "https://en.wikibooks.org/w/api.php"


def _wikibooks_en_entry(title: str, abstract: str = "") -> dict:
    slug = title.replace(" ", "_")
    return {
        "id":       f"wikibooks-en-{slug.lower().replace('_', '-')}",
        "title":    title,
        "source":   "wikibooks-en",
        "domain":   "general",
        "category": derive_category("general", title, ["english"]),
        "tags":     ["english"],
        "language": "en",
        "webUrl":   f"https://en.wikibooks.org/wiki/{slug}",
        "pdfUrl":   f"https://en.wikibooks.org/api/rest_v1/page/pdf/{slug}",
        "abstract": abstract,
        "license":  "CC-BY-SA-3.0",
        "updated":  TODAY,
    }


def fetch_wikibooks_en() -> list[dict]:
    # URLs sind deterministisch — API nur fuer Abstract (optional).
    # Bei 429 wird der Eintrag trotzdem ohne Abstract angelegt.
    abstracts: dict[str, str] = {}
    for title in WIKIBOOKS_EN_TITLES:
        params = {
            "action":      "query",
            "titles":      title,
            "prop":        "extracts",
            "exintro":     True,
            "explaintext": True,
            "format":      "json",
        }
        try:
            r = requests.get(WIKIBOOKS_EN_API, params=params, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            for page in r.json().get("query", {}).get("pages", {}).values():
                abstracts[title] = (page.get("extract") or "")[:200]
        except Exception:
            pass  # Abstract bleibt leer, Eintrag kommt trotzdem
        finally:
            time.sleep(2)

    entries = [_wikibooks_en_entry(t, abstracts.get(t, "")) for t in WIKIBOOKS_EN_TITLES]
    print(f"[wikibooks-en] {len(entries):3d} Buecher ({len(abstracts)} mit Abstract)")
    return entries


# ---------------------------------------------------------------------------
# Zusammenbauen
# ---------------------------------------------------------------------------

def deduplicate(entries: list[dict]) -> list[dict]:
    seen, out = set(), []
    for e in entries:
        if e["id"] not in seen:
            seen.add(e["id"])
            out.append(e)
    return out


def main() -> None:
    print(f"Baue content-index.json ... ({TODAY})\n")

    index: list[dict] = []
    index.extend(fetch_openstax())
    index.extend(fetch_arxiv(max_per_category=15))
    index.extend(fetch_wikibooks_de())
    time.sleep(5)  # Pause zwischen DE und EN um Rate-Limit zu vermeiden
    index.extend(fetch_wikibooks_en())
    index = deduplicate(index)

    OUT.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n→ {len(index)} Eintraege  →  {OUT}")


if __name__ == "__main__":
    main()
