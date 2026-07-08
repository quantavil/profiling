import statistics
from collections import Counter
from .config import STOPWORDS, WORD_RE
from .utils import is_deleted_or_removed, _hour_weekday

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


def analyse(about, posts, comments):
    for p in posts:
        p["_is_deleted"] = is_deleted_or_removed(p)
    for c in comments:
        c["_is_deleted"] = is_deleted_or_removed(c)

    valid_posts = posts
    valid_comments = comments
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
        "valid_posts": sum(1 for p in posts if not p["_is_deleted"]),
        "valid_comments": sum(1 for c in comments if not c["_is_deleted"]),
        "valid_total": sum(1 for i in all_valid_items if not i["_is_deleted"]),
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

    # --- timezone estimate ---
    prof["tz_estimate_posts"] = estimate_tz(prof["hour_totals_posts"])
    prof["tz_estimate_comments"] = estimate_tz(prof["hour_totals_comments"])
    prof["tz_estimate_combined"] = estimate_tz(prof["hour_totals_combined"])

    # --- interest keywords from user's own text ---
    def get_word_counter(posts_list, comments_list):
        words = Counter()
        for p in posts_list:
            if p.get("_is_deleted"):
                continue
            for field in ("title", "selftext"):
                for m in WORD_RE.findall((p.get(field) or "").lower()):
                    if m not in STOPWORDS:
                        words[m] += 1
        for c in comments_list:
            if c.get("_is_deleted"):
                continue
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
