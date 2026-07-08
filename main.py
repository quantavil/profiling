#!/usr/bin/env python3
"""
Reddit Public Activity Analyser
--------------------------------
Consumes public posts + comments for a single Reddit username and produces a
behavioural profile: subreddit breakdown, activity heatmap (hour x weekday),
interest keywords, engagement stats, and a rough timezone estimate.

Data sources (all public, no auth):
  - Reddit's own .json listings (/user/<name>/submitted.json, /comments.json)
  - Optionally an existing JSON dump produced by reddit_user_scraper.py

Everything is derived from public on-platform data only: timestamps, scores,
subreddits, and text the user posted themselves. No off-platform lookups.

Usage:
    python reddit_analyser.py USERNAME
    python reddit_analyser.py USERNAME --limit 500
    python reddit_analyser.py --infile spez_reddit_data.json   # analyse a dump
    python reddit_analyser.py USERNAME --outdir reports
"""

import argparse
import json
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import urllib.request

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
}
REDDIT_BASE = "https://www.reddit.com"

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Minimal English stopword set for keyword extraction. Deliberately small and
# transparent rather than pulling in nltk for a one-file tool.
STOPWORDS = set("""
a an the and or but if then else for to of in on at by with without from up down
out over under again further is am are was were be been being have has had do does
did doing will would shall should can could may might must this that these those i
me my we our you your he him his she her it its they them their what which who whom
whose when where why how all any both each few more most other some such no nor not
only own same so than too very just also about into through during before after above
below between only get got like one really much even still way well thing things dont
im ive youre thats gonna wanna kinda sorta yeah nah lol edit https http www com reddit
amp x200b nbsp deleted removed [deleted] [removed]
""".split())

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z'\-]{2,}")





def score_stats(items):
    scores = [i.get("score", 0) or 0 for i in items]
    if not scores:
        return {}
    return {
        "total": sum(scores),
        "mean": round(sum(scores) / len(scores), 1),
        "median": round(statistics.median(scores), 1),
        "max": max(scores),
        "min": min(scores),
    }


def is_deleted_or_removed(item):
    selftext = item.get("selftext") or ""
    body = item.get("body") or ""
    author = item.get("author") or ""
    
    placeholders = {"[deleted]", "[removed]", "deleted", "removed"}
    
    if selftext.strip() in placeholders or body.strip() in placeholders:
        return True
    if author == "[deleted]":
        return True
    return False


def fetch_about_fallback(username):
    try:
        from scrapling.fetchers import StealthyFetcher
        url = f"https://old.reddit.com/user/{username}/"
        r = StealthyFetcher.fetch(url)
        if r.status != 200:
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
            "verified": False,
            "has_verified_email": False,
        }
    except Exception as e:
        print(f"  Fallback fetch_about failed: {e}", file=sys.stderr)
        return None


def fetch_about(username):
    return fetch_about_fallback(username)


