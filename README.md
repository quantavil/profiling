# Reddit Public Activity Analyser

An elegant and lightweight tool to fetch, analyze, and profile public Reddit posts and comments for any given user. It retrieves data across multiple sources—combining real-time stealthy scraping of `old.reddit.com` with historical/deleted archives from the Pullpush and Arctic Shift APIs—to construct a comprehensive behavioral profile.

## Key Features

- **Multi-Source Data Aggregation**: Queries active posts and comments via stealthy scraping (`scrapling`) and retrieves historical/deleted contributions from Pullpush and Arctic Shift APIs concurrently.
- **Detailed Profiling & Analytics**:
  - Subreddit activity breakdown.
  - Hourly and weekly activity heatmaps.
  - Keyword and key topic extraction (with customizable stopword filters).
  - Timezone and sleep schedule estimation using a heuristic confidence score.
- **Interactive Web Dashboard**: A modern, FastAPI-powered SPA utilizing Alpine.js and Chart.js. Features:
  - On-demand analysis of any Reddit username.
  - Interactive activity charts and heatmaps.
  - A persistent sidebar list of cached profiles with quick reloading and deletion.
  - Light/Dark glassmorphic aesthetics and responsive layout.
- **Command Line Interface (CLI)**: Command-line script to query users directly from the terminal or analyze local JSON exports.
- **Output Formats**: Automatically exports structured data to JSON (`output/<username>_profile.json`) and writes clean, human-readable reports to Markdown (`output/<username>_profile.md`).

---

## Project Structure

- `app.py`: FastAPI server serving static files and exposing `/api/` endpoints.
- `src/`: Core Python package containing modular analyzer and fetcher utilities.
  - `src/cli.py` / `src/__main__.py`: Command-line interface logic.
  - `src/analyzer.py`: Performs data aggregation, deduplication, timezone estimation, and keyword parsing.
  - `src/formatter.py`: Generates the Markdown report from profiling results.
  - `src/fetchers/`: Fetchers for scraped and archived Reddit data.
- `static/`: Frontend single-page dashboard application.
  - `static/index.html`: Entrypoint containing layout and responsive templates.
  - `static/js/app.js`: Alpine.js frontend state management and API integration.
  - `static/js/charts.js`: Chart.js configuration for rendering user statistics.
  - `static/css/styles.css`: Custom CSS variables, scrollbars, and glassmorphic designs.
- `tests/`: Automated unit and integration test suite.

---

## Installation & Setup

### Prerequisites
- Python `>= 3.14`
- [uv](https://github.com/astral-sh/uv) (recommended Python package and environment manager)

### Installation
Clone or navigate to the project directory and install the package dependencies:

```bash
# Create a virtual environment and install dependencies
uv sync
```

Alternatively, using standard Python `pip`:

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies and the package in editable mode
pip install -e .
```

---

## How to Run

### 1. Interactive Web Dashboard
Run the FastAPI development server:

```bash
uv run python app.py
```
*(Or `python app.py` if your virtual environment is active)*

Once started, open your web browser and navigate to:
```
http://127.0.0.1:8000
```

### 2. Command Line Interface (CLI)
You can run the CLI tool directly to analyze any Reddit username:

```bash
# Analyze a username using all sources (default limit 1000 items)
uv run python -m profiling <username>

# Customize the limit of items to fetch
uv run python -m profiling <username> --limit 250

# Specify a data source (choices: all, reddit, arctic, pullpush)
uv run python -m profiling <username> --source reddit

# Analyze a previously exported JSON dump instead of fetching from live APIs
uv run python -m profiling --infile output/some_user_profile.json
```

The CLI will print analysis summaries to terminal and output results under `output/`:
- `output/<username>_profile.json`
- `output/<username>_profile.md`

### 3. Running Tests
Run the test suite using `unittest`:

```bash
uv run python -m unittest discover tests
```

---

## Data Sources Configuration
- **Reddit scraping**: Falls back to stealthy scraping of `old.reddit.com` via `scrapling` (to bypass standard API `403 Forbidden` limits).
- **Arctic Shift API**: Queries `https://arctic-shift.photon-reddit.com/api/` for historical data.
- **Pullpush API**: Queries `https://api.pullpush.io` for historical and deleted posts/comments.
