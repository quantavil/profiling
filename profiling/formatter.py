from datetime import datetime, timezone
from .config import WEEKDAYS
from .utils import escape_markdown

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
        if prof.get("active_span_days", 0) > 0:
            L.append(f"- Active span: {prof['active_span_days']} days "
                     f"({prof['items_per_day']} items/day)")
        else:
            L.append(f"- Active span: <1 day (all items share the same timestamp)")
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
            deleted_tag = " [DELETED/REMOVED]" if p.get("_is_deleted") else ""
            
            source = p.get("fetched_from")
            source_str = f" | **Source**: {source}" if source else ""
            
            L.append(f"### {idx+1}. {escape_markdown(title)}{deleted_tag}\n")
            L.append(f"- **Date**: {p_date} | **Subreddit**: r/{sub} | **Score**: {score}{source_str} {link_str}")
            if selftext:
                indented_text = "\n".join(f"  > {escape_markdown(line)}" for line in selftext.splitlines())
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
            deleted_tag = " [DELETED/REMOVED]" if c.get("_is_deleted") else ""
            
            source = c.get("fetched_from")
            source_str = f" | **Source**: {source}" if source else ""
            
            L.append(f"### {idx+1}. Comment in r/{sub}{deleted_tag}\n")
            L.append(f"- **Date**: {c_date} | **Score**: {score}{source_str} {link_str}")
            if body:
                indented_body = "\n".join(f"  > {escape_markdown(line)}" for line in body.splitlines())
                L.append(f"\n{indented_body}\n")
            else:
                L.append("")
        L.append("")

    L.append("---")
    L.append("_All data above is public and self-authored by the account. "
             "No off-platform correlation performed._")
    return "\n".join(L)
