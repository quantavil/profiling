import argparse
import json
import re
import sys
from pathlib import Path

from .config import HEADERS
from .fetchers.old_reddit import fetch_about
from .fetchers import fetch_listing
from .analyzer import analyse
from .formatter import render_markdown

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


def main():
    p = argparse.ArgumentParser(description="Analyse a Reddit user's public activity.")
    p.add_argument("username", nargs="?", help="Reddit username (omit if using --infile)")
    p.add_argument("--infile", help="Analyse an existing scraper JSON dump instead of fetching")
    p.add_argument("--limit", type=int, default=1000, help="Max items per type when fetching")
    p.add_argument("--outdir", default="output", help="Output directory")
    p.add_argument("--source", choices=["reddit", "arctic", "pullpush", "all"], default="all", 
                   help="Data source: 'reddit' (standard old.reddit scraping), 'arctic' (Arctic Shift API), 'pullpush' (Pullpush API), or 'all' (merge all)")
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
            
        about = fetch_about(username) if username else None
    else:
        if not args.username:
            p.error("provide a username or --infile")
        username = args.username.strip().lstrip("u/")
        
    # Username regex validation (guards against path traversal)
    if not re.match(r"^[A-Za-z0-9_-]{3,20}$", username):
        print(f"Error: Invalid or unsafe username '{username}'. Usernames must be 3-20 characters long and contain only letters, numbers, underscores, or hyphens.", file=sys.stderr)
        sys.exit(1)

    if not args.infile:
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
