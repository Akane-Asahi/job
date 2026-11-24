#!/usr/bin/env python3
"""Merge one day's scan into data/jobs.json.

Usage:
  python3 scripts/merge.py candidates.json [--date YYYY-MM-DD] [--notes "..."]

candidates.json is a JSON list of job objects found today. Required keys per job:
  title, employer, region (regina|toronto|alberta), city, url, source, role_family,
  match_score (0-100), categories (list), ai_related (bool)
Optional: work_mode, employment_type, seniority, salary_text, salary_min_cad,
  salary_max_cad, posted_date, closing_date, status, skills_tags, why,
  eligibility_note, verified, coverage (ignored on jobs; pass via --coverage file).

What it does:
  * matches today's jobs to existing ones (same URL, or same normalized
    employer + title + region); repeats keep first_seen, get last_seen = today,
    times_seen += 1, and a history event when status/closing/salary/score changed
  * new jobs get first_seen = last_seen = today
  * ages jobs: closing_date in the past -> closed; open jobs not seen for 21+ days
    -> likely_closed (a later sighting re-opens them)
  * recomputes the 'urgent_apply' category from closing dates
  * appends a run summary to runs[]
  * archives old closed jobs when the file passes the size policy
"""
import argparse, datetime as dt, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "jobs.json")
REGIONS = ("regina", "toronto", "alberta")
OPEN = {"active", "unknown", "likely_closed"}
# links that are job-board SEARCH pages, not a posting; these are rejected
SEARCH_URL = re.compile(r"indeed\.com/(q-|[A-Za-z-]+-jobs)|glassdoor\.[a-z.]+/Job/.*SRCH|ziprecruiter\.com/Jobs/|linkedin\.com/jobs/[a-z-]+-jobs|talent\.com/jobs/k-|roberthalf\.com/ca/en/(jobs/|job-details/)|jobbank\.gc\.ca/marketreport", re.I)
MAX_BYTES, MAX_JOBS, ARCHIVE_AFTER_DAYS = 1_500_000, 2500, 120

