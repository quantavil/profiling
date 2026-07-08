# Project: Reddit Public Activity Analyser

## Overview
A single-file Python script (`main.py`) that analyzes public posts and comments for a given Reddit username and produces a behavioral profile, including subreddits breakdown, activity heatmaps, interest keywords, and timezone estimate.

## Structure
/home/quantavil/Documents/Project/profiling/
└── main.py          # Entry point and the entire logic for scraping and analyzing Reddit profiles.

## Conventions
- Single file script using `urllib.request` to avoid third-party requests/BeautifulSoup.
- Clean parsing and simple statistics.

## Dependencies & Setup
- Requires Python >= 3.14, managed with `uv`.
- Added `scrapling` (stealthy fetching) dependency for old.reddit HTML parsing fallback.

## Critical Information
- Standard Reddit API endpoints (`.json`) return 403 Forbidden programmatically and have been completely removed from the script to avoid slow 403 retries.
- Primary Source: `scrapling` is used directly to scrape `old.reddit.com` HTML for user metadata and listing contents.
- Historical Source: Arctic Shift API (`https://arctic-shift.photon-reddit.com/api/`) is queried to gather history, including deleted posts/comments.

## Insights
- Arctic Shift API provides access to historical and deleted Reddit content.
- Merging Reddit scraping and Arctic Shift API data provides a complete view of a user's footprint.
- Post and comment activity metrics (subreddits, heatmaps, keyword frequencies, sleep/timezone estimates) are analyzed and rendered separately to capture distinct behavioral patterns.
- Combined statistics (subreddit counters, heatmaps, keyword counters) are merged directly from post and comment metrics to avoid redundant iteration passes.
- Item deduplication normalizes raw items to fullnames (prefixes like `t1_`/`t3_` + ID) to prevent missing/mismatched name keys.
- Timezone confidence score is designated as a "confidence heuristic" to clarify that it relies on simple thresholds.

## Blunders
- None logged yet.
