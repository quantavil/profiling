from ..utils import _get_fullname
from .old_reddit import fetch_listing_old_reddit
from .pullpush import fetch_listing_pullpush
from .arctic_shift import fetch_listing_arctic_shift

def fetch_listing(username, kind, limit=1000, source="all"):
    """kind: 'submitted' or 'comments'."""
    items = []
    
    # Fetch Candidate items from each requested source
    if source in ("all", "reddit"):
        print(f"Fetching {kind} from old.reddit.com...")
        scraped_items = fetch_listing_old_reddit(username, kind, limit)
        if scraped_items:
            items.extend(scraped_items)
            
    if source in ("all", "pullpush"):
        print(f"Fetching {kind} from Pullpush API...")
        pullpush_items = fetch_listing_pullpush(username, kind, limit)
        if pullpush_items:
            existing_names = {_get_fullname(i, kind) for i in items if _get_fullname(i, kind)}
            for item in pullpush_items:
                name = _get_fullname(item, kind)
                if name and name not in existing_names:
                    items.append(item)
                    existing_names.add(name)

    if source in ("all", "arctic"):
        print(f"Fetching {kind} from Arctic Shift API...")
        arctic_items = fetch_listing_arctic_shift(username, kind, limit)
        if arctic_items:
            existing_names = {_get_fullname(i, kind) for i in items if _get_fullname(i, kind)}
            for item in arctic_items:
                name = _get_fullname(item, kind)
                if name and name not in existing_names:
                    items.append(item)
                    existing_names.add(name)
            
    # Chronological sort (newest first) based on float representation of created_utc
    def get_created_utc(item):
        cu = item.get("created_utc")
        if cu is None:
            return 0
        try:
            return float(cu)
        except (ValueError, TypeError):
            return 0

    items.sort(key=get_created_utc, reverse=True)
    return items[:limit]
