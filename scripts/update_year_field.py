"""
In-Place-Update von content-index.json: ergänzt 'year'-Feld für OpenStax-
und arXiv-Einträge.

OpenStax: ruft fetch_openstax() (CMS-API) und matched per id.
arXiv:    holt <published> per id_list-Batch direkt aus webUrl der
          existierenden Einträge.

Andere Quellen (Wikibooks, OTL, DOAB, Pressbooks, OAPEN) werden NICHT
angefasst.
"""
import json, re, sys, time
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_content_index import fetch_openstax, HEADERS, TIMEOUT, ARXIV_API

INDEX_PATH = Path(__file__).resolve().parent.parent / "content-index.json"
ARXIV_BATCH = 25  # arXiv ist beim id_list rate-limit-empfindlich
ARXIV_DELAY_S = 6
ARXIV_429_BACKOFF_S = 60


def main() -> None:
    print(f"Lade {INDEX_PATH}")
    entries = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    print(f"  {len(entries)} Einträge total")

    # ── OpenStax: CMS-API neu, match per id ─────────────────────────────────
    print("\n[openstax] Hole frische Metadaten...")
    fresh_os = fetch_openstax()
    os_year = {e["id"]: e.get("year", "") for e in fresh_os if e.get("year")}
    print(f"  {len(os_year)} OpenStax-IDs mit year")

    # ── arXiv: id_list-Batch gegen API, native_id aus webUrl extrahieren ────
    print("\n[arxiv] Sammle native IDs aus webUrl...")
    arxiv_pairs = []  # (entry_id, native_arxiv_id)
    for e in entries:
        if e.get("source") != "arxiv":
            continue
        m = re.search(r"/abs/(.+?)(?:[?#]|$)", e.get("webUrl", ""))
        if m:
            arxiv_pairs.append((e["id"], m.group(1).strip()))
    print(f"  {len(arxiv_pairs)} arxiv-Einträge im Index")

    native_to_eid = {nat: eid for eid, nat in arxiv_pairs}
    arxiv_year: dict[str, str] = {}

    for i in range(0, len(arxiv_pairs), ARXIV_BATCH):
        batch = arxiv_pairs[i : i + ARXIV_BATCH]
        params = {
            "id_list": ",".join(nat for _, nat in batch),
            "max_results": len(batch),
        }
        # Retry bis zu 3x bei 429/timeout
        r = None
        for attempt in range(3):
            try:
                r = requests.get(ARXIV_API, params=params, headers=HEADERS, timeout=60)
                if r.status_code == 429:
                    raise requests.HTTPError(f"429 rate-limited")
                r.raise_for_status()
                break
            except Exception as ex:
                wait = ARXIV_429_BACKOFF_S * (attempt + 1)
                print(f"  batch {i} attempt {attempt + 1}: {ex} — warte {wait}s")
                r = None
                time.sleep(wait)
        if r is None:
            continue

        matched_in_batch = 0
        for block in re.findall(r"<entry>(.*?)</entry>", r.text, re.DOTALL):
            m_id = re.search(r"<id>http://arxiv\.org/abs/([^<]+)</id>", block)
            m_pub = re.search(r"<published>([^<]+)</published>", block)
            if not (m_id and m_pub):
                continue
            nat = m_id.group(1).strip()
            # arXiv liefert ID inkl. Versionssuffix (v1, v2, ...). Strip it.
            nat_base = re.sub(r"v\d+$", "", nat)
            eid = native_to_eid.get(nat) or native_to_eid.get(nat_base)
            if eid:
                year = m_pub.group(1)[:4]
                if year.isdigit():
                    arxiv_year[eid] = year
                    matched_in_batch += 1
        print(f"  batch {i}: {matched_in_batch}/{len(batch)} matched")
        time.sleep(ARXIV_DELAY_S)

    print(f"  {len(arxiv_year)} arxiv-IDs mit year ermittelt")

    # ── Merge in entries ────────────────────────────────────────────────────
    updated = 0
    for e in entries:
        src = e.get("source")
        if src == "openstax" and e["id"] in os_year:
            if e.get("year") != os_year[e["id"]]:
                e["year"] = os_year[e["id"]]
                updated += 1
        elif src == "arxiv" and e["id"] in arxiv_year:
            if e.get("year") != arxiv_year[e["id"]]:
                e["year"] = arxiv_year[e["id"]]
                updated += 1

    print(f"\n→ {updated} Einträge mit year aktualisiert")

    INDEX_PATH.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Geschrieben: {INDEX_PATH}")


if __name__ == "__main__":
    main()