def norm(s):
    s = (s or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\b(inc|ltd|llc|corp|corporation|limited|the|client|co)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def key(j):
    return f"{j['region']}|{norm(j['employer'])}|{norm(j['title'])}"

def slug(j):
    return re.sub(r"[^a-z0-9]+", "-", f"{j['region']}-{j['employer']}-{j['title']}".lower()).strip("-")[:90]

def d(s):
    return dt.date.fromisoformat(s) if s else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--notes", default="")
    ap.add_argument("--coverage", help="JSON file {worked:[], blocked_or_thin:[]}")
    a = ap.parse_args()
    today = a.date
    T = d(today)

    data = json.load(open(DATA))
    jobs = data["jobs"]
    cands = json.load(open(a.candidates))
    by_url = {j["url"]: j for j in jobs if j.get("url")}
    by_key = {key(j): j for j in jobs}
    ids = {j["id"] for j in jobs}

    new = seen_again = 0
    touched = set()
    for c in cands:
        missing = [k for k in ("title", "employer", "region", "url") if not c.get(k)]
        if c.get("url") and SEARCH_URL.search(c["url"]):
            print("skip (search page, not a posting):", c.get("title"), c["url"], file=sys.stderr); continue
        if missing or c["region"] not in REGIONS:
            print("skip (bad record):", c.get("title"), missing, file=sys.stderr); continue
        hit = by_url.get(c["url"]) or by_key.get(key(c))
        if hit:
            if hit["id"] in touched:
                continue
            touched.add(hit["id"])
            changes = []
            for f in ("status", "closing_date", "salary_text", "match_score"):
                if c.get(f) not in (None, "") and c.get(f) != hit.get(f):
                    changes.append(f"{f}: {hit.get(f)} -> {c.get(f)}")
                    hit[f] = c[f]
            if hit["status"] in ("likely_closed",) and c.get("status", "active") == "active":
                hit["status"] = "active"; changes.append("re-opened")
            for f in ("salary_min_cad", "salary_max_cad", "posted_date", "work_mode", "employment_type", "seniority", "why", "eligibility_note"):
                if c.get(f) and not hit.get(f):
                    hit[f] = c[f]
            hit["categories"] = sorted(set(hit.get("categories", [])) | set(c.get("categories", [])))
            hit["skills_tags"] = list(dict.fromkeys((hit.get("skills_tags") or []) + (c.get("skills_tags") or [])))[:12]
            if hit["last_seen"] != today:
                hit["times_seen"] = hit.get("times_seen", 1) + 1
                hit["last_seen"] = today
                seen_again += 1
            hit.setdefault("history", []).append({"date": today, "event": "seen_again", "note": "; ".join(changes) or "still listed"})
        else:
            j = {
                "id": slug(c), "title": c["title"], "employer": c["employer"], "region": c["region"],
                "city": c.get("city", ""), "work_mode": c.get("work_mode"), "employment_type": c.get("employment_type"),
                "seniority": c.get("seniority"), "role_family": c.get("role_family", "ux_product_design"),
                "salary_text": c.get("salary_text"), "salary_min_cad": c.get("salary_min_cad"), "salary_max_cad": c.get("salary_max_cad"),
                "posted_date": c.get("posted_date"), "closing_date": c.get("closing_date"),
                "first_seen": today, "last_seen": today, "times_seen": 1, "status": c.get("status", "active"),
                "categories": c.get("categories", []), "match_score": int(c.get("match_score", 50)),
                "ai_related": bool(c.get("ai_related")), "skills_tags": c.get("skills_tags", []),
                "why": c.get("why", ""), "eligibility_note": c.get("eligibility_note", ""),
                "url": c["url"], "source": c.get("source", ""), "verified": c.get("verified", "search-snippet"),
                "history": [{"date": today, "event": "first_seen", "note": "Daily scan"}],
            }
            base, n = j["id"], 2
            while j["id"] in ids:
                j["id"] = f"{base}-{n}"; n += 1
            ids.add(j["id"]); jobs.append(j); by_url[j["url"]] = j; by_key[key(j)] = j
            touched.add(j["id"]); new += 1

    # ageing + urgent recompute
    closed_today = 0
    for j in jobs:
        cd = d(j.get("closing_date"))
        if cd and cd < T and j["status"] in OPEN:
            j["status"] = "closed"; closed_today += 1
            j.setdefault("history", []).append({"date": today, "event": "closed", "note": "closing date passed"})
        elif j["status"] == "active" and (T - d(j["last_seen"])).days >= 21:
            j["status"] = "likely_closed"
            j.setdefault("history", []).append({"date": today, "event": "likely_closed", "note": "not seen for 21+ days"})
        cats = set(j.get("categories", []))
        if j["status"] not in OPEN:
            cats.discard("urgent_apply")
        elif cd and 0 <= (cd - T).days <= 10:
            cats.add("urgent_apply")
        elif cd and (cd - T).days > 10 and j["id"] not in touched:
            cats.discard("urgent_apply")
        if "most_matched" not in cats and j.get("match_score", 0) >= 78 and j["status"] in OPEN:
            cats.add("most_matched")
        j["categories"] = sorted(cats)

    open_jobs = [j for j in jobs if j["status"] in ("active", "unknown")]
    cov = json.load(open(a.coverage)) if a.coverage else {}
    run = {
        "date": today, "run_type": "daily", "new": new, "seen_again": seen_again, "closed_today": closed_today,
        "active_by_region": {r: sum(1 for j in open_jobs if j["region"] == r) for r in REGIONS},
        "new_by_region": {r: sum(1 for j in jobs if j["region"] == r and j["first_seen"] == today) for r in REGIONS},
        "ai_related_share_active": round(sum(j["ai_related"] for j in open_jobs) / max(1, len(open_jobs)), 3),
        "coverage": cov, "notes": a.notes,
    }
    data["runs"] = [r for r in data["runs"] if r["date"] != today] + [run]
    data["meta"]["last_run"] = today

    # size policy
    text = json.dumps(data, indent=1, ensure_ascii=False)
    if len(text.encode()) > MAX_BYTES or len(jobs) > MAX_JOBS:
        keep, old = [], {}
        for j in jobs:
            if j["status"] in ("closed", "filled", "likely_closed") and (T - d(j["last_seen"])).days > ARCHIVE_AFTER_DAYS:
                old.setdefault(j["last_seen"][:4], []).append(j)
            else:
                keep.append(j)
        for yr, lst in old.items():
            path = os.path.join(ROOT, "data", "archive", f"jobs-{yr}.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            prev = json.load(open(path)) if os.path.exists(path) else []
            json.dump(prev + lst, open(path, "w"), indent=1, ensure_ascii=False)
            rel = f"data/archive/jobs-{yr}.json"
            if rel not in data["meta"]["archives"]:
                data["meta"]["archives"].append(rel)
        data["jobs"] = keep
        text = json.dumps(data, indent=1, ensure_ascii=False)

    open(DATA, "w").write(text)
    print(json.dumps({"new": new, "seen_again": seen_again, "closed_today": closed_today, "total": len(data["jobs"])}))

if __name__ == "__main__":
    main()
