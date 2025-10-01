import uvicorn
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
import logging
import json
import asyncio
import time
from queue import Queue
from typing import Dict, List, Any, Optional, AsyncGenerator, Tuple
from scraper import Scraper
from contextlib import asynccontextmanager
from item_translator import get_translator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create event queue for SSE
event_queue = Queue()
total_builds = 0
current_build = 0
refresh_in_progress = False
refresh_mode: Optional[str] = None

# Custom logger handler to capture logs for the web UI
class QueueHandler(logging.Handler):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        
    def emit(self, record):
        log_entry = self.format(record)
        self.queue.put({
            'type': 'log',
            'message': log_entry,
            'log_level': record.levelname.lower()
        })

# Add queue handler to logger
queue_handler = QueueHandler(event_queue)
queue_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
queue_handler.setLevel(logging.WARNING)
logger.addHandler(queue_handler)

# Create FastAPI app
app = FastAPI(title="Diablo 4 Build Search Tool")

# Create templates directory if it doesn't exist
os.makedirs("templates", exist_ok=True)

# Set up templates
templates = Jinja2Templates(directory="templates")

# Initialize scraper
scraper = Scraper()

# Initialize item translator
translator = get_translator()
item_translations = translator.get_all_translations()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "results": None,
        "active_page": "search"
    })

@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, equipment_name: str = Form(...)):
    """
    Search for builds that use a specific piece of equipment.
    Args:
        equipment_name: The name of the equipment to search for.
    """
    original_query = equipment_name.strip()

    canonical_name, used_translation = translator.get_canonical_name(original_query)

    if used_translation:
        logger.info(
            "Resolved localized equipment name '%s' to canonical '%s'",
            original_query,
            canonical_name
        )
    else:
        logger.info("Searching for builds with equipment: %s", canonical_name)

    results = scraper.search_builds_by_equipment(canonical_name)

    display_name = (
        canonical_name
        if canonical_name.casefold() == original_query.casefold()
        else f"{original_query} ({canonical_name})"
    )

    logger.info("Found %d builds matching '%s'", len(results), canonical_name)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "results": results,
        "equipment_name": display_name,
        "active_page": "search",
        "search_query": canonical_name,
        "original_query": original_query
    })

@app.get("/unique-translations", response_class=HTMLResponse)
async def unique_translations(request: Request):
    """Display a localized reference table for all unique items."""

    sorted_items = sorted(
        item_translations,
        key=lambda entry: (entry.get("english") or "").casefold()
    )

    return templates.TemplateResponse(
        "unique_reference.html",
        {
            "request": request,
            "items": sorted_items,
            "active_page": "unique-reference"
        }
    )

@app.get("/build/{build_url:path}", response_class=HTMLResponse)
async def view_build(request: Request, build_url: str):
    """
    Display detailed information about a specific build.
    
    Args:
        build_url: The URL of the build to display.
    """
    logger.info(f"Viewing build details for: {build_url}")
    
    # Load all builds
    builds = scraper._load_builds()
    
    # Find the build with the matching URL
    build = None
    for b in builds:
        if b["url"].endswith(build_url):
            build = b
            break
    
    if not build:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "message": f"Build not found: {build_url}"
        })
    
    # Return the template response with the build details
    return templates.TemplateResponse("build_details.html", {
        "request": request,
        "build": build
    })

@app.get("/refresh-data", response_class=HTMLResponse)
async def refresh_data_page(request: Request):
    """Show the refresh data page with real-time progress."""
    return templates.TemplateResponse("refresh_data.html", {"request": request, "active_page": "refresh"})

@app.get("/api/refresh-data")
async def start_refresh_data(background_tasks: BackgroundTasks):
    """Start the full data refresh process in the background."""
    return _schedule_refresh(background_tasks, fake=False)


@app.get("/api/refresh-data-fake")
async def start_fake_refresh(background_tasks: BackgroundTasks):
    """Start the fake refresh process that mimics the real workflow."""
    return _schedule_refresh(background_tasks, fake=True)


