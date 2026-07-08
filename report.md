# Audit Evaluation & Architecture Report

This report evaluates the merged audit findings against the codebase of the **Reddit Public Activity Analyser** ([main.py](file:///home/quantavil/Documents/Project/profiling/main.py)) and discusses the viability of the dual-API/source scraping architecture.

---

## Part 1: Verifiable Hard Bugs & Logic Flaws

### 1. Data Loss on Text Deletion (Critical Logic Flaw)
* **Status**: **True Bug**
* **Analysis**: In `analyse()` (lines 329-330), the lists of posts and comments are filtered:
  ```python
  valid_posts = [p for p in posts if not is_deleted_or_removed(p)]
  valid_comments = [c for c in comments if not is_deleted_or_removed(c)]
  ```
  This drops deleted items completely from heatmaps, active span calculations, and subreddit counters. Since a deleted post/comment still represents user activity at that time, dropping it distorts the temporal and subreddit metrics.
* **Resolution**: Keep the metadata (`created_utc`, `subreddit`) for temporal and subreddit counts, but clear/ignore the `body`/`selftext` fields during text analysis (NLP/keywords).

### 2. Overly Aggressive Deletion Detection
* **Status**: **True Bug**
* **Analysis**: In `is_deleted_or_removed()` (line 80), the raw strings `"deleted"` and `"removed"` are checked:
  ```python
  placeholders = {"[deleted]", "[removed]", "deleted", "removed"}
  ```
  If a user makes a legitimate one-word comment like `"removed"`, the script flags it as a platform deletion and excludes/handles it differently.
* **Resolution**: Limit placeholders to Reddit's official bracketed tags: `"[deleted]"` and `"[removed]"`, or check if `author == "[deleted]"`.

### 3. Path Traversal via Username
* **Status**: **True Bug**
* **Analysis**: The script writes output files to `outdir / f"{username}_profile.md"` without sanitizing the username argument. If the username is a path traversal sequence like `../../etc/passwd`, it tries to write files outside the target directory.
* **Resolution**: Validate the username using a regex (e.g., `^[A-Za-z0-9_-]{3,20}$`) or strip path characters before constructing file paths.

### 4. Score Parsing Fails on Suffixes (Silent Data Loss)
* **Status**: **Partially True / Incorrect Fix Recommendation**
* **Analysis**: 
  * **True part**: The parser `int(score_text.replace("points", "").replace("point", "").strip())` raises a `ValueError` for strings with commas (e.g., `"1,234 points"`), which is caught by a broad `except Exception` block and silently defaults the score to `0`.
  * **Incorrect recommendation part**: The proposed regex replacement `r"([0-9.]+)\s*([km]?)"` does **not** match negative signs. Reddit comments frequently have negative scores (e.g., `"-5"`), which would match nothing and return `0`.
* **Resolution**: Use a parser that supports commas, suffixes (like `k` and `m`), and optional negative signs:
  ```python
  match = re.match(r"([-+]?[0-9.]+)\s*([km]?)", text)
  ```

### 5. `--infile` Username Bypass
* **Status**: **True Bug**
* **Analysis**: When using `--infile`, the script derives the username from the filename but checks `args.username` to fetch the account metadata:
  ```python
  about = fetch_about(username) if args.username else None
  ```
  Since `args.username` is `None` in this scenario, the profile metadata is silently skipped despite the derived username being available.
* **Resolution**: Change to `about = fetch_about(username) if username else None`.

### 6. Flawed Dedup Logic
* **Status**: **True Bug**
* **Analysis**: If `_get_fullname()` returns `None`, `name` is `None`. The condition `if not name or name not in existing_names` evaluates to `True`, appending the item to the final list and bypassing deduplication.
* **Resolution**: Enforce ID generation or skip items that lack a fullname/ID.

### 7. Missing `permalink` & Broken Links
* **Status**: **True Bug**
* **Analysis**: `fetch_listing_old_reddit` does not extract or construct `permalink`, resulting in broken links `[Link](https://reddit.com)` in the generated Markdown.
* **Resolution**: Extract the permalink directly from the comment's/post's HTML structure (e.g., from `a.bylink`), which is more robust than manual string assembly.

### 8. Silent Override of `--user-agent`
* **Status**: **True Bug**
* **Analysis**: `fetch_listing_arctic_shift` hardcodes `headers = {"User-Agent": "Mozilla/5.0"}`, completely ignoring the global `HEADERS` dictionary which can be set by the user via the `--user-agent` CLI flag.
* **Resolution**: Pass the global `HEADERS` (or local headers derived from it) to the request.

### 9. Fabricated Account Fields
* **Status**: **True Bug**
* **Analysis**: `fetch_about_fallback` hardcodes `"verified": False` and `"has_verified_email": False`. These values are not available on Old Reddit user pages.
* **Resolution**: Remove these key-value pairs from the dictionary to avoid conveying false data.

### 10. Markdown Injection
* **Status**: **Partially True / False Positive**
* **Analysis**:
  * **False Positive part**: The audit states that titles like `How to | pipe | output` break table layouts. However, no user-generated text (titles/bodies) is rendered inside Markdown tables in this script.
  * **True part**: User text is injected directly into markdown headers (e.g., `### {idx+1}. {title}`), which can break layout structure if the title contains markdown formatting or newlines.
* **Resolution**: Escape markdown headers and sanitize titles/bodies before writing them.

---

## Part 2: Redundancies & Robustness

### 1. Dead API Endpoints & Brittle Scraping
* **Status**: **False Positive / Incorrect Recommendation**
* **Analysis**: 
  * Recommending the complete replacement of Arctic Shift (`photon-reddit.com`) is a false positive under a redundancy-first approach. While Arctic Shift has reliability issues, it should be kept as a secondary fallback. We should integrate Pullpush API (`api.pullpush.io`) alongside Arctic Shift to support both sources.
  * Recommending `PRAW` is **incorrect** because PRAW requires OAuth credentials (client IDs/secrets), violating the script's constraint of being **no auth / zero config**.
  * Suggesting `httpx` + `selectolax` is a design trade-off. Recommending it because `scrapling` is a "headless browser" is incorrect; Scrapling's `StealthyFetcher` performs request-based scrapes (similar to curl-impersonate/httpx) without spawning a browser process by default. Introducing `httpx` + `selectolax` would add unnecessary third-party dependencies.

### 2. Redundant Processing
* **Status**: **False Positive / Incorrect Recommendation**
* **Analysis**:
  * **Triple Heatmap**: Reconstructing the combined heatmap by adding the cells of the posts and comments heatmaps (a small 7x24 grid) is extremely fast. Suggesting to call `make_heatmap(valid_posts + valid_comments)` instead would lose the separate post and comment heatmaps which are explicitly displayed in the markdown report.
  * **Triple Keyword Counting**: `get_word_counter()` is only called twice (not three times). Since posts and comments are disjoint lists, iterating them separately traverses each item exactly once ($O(N)$), which is optimal.
  * **Double Deletion Check**: **True**. `is_deleted_or_removed` is evaluated during both analysis and rendering. Attaching it as a boolean key to the item dictionary is a cleaner solution.

### 3. No Rate-Limit Handling for Old Reddit
* **Status**: **Partially True / Incorrect Recommendation**
* **Analysis**: 
  * **True part**: The scraper has no retry or delay handling for 503/429 status codes.
  * **Incorrect recommendation part**: Respecting `X-Ratelimit-Remaining` is impossible for HTML scrapes because this header is only sent on the JSON API. Introducing `tenacity` is also an unnecessary dependency when a basic retry loop using `time.sleep` is cleaner and self-contained.

### 4. `scrapling` Imported Inside Functions
* **Status**: **False Positive**
* **Analysis**: Importing `scrapling` inside functions is a deliberate pattern. It allows the tool to degrade gracefully and run offline or using `--source arctic` even if `scrapling` is not installed on the system.

---

## Architecture Discussion: Should We Use a Dual-API/Source Approach?

**Yes, we absolutely should continue using a dual-source approach.** 

Combining direct scraping of `old.reddit.com` and an archive API (Pullpush) provides a unique set of complementary benefits that neither can achieve alone:

1. **Real-time Data vs. Historical Archive**:
   * **Direct Scraping**: Fetches the most recent, up-to-the-minute activity directly from Reddit.
   * **Archive API (Pullpush)**: Has an indexing delay (varying from minutes to days). Relying solely on Pullpush means missing the user's most recent posts.

2. **Capturing Deleted/Removed Activity**:
   * **Direct Scraping**: Only returns posts and comments that are currently active. Once deleted, they disappear completely from the user's profile feed.
   * **Archive API (Pullpush)**: Retains historical records of posts/comments before they were deleted or moderated. This is vital for behavioral profiling (e.g. tracking deletion habits or reading edited/deleted text).

3. **Circumventing listing limits**:
   * **Direct Scraping**: Reddit limits public user listings to the last 1,000 items. 
   * **Archive API (Pullpush)**: Can query historical database records, allowing analysis of very old activity.

4. **Resiliency and Fallback**:
   * If direct scraping is rate-limited or blocked, the archive API serves as a fallback.
   * If the archive API is temporarily down, the direct scraper still provides recent profile analysis.

### Recommendation for Implementation
We agree on integrating the **Pullpush API** (`api.pullpush.io`) alongside the existing **Arctic Shift API** (`photon-reddit.com`) for maximum archive source redundancy. The implementation plan is detailed below:

1. **Dual Archive Source Integration (Arctic + Pullpush)**:
   * Keep the Arctic Shift search endpoints as a fallback.
   * Add Pullpush search endpoints:
     * **Submission Search Endpoint**:
       `https://api.pullpush.io/reddit/search/submission/?author={username}&limit=100`
     * **Comment Search Endpoint**:
       `https://api.pullpush.io/reddit/search/comment/?author={username}&limit=100`
   * Implement both fetchers so the application can query them sequentially or selectively.

2. **Deduplication Improvements**:
   * Resolve the fullname parsing issues in `_get_fullname()` and `fetch_listing()` to ensure items scraped from `old.reddit.com`, fetched from `api.pullpush.io`, and fetched from Arctic Shift are cleanly merged and deduped without duplicates.

3. **Fallback and Resilience**:
   * Retain and expand the CLI `--source` parameter to support choices like `reddit`, `arctic`, `pullpush`, or `all` (default: `all` or `both` which merges all available sources), ensuring maximum uptime and data retrieval capability.

