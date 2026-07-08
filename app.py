import re
import sys
import json
from pathlib import Path
import uvicorn
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.fetchers.old_reddit import fetch_about
from src.fetchers import fetch_listing
from src.analyzer import analyse
from src.formatter import render_markdown

app = FastAPI(
    title="Reddit Public Activity Analyser Dashboard API",
    description="Backend API for fetching, profiling, and managing Reddit users activity",
    version="1.1.0",
)

@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Regex to prevent directory traversal and validate Reddit usernames
USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_-]{3,20}$")

@app.get("/api/analyse")
def api_analyse(
    username: str = Query(..., description="Reddit username to analyse"),
    limit: int = Query(250, ge=1, le=1000, description="Max items per listing type"),
    source: str = Query("all", pattern="^(all|reddit|pullpush|arctic)$", description="Data source to fetch from"),
):
    # Sanitize and validate username
    username_clean = username.strip().lstrip("u/")
    if not USERNAME_REGEX.match(username_clean):
        raise HTTPException(
            status_code=400,
            detail="Invalid or unsafe username. Reddit usernames must be 3-20 characters long and contain only alphanumeric characters, underscores, or hyphens."
        )

    try:
        # Fetch about page
        about = fetch_about(username_clean)
        
        # Fetch listings (submitted posts & comments)
        posts = fetch_listing(username_clean, "submitted", limit, source)
        comments = fetch_listing(username_clean, "comments", limit, source)
        
        # If absolutely no data could be retrieved, inform the client
        if not posts and not comments and not about:
            raise HTTPException(
                status_code=404,
                detail=f"No public data or metadata found for user u/{username_clean}. The user might not exist, be suspended, or have no public contributions."
            )
            
        # Run profiling analysis
        profile = analyse(about, posts, comments)
        
        # Add basic success and metadata info
        profile["status"] = "success"
        profile["queried_username"] = username_clean
        profile["queried_limit"] = limit
        profile["queried_source"] = source
        
        # Ensure output folder exists and write the JSON and MD outputs (matching CLI functionality)
        outdir = Path("output")
        outdir.mkdir(parents=True, exist_ok=True)
        
        # Write JSON file
        json_path = outdir / f"{username_clean}_profile.json"
        json_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
        
        # Write MD report file
        try:
            md = render_markdown(username_clean, profile)
            md_path = outdir / f"{username_clean}_profile.md"
            md_path.write_text(md, encoding="utf-8")
        except Exception as e:
            print(f"Warning: Failed to render markdown for u/{username_clean}: {e}", file=sys.stderr)
        
        return profile
        
    except HTTPException as he:
        raise he
    except Exception as e:
        # Print stack trace to stderr for server side debugging
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during profiling: {str(e)}"
        )

@app.get("/api/profiles")
def api_list_profiles():
    """Lists lightweight metadata of all profiles saved in output folder."""
    outdir = Path("output")
    if not outdir.exists() or not outdir.is_dir():
        return []
    
    profiles = []
    for f in outdir.glob("*_profile.json"):
        try:
            m = USERNAME_REGEX.match(f.name.split("_profile")[0])
            if not m:
                continue
            username = m.group(0)
            
            # Read file to extract summary statistics (fast and lightweight)
            with open(f, encoding="utf-8") as file_obj:
                data = json.load(file_obj)
            
            about = data.get("about") or {}
            counts = data.get("counts") or {}
            tz = data.get("tz_estimate_combined") or {}
            
            profiles.append({
                "username": username,
                "total_karma": about.get("total_karma", 0),
                "posts": counts.get("posts", 0),
                "comments": counts.get("comments", 0),
                "total": counts.get("total", 0),
                "utc_offset": tz.get("estimated_utc_offset"),
                "confidence": tz.get("confidence_heuristic", "low"),
                "modified_at": f.stat().st_mtime
            })
        except Exception as e:
            print(f"Warning: Failed to parse profile file {f.name}: {e}", file=sys.stderr)
            
    # Sort profiles: most recently modified first
    profiles.sort(key=lambda x: x["modified_at"], reverse=True)
    return profiles

@app.get("/api/profiles/{username}")
def api_get_saved_profile(username: str):
    """Retrieves a saved profile from the output directory directly (cached lookup)."""
    username_clean = username.strip().lstrip("u/")
    if not USERNAME_REGEX.match(username_clean):
        raise HTTPException(
            status_code=400,
            detail="Invalid username format."
        )
        
    file_path = Path("output") / f"{username_clean}_profile.json"
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Cached profile for user u/{username_clean} was not found in the output folder."
        )
        
    return FileResponse(file_path)

@app.delete("/api/profiles/{username}")
def api_delete_saved_profile(username: str):
    """Deletes a saved profile (both JSON and MD report) from output directory."""
    username_clean = username.strip().lstrip("u/")
    if not USERNAME_REGEX.match(username_clean):
        raise HTTPException(
            status_code=400,
            detail="Invalid username format."
        )
        
    json_path = Path("output") / f"{username_clean}_profile.json"
    md_path = Path("output") / f"{username_clean}_profile.md"
    
    deleted = False
    if json_path.exists():
        json_path.unlink()
        deleted = True
    if md_path.exists():
        md_path.unlink()
        deleted = True
        
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Profile for user u/{username_clean} was not found."
        )
        
    return {"status": "success", "detail": f"Profile files for u/{username_clean} deleted successfully."}

# Serve the static files
# Serve index.html directly from root route
@app.get("/")
def read_index():
    return FileResponse("static/index.html")

# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    print("Starting Reddit Public Activity Analyser Dashboard...")
    print("Open http://127.0.0.1:8000 in your browser to view the dashboard.")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