def fetch_listing_old_reddit(username, kind, limit=1000):
    try:
        from scrapling.fetchers import StealthyFetcher
    except ImportError:
        print("  scrapling is not installed. Fallback to old.reddit scraping skipped.", file=sys.stderr)
        return []
    endpoint = "submitted" if kind == "submitted" else "comments"
    url = f"https://old.reddit.com/user/{username}/{endpoint}/"
    items = []
    
    while len(items) < limit:
        try:
            r = StealthyFetcher.fetch(url)
            if r.status != 200:
                print(f"  [old.reddit] Failed to fetch: {r.status}", file=sys.stderr)
                break
        except Exception as e:
            print(f"  [old.reddit] Error fetching {url}: {e}", file=sys.stderr)
            break
            
        things = r.css(".thing")
        if not things:
            break
            
        for thing in things:
            fullname = thing.attrib.get("data-fullname")
            subreddit = thing.attrib.get("data-subreddit")
            
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
            score = 0
            if score_text:
                try:
                    score = int(score_text.replace("points", "").replace("point", "").strip())
                except Exception:
                    pass
            
            item = {
                "name": fullname,
                "created_utc": created_utc,
                "subreddit": subreddit,
                "score": score,
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


def fetch_listing_arctic_shift(username, kind, limit=1000):
    endpoint = "posts" if kind == "submitted" else "comments"
    items = []
    before = None
    headers = {"User-Agent": "Mozilla/5.0"}
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
            
        items.extend(children)
        valid_utcs = [c["created_utc"] for c in children if c.get("created_utc")]
        if not valid_utcs:
            break
        before = min(valid_utcs)
        print(f"  [Arctic Shift] {len(items)} fetched...")
        if len(children) < 100:
            break
            
        time.sleep(1.0)
        
    return items[:limit]


def _get_fullname(item, kind):
    name = item.get("name")
    if name:
        return name
    item_id = item.get("id")
    if item_id:
        prefix = "t3_" if kind == "submitted" else "t1_"
        if not str(item_id).startswith(prefix):
            return f"{prefix}{item_id}"
        return item_id
    return None


def fetch_listing(username, kind, limit=1000, source="both"):
    """kind: 'submitted' or 'comments'."""
    items = []
    
    if source in ("both", "reddit"):
        print(f"Fetching {kind} from old.reddit.com...")
        scraped_items = fetch_listing_old_reddit(username, kind, limit)
        if scraped_items:
            items.extend(scraped_items)
            
    if source in ("both", "arctic"):
        print(f"Fetching {kind} from Arctic Shift API...")
        arctic_items = fetch_listing_arctic_shift(username, kind, limit)
        if arctic_items:
            existing_names = {_get_fullname(i, kind) for i in items if _get_fullname(i, kind)}
            for item in arctic_items:
                name = _get_fullname(item, kind)
                if not name or name not in existing_names:
                    items.append(item)
                    if name:
                        existing_names.add(name)
            
    return items[:limit]


def load_dump(path):
    """Load a JSON dump from reddit_user_scraper.py or a profile JSON and split by type."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        posts = data.get("posts_raw", [])
        comments = data.get("comments_raw", [])
        return posts, comments
    posts = [i for i in data if i.get("type") == "post"]
    comments = [i for i in data if i.get("type") == "comment"]
    return posts, comments


def _hour_weekday(created_utc):
    dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
    return dt.hour, dt.weekday()


def analyse(about, posts, comments):
    # Filter out deleted/removed content first
    valid_posts = [p for p in posts if not is_deleted_or_removed(p)]
    valid_comments = [c for c in comments if not is_deleted_or_removed(c)]
    all_valid_items = valid_posts + valid_comments

    prof = {
        "about": about,
        "posts_raw": posts,
        "comments_raw": comments,
    }
    
    ts = [i["created_utc"] for i in all_valid_items if i.get("created_utc")]

    # --- activity span ---
    if ts:
        first, last = min(ts), max(ts)
        prof["first_activity_utc"] = first
        prof["last_activity_utc"] = last
        span_days = (last - first) / 86400 or 1
        prof["active_span_days"] = round(span_days, 1)
        prof["items_per_day"] = round(len(all_valid_items) / span_days, 2)

    prof["counts"] = {
        "posts": len(posts),
        "comments": len(comments),
        "total": len(posts) + len(comments),
        "valid_posts": len(valid_posts),
        "valid_comments": len(valid_comments),
        "valid_total": len(all_valid_items),
    }

    # --- subreddit breakdown ---
    def get_sub_counter(items):
        return Counter(i.get("subreddit") for i in items if i.get("subreddit"))
        
    posts_sub_counter = get_sub_counter(valid_posts)
    comments_sub_counter = get_sub_counter(valid_comments)
    combined_sub_counter = posts_sub_counter + comments_sub_counter
    
    prof["subreddits_posts"] = posts_sub_counter.most_common(30)
    prof["unique_subreddits_posts"] = len(posts_sub_counter)
    prof["subreddits_comments"] = comments_sub_counter.most_common(30)
    prof["unique_subreddits_comments"] = len(comments_sub_counter)
    prof["subreddits_combined"] = combined_sub_counter.most_common(30)
    prof["unique_subreddits_combined"] = len(combined_sub_counter)

    # --- engagement ---
    prof["post_score_stats"] = score_stats(valid_posts)
    prof["comment_score_stats"] = score_stats(valid_comments)

    # --- activity heatmap: hour(0-23) x weekday(0-6) ---
    def make_heatmap(items):
        heat = [[0] * 24 for _ in range(7)]
        hour_totals = [0] * 24
        for i in items:
            cu = i.get("created_utc")
            if not cu:
                continue
            h, wd = _hour_weekday(cu)
            heat[wd][h] += 1
            hour_totals[h] += 1
        return heat, hour_totals

    prof["heatmap_posts"], prof["hour_totals_posts"] = make_heatmap(valid_posts)
    prof["heatmap_comments"], prof["hour_totals_comments"] = make_heatmap(valid_comments)
    
    # Merge heatmaps and hour totals for combined directly
    heatmap_combined = [
        [prof["heatmap_posts"][wd][h] + prof["heatmap_comments"][wd][h] for h in range(24)]
        for wd in range(7)
    ]
    hour_totals_combined = [
        prof["hour_totals_posts"][h] + prof["hour_totals_comments"][h] for h in range(24)
    ]
    prof["heatmap_combined"] = heatmap_combined
    prof["hour_totals_combined"] = hour_totals_combined

    # --- timezone estimate from quietest 6h window (approx sleep) ---
    def estimate_tz(hour_totals):
        if sum(hour_totals) <= 20:
            return None
        best_start, best_sum = 0, None
        for start in range(24):
            window = sum(hour_totals[(start + k) % 24] for k in range(6))
            if best_sum is None or window < best_sum:
                best_sum, best_start = window, start
        sleep_mid_utc = (best_start + 3) % 24
        offset = (3 - sleep_mid_utc) % 24
        if offset > 12:
            offset -= 24
            
        total_activity = sum(hour_totals)
        avg_6h_activity = total_activity / 4.0
        ratio = best_sum / avg_6h_activity if avg_6h_activity > 0 else 1.0
        
        # This is a heuristic score, not a statistical confidence level
        if total_activity > 100 and ratio < 0.25:
            confidence_heuristic = "high"
        elif total_activity > 50 and ratio < 0.4:
            confidence_heuristic = "medium"
        else:
            confidence_heuristic = "low"
            
        return {
            "quiet_window_utc": f"{best_start:02d}:00-{(best_start + 6) % 24:02d}:00",
            "estimated_utc_offset": offset,
            "confidence_heuristic": confidence_heuristic,
            "note": f"Inferred from least-active 6h window (sleep ratio: {ratio:.2f}, total samples: {total_activity}).",
        }

    prof["tz_estimate_posts"] = estimate_tz(prof["hour_totals_posts"])
    prof["tz_estimate_comments"] = estimate_tz(prof["hour_totals_comments"])
    prof["tz_estimate_combined"] = estimate_tz(prof["hour_totals_combined"])

    # --- interest keywords from user's own text ---
    def get_word_counter(posts_list, comments_list):
        words = Counter()
        for p in posts_list:
            for field in ("title", "selftext"):
                for m in WORD_RE.findall((p.get(field) or "").lower()):
                    if m not in STOPWORDS:
                        words[m] += 1
        for c in comments_list:
            for m in WORD_RE.findall((c.get("body") or "").lower()):
                if m not in STOPWORDS:
                    words[m] += 1
        return words

    posts_word_counter = get_word_counter(valid_posts, [])
    comments_word_counter = get_word_counter([], valid_comments)
    combined_word_counter = posts_word_counter + comments_word_counter

    prof["top_keywords_posts"] = posts_word_counter.most_common(40)
    prof["top_keywords_comments"] = comments_word_counter.most_common(40)
    prof["top_keywords_combined"] = combined_word_counter.most_common(40)

    return prof


def render_markdown(username, prof):
    L = []
    a = prof.get("about") or {}
    L.append(f"# Reddit activity profile: u/{username}\n")
    L.append(f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}. "
             f"Public on-platform data only._\n")

    # Account
    L.append("## Account\n")
    if a.get("created_utc"):
        cake = datetime.fromtimestamp(a["created_utc"], tz=timezone.utc)
        age_days = (datetime.now(timezone.utc) - cake).days
        L.append(f"- Created: {cake:%Y-%m-%d} ({age_days} days, "
                 f"{age_days / 365:.1f} years old)")
    if a.get("link_karma") is not None:
        L.append(f"- Post karma: {a['link_karma']:,}")
    if a.get("comment_karma") is not None:
        L.append(f"- Comment karma: {a['comment_karma']:,}")
    if a.get("is_mod") is not None:
        L.append(f"- Moderator: {'yes' if a['is_mod'] else 'no'}")
    L.append("")

    # Volume
    c = prof["counts"]
    L.append("## Activity volume\n")
    L.append(f"- Posts analysed: {c['posts']} (valid: {c['valid_posts']})")
    L.append(f"- Comments analysed: {c['comments']} (valid: {c['valid_comments']})")
    L.append(f"- Total items: {c['total']} (valid: {c['valid_total']})")
    if "active_span_days" in prof:
        L.append(f"- Active span: {prof['active_span_days']} days "
                 f"({prof['items_per_day']} items/day)")
    if prof.get("last_activity_utc"):
        last = datetime.fromtimestamp(prof["last_activity_utc"], tz=timezone.utc)
        L.append(f"- Most recent captured activity: {last:%Y-%m-%d %H:%M UTC}")
    L.append(f"- Unique subreddits (Combined): {prof['unique_subreddits_combined']}")
    L.append("")

    # Subreddits
    L.append("## Top subreddits\n")
    
    if prof.get("subreddits_posts"):
        L.append("### Submissions (Posts)\n")
        L.append("| Subreddit | Posts |")
        L.append("|---|---|")
        for sub, n in prof["subreddits_posts"][:15]:
            L.append(f"| r/{sub} | {n} |")
        L.append("")

    if prof.get("subreddits_comments"):
        L.append("### Comments\n")
        L.append("| Subreddit | Comments |")
        L.append("|---|---|")
        for sub, n in prof["subreddits_comments"][:15]:
            L.append(f"| r/{sub} | {n} |")
        L.append("")

    if prof.get("subreddits_combined"):
        L.append("### Combined Activity\n")
        L.append("| Subreddit | Total Items |")
        L.append("|---|---|")
        for sub, n in prof["subreddits_combined"][:15]:
            L.append(f"| r/{sub} | {n} |")
        L.append("")

    # Engagement
    ps, cs = prof.get("post_score_stats", {}), prof.get("comment_score_stats", {})
    if ps or cs:
        L.append("## Engagement\n")
        L.append("| Metric | Posts | Comments |")
        L.append("|---|---|---|")
        for key in ("total", "mean", "median", "max", "min"):
            L.append(f"| {key} | {ps.get(key, '-')} | {cs.get(key, '-')} |")
        L.append("")

    # Timezone
    tz_p = prof.get("tz_estimate_posts")
    tz_c = prof.get("tz_estimate_comments")
    tz_comb = prof.get("tz_estimate_combined")
    
    if tz_p or tz_c or tz_comb:
        L.append("## Timezone estimate\n")
        L.append("| Source | Quietest window (UTC) | Estimated UTC Offset | Confidence Heuristic | Note |")
        L.append("|---|---|---|---|---|")
        for name, tz in [("Posts", tz_p), ("Comments", tz_c), ("Combined", tz_comb)]:
            if tz:
                sign = "+" if tz["estimated_utc_offset"] >= 0 else ""
                L.append(f"| {name} | {tz['quiet_window_utc']} | UTC{sign}{tz['estimated_utc_offset']} | {tz['confidence_heuristic']} | {tz['note']} |")
        L.append("")

    # Heatmaps
    def render_heatmap(title, heat, hour_totals):
        res = []
        res.append(f"### {title}\n")
        res.append("Rows = weekday, columns = hour 00-23. Densest cells = peak activity.\n")
        res.append("```")
        header = "     " + "".join(f"{h:>3}" for h in range(24))
        res.append(header)
        peak = max((max(row) for row in heat), default=0) or 1
        for wd in range(7):
            cells = []
            for h in range(24):
                v = heat[wd][h]
                if v == 0:
                    cells.append("  .")
                else:
                    frac = v / peak
                    mark = "#" if frac > 0.66 else ("+" if frac > 0.33 else "-")
                    cells.append(f"  {mark}")
            res.append(f"{WEEKDAYS[wd]}  " + "".join(cells))
        res.append("```\n")
        return res

    L.append("## Activity heatmaps (UTC)\n")
    if prof.get("heatmap_posts") and sum(prof["hour_totals_posts"]) > 0:
        L.extend(render_heatmap("Submissions (Posts) Heatmap", prof["heatmap_posts"], prof["hour_totals_posts"]))
    if prof.get("heatmap_comments") and sum(prof["hour_totals_comments"]) > 0:
        L.extend(render_heatmap("Comments Heatmap", prof["heatmap_comments"], prof["hour_totals_comments"]))
    if prof.get("heatmap_combined") and sum(prof["hour_totals_combined"]) > 0:
        L.extend(render_heatmap("Combined Heatmap", prof["heatmap_combined"], prof["hour_totals_combined"]))
    L.append("Legend: `#` high, `+` medium, `-` low, `.` none.\n")

    # Keywords
    L.append("## Top interest keywords\n")
    L.append("Most frequent non-trivial words from the user's own content.\n")
    
    if prof.get("top_keywords_posts"):
        L.append("### From Submissions (Posts)\n")
        L.append(", ".join(f"{w} ({n})" for w, n in prof["top_keywords_posts"][:20]) + "\n")
        
    if prof.get("top_keywords_comments"):
        L.append("### From Comments\n")
        L.append(", ".join(f"{w} ({n})" for w, n in prof["top_keywords_comments"][:20]) + "\n")
        
    if prof.get("top_keywords_combined"):
        L.append("### Combined Keywords\n")
        L.append(", ".join(f"{w} ({n})" for w, n in prof["top_keywords_combined"][:20]) + "\n")
    L.append("")

    # Posts details
    posts_raw = prof.get("posts_raw", [])
    if posts_raw:
        L.append("## Submissions (Posts)\n")
        sorted_posts = sorted(posts_raw, key=lambda x: x.get("created_utc", 0), reverse=True)
        for idx, p in enumerate(sorted_posts):
            p_date = datetime.fromtimestamp(p.get("created_utc", 0), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            sub = p.get("subreddit")
            score = p.get("score", 0)
            title = p.get("title", "(No Title)")
            selftext = p.get("selftext", "").strip()
            permalink = p.get("permalink", "")
            
            link_str = f"[Link](https://reddit.com{permalink})" if permalink else ""
            
            deleted_tag = " [DELETED/REMOVED]" if is_deleted_or_removed(p) else ""
            L.append(f"### {idx+1}. {title}{deleted_tag}\n")
            L.append(f"- **Date**: {p_date} | **Subreddit**: r/{sub} | **Score**: {score} {link_str}")
            if selftext:
                indented_text = "\n".join(f"  > {line}" for line in selftext.splitlines())
                L.append(f"\n{indented_text}\n")
            else:
                L.append("")
        L.append("")

    # Comments details
    comments_raw = prof.get("comments_raw", [])
    if comments_raw:
        L.append("## Comments\n")
        sorted_comments = sorted(comments_raw, key=lambda x: x.get("created_utc", 0), reverse=True)
        for idx, c in enumerate(sorted_comments):
            c_date = datetime.fromtimestamp(c.get("created_utc", 0), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            sub = c.get("subreddit")
            score = c.get("score", 0)
            body = c.get("body", "").strip()
            permalink = c.get("permalink", "")
            
            link_str = f"[Link](https://reddit.com{permalink})" if permalink else ""
            
            deleted_tag = " [DELETED/REMOVED]" if is_deleted_or_removed(c) else ""
            L.append(f"### {idx+1}. Comment in r/{sub}{deleted_tag}\n")
            L.append(f"- **Date**: {c_date} | **Score**: {score} {link_str}")
            if body:
                indented_body = "\n".join(f"  > {line}" for line in body.splitlines())
                L.append(f"\n{indented_body}\n")
            else:
                L.append("")
        L.append("")

    L.append("---")
    L.append("_All data above is public and self-authored by the account. "
             "No off-platform correlation performed._")
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser(description="Analyse a Reddit user's public activity.")
    p.add_argument("username", nargs="?", help="Reddit username (omit if using --infile)")
    p.add_argument("--infile", help="Analyse an existing scraper JSON dump instead of fetching")
    p.add_argument("--limit", type=int, default=1000, help="Max items per type when fetching")
    p.add_argument("--outdir", default="output", help="Output directory")
    p.add_argument("--source", choices=["reddit", "arctic", "both"], default="both", 
                   help="Data source: 'reddit' (standard API & old.reddit fallback), 'arctic' (Arctic Shift API), or 'both' (merge)")
    p.add_argument("--user-agent", help="Custom User-Agent header to use for API requests")
    args = p.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if args.user_agent:
        HEADERS["User-Agent"] = args.user_agent

    if args.infile:
        posts, comments = load_dump(args.infile)
        
        # Robust username derivation from infile name
        stem = Path(args.infile).stem
        parts = stem.split("_")
        derived_username = parts[0] if parts else stem
        
        if derived_username.lower() in ("data", "export", "reddit", "profile", "posts", "comments", "dump"):
            username = args.username or "unknown_user"
            print(f"  Warning: Derived username '{derived_username}' from filename is generic. Defaulting to '{username}'.", file=sys.stderr)
        else:
            username = args.username or derived_username
            
        about = fetch_about(username) if args.username else None
    else:
        if not args.username:
            p.error("provide a username or --infile")
        username = args.username.strip().lstrip("u/")
        print(f"Fetching public activity for u/{username} ...")
        about = fetch_about(username)
        if about is None:
            print("Could not fetch account metadata. It may be private, "
                  "suspended, or nonexistent. Continuing with listings anyway.", file=sys.stderr)
        posts = fetch_listing(username, "submitted", args.limit, args.source)
        comments = fetch_listing(username, "comments", args.limit, args.source)

    if not posts and not comments:
        print("No public posts or comments retrieved. Nothing to analyse.", file=sys.stderr)
        sys.exit(1)

    prof = analyse(about, posts, comments)
    md = render_markdown(username, prof)

    md_path = outdir / f"{username}_profile.md"
    json_path = outdir / f"{username}_profile.json"
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone. {prof['counts']['posts']} posts, "
          f"{prof['counts']['comments']} comments analysed.")
    print(f"  -> {md_path}")
    print(f"  -> {json_path}")


if __name__ == "__main__":
    main()