# Project: Reddit Public Activity Analyser

## Overview
A Python package (`src/`) that analyzes public posts and comments for a given Reddit username and produces a behavioral profile, including subreddits breakdown, activity heatmaps, interest keywords, and timezone estimate.

## Structure
/home/quantavil/Documents/Project/profiling/
└── src/             # Package source containing all modular subpackages and configurations.

## Conventions
- Modular package under src/ with absolute/relative imports.
- Clean parsing and simple statistics.

## Dependencies & Setup
- Requires Python >= 3.14, managed with `uv`.
- Added `scrapling` (stealthy fetching) dependency for old.reddit HTML parsing fallback.

## Critical Information
- Standard Reddit API endpoints (`.json`) return 403 Forbidden programmatically and have been completely removed from the script to avoid slow 403 retries.
- Primary Source: `scrapling` is used directly to scrape `old.reddit.com` HTML for user metadata and listing contents.
- Historical Sources: Pullpush API (`https://api.pullpush.io`) and Arctic Shift API (`https://arctic-shift.photon-reddit.com/api/`) are queried concurrently to gather history.

## Insights
- Arctic Shift and Pullpush APIs provide access to historical and deleted Reddit content.
- Merging Reddit scraping and archive API data provides a complete view of a user's footprint.
- Post and comment activity metrics (subreddits, heatmaps, keyword frequencies, sleep/timezone estimates) are analyzed and rendered separately to capture distinct behavioral patterns.
- Combined statistics (subreddit counters, heatmaps, keyword counters) are merged directly from post and comment metrics to avoid redundant iteration passes.
- Item deduplication normalizes raw items to fullnames (prefixes like `t1_`/`t3_` + ID) to prevent missing/mismatched name keys.
- Timezone confidence score is designated as a "confidence heuristic" to clarify that it relies on simple thresholds.

## Blunders
- Swallowed commas and hidden score details in score parsing due to broad exception handling; fixed by implementing regex score parsing supporting negative numbers and suffixes.
- Concatenating raw username values without sanitization resulted in path traversal vulnerability; fixed by validating usernames with `^[A-Za-z0-9_-]{3,20}$`.
- Item deduplication appended items when fullname returned `None`; fixed by enforcing fullname existence during listing merging.