def _schedule_refresh(background_tasks: BackgroundTasks, fake: bool) -> JSONResponse:
    """Common logic for preparing a refresh job."""
    global refresh_in_progress, total_builds, current_build, refresh_mode

    if refresh_in_progress:
        return JSONResponse(
            {"message": "Refresh already in progress", "in_progress": True},
            status_code=409
        )

    while not event_queue.empty():
        event_queue.get()

    refresh_in_progress = True
    total_builds = 0
    current_build = 0
    refresh_mode = "fake" if fake else "real"

    background_tasks.add_task(refresh_data_background, fake)

    return JSONResponse({"message": "Refresh started", "mode": refresh_mode})


def refresh_data_background(fake: bool = False):
    """Background task to refresh the builds data."""
    global refresh_in_progress, total_builds, current_build

    try:
        mode_description = "Fake data refresh" if fake else "Data refresh"
        logger.info("%s started", mode_description)
        event_queue.put({
            "type": "log",
            "message": f"{mode_description} started",
            "log_level": "info"
        })

        if fake:
            _run_fake_refresh()
        else:
            _run_real_refresh()

    except Exception as exc:
        logger.error("Error during refresh: %s", exc)
        event_queue.put({"type": "error", "message": str(exc)})
    finally:
        refresh_in_progress = False


def _run_real_refresh() -> None:
    """Execute the long-running refresh logic."""
    global total_builds, current_build

    if os.path.exists("all_builds.json"):
        os.remove("all_builds.json")
        logger.info("Removed existing all_builds.json file")
        event_queue.put({
            "type": "log",
            "message": "Removed existing all_builds.json file",
            "log_level": "info"
        })

    logger.info("Fetching build list from MaxRoll.gg")
    builds = scraper.get_build_list()
    total_builds = len(builds)
    current_build = 0

    event_queue.put({
        "type": "log",
        "message": f"Found {total_builds} builds to process",
        "log_level": "info"
    })
    event_queue.put({"type": "progress", "current": current_build, "total": total_builds})

    with open("all_builds.json", "w", encoding="utf-8") as file:
        json.dump([], file)

    processed_builds = []

    for build_index, build in enumerate(builds, start=1):
        build_url = build.get("url")
        title = build.get("title", "Unknown build")
        logger.info("Processing build %s/%s: %s", build_index, total_builds, title)

        try:
            equipment = scraper.get_build_equipment(build_url)
            build["equipment"] = equipment
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Error getting equipment for build %s: %s", title, exc)
            event_queue.put({
                "type": "log",
                "message": f"Failed to fetch equipment for {title}: {exc}",
                "log_level": "warning"
            })
            build["equipment"] = []
        finally:
            current_build = build_index
            log_message = f"Processed build {current_build}/{total_builds}: {title}"
            event_queue.put({
                "type": "progress",
                "current": current_build,
                "total": total_builds
            })
            event_queue.put({"type": "log", "message": log_message, "log_level": "info"})

            processed_builds.append(build)
            with open("all_builds.json", "w", encoding="utf-8") as file:
                json.dump(processed_builds, file, indent=2)

            time.sleep(1)

    event_queue.put({
        "type": "log",
        "message": "Completed fetching equipment data for all builds",
        "log_level": "info"
    })

    with open("all_builds.json", "w", encoding="utf-8") as file:
        json.dump(processed_builds, file, indent=2)

    logger.info("Data refresh completed successfully. Found %s builds.", len(processed_builds))
    event_queue.put({"type": "completed", "build_count": len(processed_builds)})


def _run_fake_refresh(total_steps: int = 20, delay_seconds: float = 1.0) -> None:
    """Run a lightweight fake refresh for UI validation."""
    global total_builds, current_build

    total_builds = total_steps
    current_build = 0

    event_queue.put({
        "type": "log",
        "message": f"Preparing {total_steps} fake builds for testing",
        "log_level": "info"
    })
    event_queue.put({"type": "progress", "current": current_build, "total": total_builds})

    fake_builds = []

    for step in range(1, total_steps + 1):
        time.sleep(delay_seconds)
        current_build = step
        fake_title = f"Fake Build #{step}"
        fake_builds.append({"title": fake_title, "url": f"https://example.com/fake/{step}", "equipment": []})

        event_queue.put({
            "type": "progress",
            "current": current_build,
            "total": total_builds
        })
        event_queue.put({
            "type": "log",
            "message": f"Simulated progress for {fake_title}",
            "log_level": "info"
        })

    event_queue.put({
        "type": "log",
        "message": "Fake refresh completed successfully",
        "log_level": "info"
    })
    event_queue.put({"type": "completed", "build_count": len(fake_builds)})

