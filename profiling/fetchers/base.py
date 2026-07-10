import json
import sys
import time
import urllib.request
from ..config import get_headers

def fetch_listing_archive(username, kind, limit, api_type):
    """
    api_type: 'pullpush' or 'arctic'
    """
    if api_type == "pullpush":
        endpoint = "submission" if kind == "submitted" else "comment"
        base_url = f"https://api.pullpush.io/reddit/search/{endpoint}/?author={username}&size=100"
        source_name = "pullpush"
    else:
        endpoint = "posts" if kind == "submitted" else "comments"
        base_url = f"https://arctic-shift.photon-reddit.com/api/{endpoint}/search?author={username}&limit=100"
        source_name = "arctic"
        
    items = []
    before = None
    headers = get_headers()
    retries = 3
    pause = 2
    
    while len(items) < limit:
        url = base_url
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
                print(f"  [{source_name.capitalize()}] Attempt {attempt} failed: {e}", file=sys.stderr)
                if attempt < retries:
                    time.sleep(pause * attempt)
                    
        if not data:
            print(f"  [{source_name.capitalize()}] Failed to fetch {url} after {retries} attempts.", file=sys.stderr)
            break
            
        children = data.get("data", [])
        if not children:
            break
            
        for child in children:
            if "created_utc" in child:
                try:
                    child["created_utc"] = int(child["created_utc"])
                except (ValueError, TypeError):
                    pass
            child["fetched_from"] = source_name
            items.append(child)
            
        valid_utcs = [c["created_utc"] for c in children if isinstance(c.get("created_utc"), int)]
        if not valid_utcs:
            break
            
        current_min_utc = min(valid_utcs)
        if before is not None and current_min_utc >= before:
            # Prevent infinite loop if API returns inclusive or duplicate results
            break
        before = current_min_utc
        
        print(f"  [{source_name.capitalize()}] {len(items)} fetched...")
        if len(children) < 100:
            break
            
        time.sleep(1.0)
        
    return items[:limit]
