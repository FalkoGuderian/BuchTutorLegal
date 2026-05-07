#!/usr/bin/env python3
"""
Full content-index rebuild for CI/GitHub Actions.

Runs sequentially:
  1. fetch_content_index.py  -- OpenStax, arXiv, Wikibooks DE/EN
  2. DOAB parallel fetch      -- inline, portable, no absolute paths
  3. Reclassify cat_education
  4. Build compact app index

Output: content-index.json (full) + content-index-app.json (compact)
"""
import json, re, time, sys
from pathlib import Path
from urllib.parse import quote
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

ROOT   = Path(__file__).resolve().parent.parent
INDEX  = ROOT / "content-index.json"
TODAY  = date.today().isoformat()
UA     = "DocWorm-ContentIndexer/1.0 (open-source educational project)"
DOAB_API = "https://directory.doabooks.org/rest/search"
DOAB_LIMIT   = 10
DOAB_WORKERS = 10
DOAB_OFFSETS = list(range(0, 310, 10))   # offsets 0..300

# ── Category helpers ─────────────────────────────────────────────────────────
CAT_MAP = {
    'mathemat': 'cat_math_science', 'physik': 'cat_math_science',
    'chemi': 'cat_math_science', 'biolog': 'cat_health',
    'statist': 'cat_math_science', 'ingenieur': 'cat_cs_tech',
    'informatik': 'cat_cs_tech', 'computer': 'cat_cs_tech',
    'wirtschaft': 'cat_business', 'recht': 'cat_business',
    'geschicht': 'cat_humanities', 'philosoph': 'cat_humanities',
    'soziolog': 'cat_humanities', 'politik': 'cat_humanities',
    'medizin': 'cat_health', 'gesundheit': 'cat_health',
    'kunst': 'cat_arts', 'musik': 'cat_arts',
    'sprach': 'cat_languages', 'linguistik': 'cat_languages',
    'paedagog': 'cat_education',
    'math': 'cat_math_science', 'physic': 'cat_math_science',
    'biology': 'cat_health', 'chemistry': 'cat_math_science',
    'history': 'cat_humanities', 'philosophy': 'cat_humanities',
    'sociology': 'cat_humanities', 'politics': 'cat_humanities',
    'law': 'cat_business', 'economics': 'cat_business',
    'medicine': 'cat_health', 'music': 'cat_arts',
    'linguistics': 'cat_languages', 'language': 'cat_languages',
    'education': 'cat_education', 'engineering': 'cat_cs_tech',
}
def get_cat(title):
    t = title.lower()
    for k, v in CAT_MAP.items():
        if k in t: return v
    return 'cat_general'

DOAB_QUERIES = [
    'mathematics','physics','chemistry','biology','statistics','calculus',
    'algebra','geometry','astronomy','ecology',
    'Mathematik','Physik','Chemie','Biologie','Statistik','Astronomie',
    'Analysis','Numerik',
    'computer science','software engineering','algorithms','data science',
    'artificial intelligence','machine learning','cybersecurity',
    'electrical engineering','mechanical engineering',
    'Informatik','Maschinenbau','Elektrotechnik',
    'economics','management','finance','accounting','law',
    'business administration','marketing','entrepreneurship',
    'Wirtschaft','Recht','Betriebswirtschaft','Finanzen',
    'medicine','health','nursing','public health','neuroscience',
    'pharmacology','epidemiology','psychology clinical',
    'Medizin','Gesundheit','Pharmakologie','Psychiatrie',
    'history','philosophy','sociology','political science','anthropology',
    'archaeology','cultural studies','theology',
    'Geschichte','Philosophie','Soziologie','Theologie',
    'linguistics','language','translation','literature',
    'Linguistik',
    'art history','musicology','architecture','film studies',
    'visual arts','design','theater',
    'Kunstgeschichte','Architektur',
    'pedagogy','education science','didactics',
    'Paedagogik','Didaktik',
]

def doab_fetch(query, offset):
    url = f"{DOAB_API}?query={quote(query)}&limit={DOAB_LIMIT}&offset={offset}&expand=metadata,bitstreams"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(8 * (attempt + 1))
    return []

def doab_entry(item, query):
    meta = {}
    for m in item.get('metadata', []):
        k, v = m.get('key',''), (m.get('value') or '').strip()
        if k and v and k not in meta: meta[k] = v
    title = meta.get('dc.title','').strip()
    if not title: return None
    pages = int(re.sub(r'[^0-9]', '', meta.get('oapen.pages','0') or '0') or 0)
    if 0 < pages < 4: return None
    bits = [b for b in item.get('bitstreams',[])
            if b.get('name','').endswith('.pdf')
            and '.jpg' not in b.get('name','')]
    if not bits: return None
    pdf = None
    for b in bits:
        for m in b.get('metadata',[]):
            if m.get('key') == 'oapen.identifier.downloadUrl':
                pdf = m.get('value'); break
        if pdf: break
    if not pdf:
        link = bits[0].get('retrieveLink','')
        if link: pdf = 'https://library.oapen.org' + link
    if not pdf: return None
    dc_lang = meta.get('dc.language','').lower()
    lang = 'de' if ('german' in dc_lang or any(c in title for c in 'äöüÄÖÜß')) else 'en'
    year_raw = meta.get('dc.date.issued','') or meta.get('dc.date.available','')
    m_year = re.search(r'\b(19|20)\d{2}\b', year_raw)
    year = m_year.group(0) if m_year else ''
    eid = 'doab-' + re.sub(r'[^a-z0-9]+','-',title.lower())[:80].strip('-')
    return {
        'id': eid, 'title': title, 'source': 'doab', 'domain': 'general',
        'category': get_cat(title), 'tags': [query], 'language': lang,
        'webUrl': meta.get('dc.identifier.uri',''),
        'pdfUrl': pdf, 'year': year,
        'license': meta.get('dc.rights','CC-BY'), 'updated': TODAY,
    }


