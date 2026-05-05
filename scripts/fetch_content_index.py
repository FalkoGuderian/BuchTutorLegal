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

WIKIBOOKS_API = "https://de.wikibooks.org/w/api.php"


def fetch_wikibooks_de() -> list[dict]:
    entries = []
    for title in WIKIBOOKS_DE_TITLES:
        params = {
            "action":      "query",
            "titles":      title,
            "prop":        "info|extracts",
            "exintro":     True,
            "explaintext": True,
            "format":      "json",
        }
        try:
            r = requests.get(WIKIBOOKS_API, params=params, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            pages = r.json().get("query", {}).get("pages", {})
        except Exception as e:
            print(f"[wikibooks-de:{title}] Fehler: {e}")
            continue
        finally:
            time.sleep(1)  # Wikibooks rate-limit respektieren

        for page_id, page in pages.items():
            if page_id == "-1":
                continue
            slug     = page.get("title", title).replace(" ", "_")
            abstract = (page.get("extract") or "")[:200]
            entries.append({
                "id":       f"wikibooks-de-{slug.lower().replace('_', '-')}",
                "title":    page.get("title", title),
                "source":   "wikibooks-de",
                "domain":   "general",
                "tags":     ["deutsch"],
                "language": "de",
                "webUrl":   f"https://de.wikibooks.org/wiki/{slug}",
                "pdfUrl":   None,
                "abstract": abstract,
                "license":  "CC-BY-SA-3.0",
                "updated":  TODAY,
            })

    print(f"[wikibooks-de] {len(entries):3d} Buecher")
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
    index = deduplicate(index)

    OUT.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n→ {len(index)} Eintraege  →  {OUT}")


if __name__ == "__main__":
    main()
