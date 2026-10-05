import os
import re
import json

cache_dir = os.path.expanduser("~/Library/Caches/Google/Chrome/Default/Cache/Cache_Data")
recovered_dir = "/Users/elielkatche/job-tracker/data/recovered"
os.makedirs(recovered_dir, exist_ok=True)

applications_by_id = {}
cover_letters_by_app_id = {}
evaluations_by_app_id = {}
resumes_by_id = {}
offers_by_id = {}
raw_endpoints = {}

count = 0
with os.scandir(cache_dir) as entries:
    for entry in entries:
        if not entry.is_file():
            continue
        sz = entry.stat().st_size
        if sz < 100 or sz > 15_000_000:
            continue
        try:
            with open(entry.path, "rb") as f:
                data = f.read()
        except Exception:
            continue

        if b"localhost:8000" not in data and b"127.0.0.1:8000" not in data:
            continue

        count += 1
        # Extract URL
        match_url = re.search(rb"http://(?:localhost|127\.0\.0\.1):8000([^\s\x00\"<>]+)", data)
        if not match_url:
            continue
        url_path = match_url.group(1).decode("utf-8", errors="ignore")

        # Try to find JSON payload
        for s_char, e_char in [(b"[{", b"}]"), (b"{\"", b"}")]:
            s_idx = data.find(s_char)
            if s_idx != -1:
                e_idx = data.rfind(e_char) + len(e_char)
                if e_idx > s_idx:
                    try:
                        payload = data[s_idx:e_idx].decode("utf-8")
                        parsed = json.loads(payload)
                    except Exception:
                        continue

                    if url_path in ("/applications/", "/applications"):
                        if isinstance(parsed, list):
                            for app in parsed:
                                if isinstance(app, dict) and "_id" in app:
                                    aid = str(app["_id"])
                                    applications_by_id[aid] = app
                    elif "/cover-letter" in url_path:
                        # Could be /applications/{id}/cover-letter or /cover-letters/{id}
                        app_match = re.search(r"/applications/([a-f0-9]{24})/cover-letter", url_path)
                        if app_match:
                            app_id = app_match.group(1)
                            if isinstance(parsed, dict):
                                cover_letters_by_app_id[app_id] = parsed
                        elif isinstance(parsed, dict) and "application_id" in parsed:
                            cover_letters_by_app_id[str(parsed["application_id"])] = parsed
                    elif "/evaluation" in url_path:
                        app_match = re.search(r"/applications/([a-f0-9]{24})/evaluation", url_path)
                        if app_match:
                            app_id = app_match.group(1)
                            if isinstance(parsed, dict) and parsed is not None:
                                evaluations_by_app_id[app_id] = parsed
                    elif "/resumes" in url_path:
                        if isinstance(parsed, list):
                            for r in parsed:
                                if isinstance(r, dict) and "_id" in r:
                                    resumes_by_id[str(r["_id"])] = r
                        elif isinstance(parsed, dict) and "_id" in parsed:
                            resumes_by_id[str(parsed["_id"])] = parsed
                    elif "/offers" in url_path:
                        if isinstance(parsed, list):
                            for o in parsed:
                                if isinstance(o, dict) and "_id" in o:
                                    offers_by_id[str(o["_id"])] = o
                        elif isinstance(parsed, dict) and "_id" in parsed:
                            offers_by_id[str(parsed["_id"])] = parsed

out_data = {
    "applications": list(applications_by_id.values()),
    "cover_letters": cover_letters_by_app_id,
    "evaluations": evaluations_by_app_id,
    "resumes": list(resumes_by_id.values()),
    "offers": list(offers_by_id.values())
}

output_path = os.path.join(recovered_dir, "consolidated_data.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(out_data, f, indent=2, ensure_ascii=False)

print(f"Extraction consolidation terminee:")
print(f"- Fichiers examines: {count}")
print(f"- Applications: {len(out_data['applications'])}")
print(f"- Cover Letters: {len(out_data['cover_letters'])}")
print(f"- Evaluations: {len(out_data['evaluations'])}")
print(f"- Resumes: {len(out_data['resumes'])}")
print(f"- Offers: {len(out_data['offers'])}")
print(f"- Sauvegarde: {output_path}")