def run_doab(existing_ids):
    """Fetch all DOAB entries in parallel across all offsets × queries."""
    import threading
    lock = threading.Lock()
    all_new = {}

    def fetch_offset(offset):
        local = {}
        for q in DOAB_QUERIES:
            items = doab_fetch(q, offset)
            for item in items:
                e = doab_entry(item, q)
                if not e: continue
                if e['id'] in existing_ids or e['id'] in local: continue
                local[e['id']] = e
            time.sleep(0.15)
        return offset, local

    with ThreadPoolExecutor(max_workers=DOAB_WORKERS) as pool:
        futs = {pool.submit(fetch_offset, off): off for off in DOAB_OFFSETS}
        for fut in as_completed(futs):
            off, local = fut.result()
            with lock:
                added = sum(1 for k in local if k not in all_new)
                all_new.update(local)
            print(f"  DOAB offset={off:3d}: +{len(local):4d} (total new: {len(all_new)})", flush=True)
    return all_new


def reclassify(data):
    EXTRA = [
        (r"(?i)(circuit|platine|oracle|sql|linux|programm|software|hardware|git|docker|web develop)", 'cat_cs_tech'),
        (r"(?i)(earth|geology|ecosystem|species|dna|genetics|quantum|optic)", 'cat_math_science'),
        (r"(?i)(chinese|mandarin|japanese|arabic|grammar|second language)", 'cat_languages'),
        (r"(?i)(therapy|stuttering|disability|mental health|exercise|fitness)", 'cat_health'),
        (r"(?i)(chess|schach|film\b|video game|mythology|democracy|immigration)", 'cat_humanities'),
        (r"(?i)(music\b|fotograf|architektur|theater|film\b|design\b)", 'cat_arts'),
        (r"(?i)(gdpr|dsgvo|supply chain|accounting|bookkeeping)", 'cat_business'),
        (r"(?i)(pedagog|didactik|curriculum|classroom|teacher training)", 'cat_education'),
    ]
    for e in data:
        if e.get('category') == 'cat_education':
            for pat, cat in EXTRA:
                if re.search(pat, e.get('title','')):
                    e['category'] = cat
                    break
            else:
                if e.get('category') == 'cat_education':
                    e['category'] = 'cat_general'
    return data


def build_app_index(data):
    KEEP = {"title", "source", "category", "language", "pdfUrl", "webUrl", "year"}
    stripped = []
    for e in data:
        entry = {k: v for k, v in e.items() if k in KEEP}
        if "year" in entry and not entry.get("year"):
            del entry["year"]
        stripped.append(entry)
    return stripped


def main():
    # Step 1: fetch_content_index.py (OpenStax, arXiv, Wikibooks)
    print("=== Step 1: fetch_content_index.py ===", flush=True)
    import subprocess
    result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'fetch_content_index.py')],
                            capture_output=False)
    if result.returncode != 0:
        print("fetch_content_index.py failed — continuing with existing index")

    # Step 2: DOAB parallel fetch
    print("\n=== Step 2: DOAB fetch ===", flush=True)
    existing = json.loads(INDEX.read_text(encoding='utf-8'))
    existing_ids = {e['id'] for e in existing}
    print(f"Base: {len(existing)} entries", flush=True)
    new_doab = run_doab(existing_ids)
    print(f"DOAB new: {len(new_doab)}", flush=True)
    merged = {e['id']: e for e in existing}
    merged.update(new_doab)
    data = list(merged.values())

    # Step 3: Reclassify
    print("\n=== Step 3: Reclassify ===", flush=True)
    data = reclassify(data)

    # Write full index
    INDEX.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n',
                     encoding='utf-8')
    print(f"content-index.json: {len(data)} entries", flush=True)

    # Step 4: compact app index
    print("\n=== Step 4: Build app index ===", flush=True)
    app_data = build_app_index(data)
    app_index = ROOT / 'content-index-app.json'
    app_index.write_text(json.dumps(app_data, ensure_ascii=False, separators=(',',':')),
                         encoding='utf-8')
    size = app_index.stat().st_size / 1024 / 1024
    print(f"content-index-app.json: {len(app_data)} entries, {size:.1f} MB", flush=True)


if __name__ == '__main__':
    main()
