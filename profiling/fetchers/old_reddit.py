import sys
import time
from datetime import datetime
from ..utils import parse_reddit_score

def _fetch_url_with_retry(url, label="old.reddit", retries=3, pause=2):
    try:
        from scrapling.fetchers import StealthyFetcher
    except ImportError:
        print(f"  scrapling is not installed. Fetch for {url} skipped.", file=sys.stderr)
        return None
        
    for attempt in range(1, retries + 1):
        try:
            r = StealthyFetcher.fetch(url)
            if r.status == 200:
                return r
            print(f"  [{label}] fetch attempt {attempt} failed: Status {r.status}", file=sys.stderr)
            time.sleep(pause * attempt)
        except Exception as e:
            print(f"  [{label}] fetch attempt {attempt} failed with error: {e}", file=sys.stderr)
            time.sleep(pause * attempt)
    return None


def fetch_about(username):
    try:
        url = f"https://old.reddit.com/user/{username}/"
        r = _fetch_url_with_retry(url, "old.reddit fetch_about")
        if not r:
            return None
        
        # parse created_utc
        dt_str = r.css('.side time::attr(datetime)').get()
        created_utc = None
        if dt_str:
            try:
                created_utc = int(datetime.fromisoformat(dt_str).timestamp())
            except Exception as e:
                print(f"  Warning: Failed to parse datetime '{dt_str}': {e}", file=sys.stderr)
        
        # parse link_karma & comment_karma
        karma_spans = r.css('.side span.karma')
        link_karma = 0
        comment_karma = 0
        for span in karma_spans:
            klass = span.attrib.get('class', '')
            text = span.css('::text').get()
            if not text:
                continue
            try:
                val = int(text.replace(',', '').strip())
                if 'comment-karma' in klass:
                    comment_karma = val
                else:
                    link_karma = val
            except Exception:
                pass
                
        # is_mod
        side_text = "".join(r.css('.side').getall())
        is_mod = "MODERATOR OF" in side_text
        
        return {
            "name": username,
            "created_utc": created_utc,
            "link_karma": link_karma,
            "comment_karma": comment_karma,
            "total_karma": link_karma + comment_karma,
            "is_mod": is_mod,
        }
    except Exception as e:
        print(f"  Fetch_about failed: {e}", file=sys.stderr)
        return None


def fetch_listing_old_reddit(username, kind, limit=1000):
    endpoint = "submitted" if kind == "submitted" else "comments"
    url = f"https://old.reddit.com/user/{username}/{endpoint}/"
    items = []
    
    while len(items) < limit:
        r = _fetch_url_with_retry(url, "old.reddit fetch_listing")
        if not r:
            print(f"  [old.reddit] Failed to fetch {url}", file=sys.stderr)
            break
            
        things = r.css(".thing")
        if not things:
            break
            
        for thing in things:
            fullname = thing.attrib.get("data-fullname")
            subreddit = thing.attrib.get("data-subreddit")
            permalink = thing.attrib.get("data-permalink", "")
            
            # created_utc
            dt_str = thing.css("time::attr(datetime)").get()
            created_utc = None
            if dt_str:
                try:
                    created_utc = int(datetime.fromisoformat(dt_str).timestamp())
                except Exception as e:
                    print(f"  Warning: Failed to parse datetime '{dt_str}': {e}", file=sys.stderr)
            
            # score
            score_text = thing.css(".score.unvoted::text").get()
            if not score_text:
                score_text = thing.css(".score::text").get()
            score = parse_reddit_score(score_text)
            
            item = {
                "name": fullname,
                "created_utc": created_utc,
                "subreddit": subreddit,
                "score": score,
                "permalink": permalink,
                "fetched_from": "reddit",
            }
            
            if kind == "comments":
                body_el = thing.css(".usertext-body")
                body = body_el[0].get_all_text() if body_el else ""
                item["body"] = body
            else:
                title = thing.css("a.title::text").get()
                item["title"] = title
                body_el = thing.css(".usertext-body")
                selftext = body_el[0].get_all_text() if body_el else ""
                item["selftext"] = selftext
                
            items.append(item)
            
        next_btn = r.css(".next-button a::attr(href)").get()
        if not next_btn:
            break
        url = next_btn
        time.sleep(1.2)
        
    return items[:limit]
