import json
import sys
import time
import urllib.request
from ..config import HEADERS

def fetch_listing_arctic_shift(username, kind, limit=1000):
    endpoint = "posts" if kind == "submitted" else "comments"
    items = []
    before = None
    headers = HEADERS
    retries = 3
    pause = 2
    
    while len(items) < limit:
        url = f"https://arctic-shift.photon-reddit.com/api/{endpoint}/search?author={username}&limit=100"
        if before:
            url += f"&before={before}"
            
        data = None
        for attempt in range(1, retries + 1):
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    break
            except Exception as e:
                print(f"  [Arctic Shift] Attempt {attempt} failed: {e}", file=sys.stderr)
                if attempt < retries:
                    time.sleep(pause * attempt)
                    
        if not data:
            print(f"  [Arctic Shift] Failed to fetch {url} after {retries} attempts.", file=sys.stderr)
            break
            
        children = data.get("data", [])
        if not children:
            break
            
        for child in children:
            child["fetched_from"] = "arctic"
            items.append(child)
            
        valid_utcs = [c["created_utc"] for c in children if c.get("created_utc")]
        if not valid_utcs:
            break
        before = min(valid_utcs)
        print(f"  [Arctic Shift] {len(items)} fetched...")
        if len(children) < 100:
            break
            
        time.sleep(1.0)
        
    return items[:limit]