@app.get("/api/refresh-events")
async def refresh_events():
    """Server-sent events endpoint for refresh progress."""
    async def event_generator():
        # Send an initial event to establish the connection
        initial_event = {'type': 'log', 'message': 'Connected to event stream', 'log_level': 'info'}
        yield f"data: {json.dumps(initial_event)}\n\n"

        progress_event = {'type': 'progress', 'current': current_build, 'total': total_builds}
        yield f"data: {json.dumps(progress_event)}\n\n"

        while True:
            try:
                # If there are events in the queue, yield them
                if not event_queue.empty():
                    event = event_queue.get()
                    yield f"data: {json.dumps(event)}\n\n"

                # If refresh is not in progress and queue is empty, end the stream
                elif not refresh_in_progress and event_queue.empty():
                    final_event = {'type': 'log', 'message': 'Refresh process completed', 'log_level': 'info'}
                    yield f"data: {json.dumps(final_event)}\n\n"
                    break

                # Otherwise, send a keep-alive comment and wait a bit
                else:
                    yield ": keep-alive\n\n"
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in event stream: {e}")
                error_event = {'type': 'error', 'message': f'Error in event stream: {str(e)}', 'log_level': 'error'}
                yield f"data: {json.dumps(error_event)}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@app.get("/tier-list", response_class=HTMLResponse)
async def tier_list(request: Request):
    """
    Generate a tier list of equipment based on how many builds use each item.
    """
    logger.info("Generating equipment tier list")
    
    # Load all builds
    builds = scraper._load_builds()
    
    # Count how many builds use each equipment item
    equipment_counts = {}
    equipment_details = {}
    
    for build in builds:
        for item in build.get('equipment', []):
            item_name = item.get('name', '').strip()
            if not item_name or item_name == 'Unknown':
                continue
                
            # Only count unique/legendary items
            if not item.get('is_unique', False) and not 'unique' in item.get('type', '').lower():
                continue
                
            if item_name not in equipment_counts:
                equipment_counts[item_name] = 0
                equipment_details[item_name] = {
                    'name': item_name,
                    'type': item.get('type', 'Unknown'),
                    'category': item.get('category', 'Unknown'),
                    'description': item.get('description', ''),
                    'is_unique': item.get('is_unique', False),
                    'builds': []
                }
            
            equipment_counts[item_name] += 1
            
            # Add build to the list if not already there
            build_info = {
                'title': build.get('title', ''),
                'url': build.get('url', ''),
                'class': build.get('class', 'Unknown')
            }
            
            if build_info not in equipment_details[item_name]['builds']:
                equipment_details[item_name]['builds'].append(build_info)
    
    # Sort equipment by count (descending)
    sorted_equipment = sorted(
        [(name, count, equipment_details[name]) for name, count in equipment_counts.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    # Define tier thresholds
    tier_thresholds = {
        'S': 30,  # Items used in 30+ builds
        'A': 20,  # Items used in 20-29 builds
        'B': 10,  # Items used in 10-19 builds
        'C': 5,   # Items used in 5-9 builds
        'D': 1    # Items used in 1-4 builds
    }
    
    # Group equipment by tiers
    tiers = {
        'S': [],
        'A': [],
        'B': [],
        'C': [],
        'D': []
    }
    
    for name, count, details in sorted_equipment:
        if count >= tier_thresholds['S']:
            tier = 'S'
        elif count >= tier_thresholds['A']:
            tier = 'A'
        elif count >= tier_thresholds['B']:
            tier = 'B'
        elif count >= tier_thresholds['C']:
            tier = 'C'
        else:
            tier = 'D'
        
        tiers[tier].append({
            'name': name,
            'count': count,
            'details': details
        })
    
    # Return the template response with the tier list
    return templates.TemplateResponse("tier_list.html", {
        "request": request,
        "tiers": tiers,
        "tier_thresholds": tier_thresholds,
        "total_items": len(sorted_equipment),
        "active_page": "tier-list"
    })

if __name__ == "__main__":
    # Create templates directory if it doesn't exist
    os.makedirs("templates", exist_ok=True)
    
    # Run the app
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
