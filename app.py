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
from typing import Dict, List, Any, Optional, AsyncGenerator
from scraper import Scraper
from contextlib import asynccontextmanager

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
logger.addHandler(queue_handler)

# Create FastAPI app
app = FastAPI(title="Diablo 4 Build Search Tool")

# Create templates directory if it doesn't exist
os.makedirs("templates", exist_ok=True)

# Set up templates
templates = Jinja2Templates(directory="templates")

# Initialize scraper
scraper = Scraper()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page."""
    return templates.TemplateResponse("index.html", {"request": request, "results": None})

@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, equipment_name: str = Form(...)):
    """
    Search for builds that use a specific piece of equipment.
    
    Args:
        equipment_name: The name of the equipment to search for.
    """
    logger.info(f"Searching for builds with equipment: {equipment_name}")
    
    # Search for builds using the equipment name
    results = scraper.search_builds_by_equipment(equipment_name)
    
    # Log the number of results found
    logger.info(f"Found {len(results)} builds matching '{equipment_name}'")
    
    # Return the template response with the search results
    return templates.TemplateResponse("index.html", {
        "request": request,
        "results": results,
        "equipment_name": equipment_name
    })

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
    return templates.TemplateResponse("refresh_data.html", {"request": request})

@app.get("/api/refresh-data")
async def start_refresh_data(background_tasks: BackgroundTasks):
    """Start the data refresh process in the background."""
    global refresh_in_progress, total_builds, current_build
    
    if refresh_in_progress:
        return JSONResponse({"message": "Refresh already in progress"})
    
    # Clear the event queue
    while not event_queue.empty():
        event_queue.get()
    
    # Reset counters
    refresh_in_progress = True
    total_builds = 0
    current_build = 0
    
    # Start the refresh process in the background
    background_tasks.add_task(refresh_data_background)
    
    return JSONResponse({"message": "Refresh started"})

async def refresh_data_background():
    """Background task to refresh the builds data."""
    global refresh_in_progress, total_builds, current_build
    
    try:
        logger.info("Starting data refresh process")
        event_queue.put({"type": "log", "message": "Starting data refresh process", "log_level": "info"})
        
        # Remove the cached data file if it exists
        if os.path.exists("all_builds.json"):
            os.remove("all_builds.json")
            logger.info("Removed existing all_builds.json file")
        
        # Re-scrape the build list
        logger.info("Fetching build list from MaxRoll.gg")
        builds = scraper.get_build_list()
        total_builds = len(builds)
        event_queue.put({"type": "log", "message": f"Found {total_builds} builds to process", "log_level": "info"})
        event_queue.put({"type": "progress", "current": 0, "total": total_builds})
        
        # Monkey patch the scraper's get_equipment_for_build method to track progress
        original_get_equipment = scraper.get_equipment_for_build
        
        def get_equipment_with_progress(build):
            global current_build
            result = original_get_equipment(build)
            current_build += 1
            event_queue.put({"type": "progress", "current": current_build, "total": total_builds})
            event_queue.put({"type": "log", "message": f"Processed build {current_build}/{total_builds}: {build['title']}", "log_level": "info"})
            return result
        
        # Replace the method temporarily
        scraper.get_equipment_for_build = get_equipment_with_progress
        
        # Get equipment data for all builds
        logger.info("Fetching equipment data for all builds")
        builds = scraper.get_equipment_for_builds(builds)
        
        # Restore the original method
        scraper.get_equipment_for_build = original_get_equipment
        
        # Save the updated builds data
        with open("all_builds.json", 'w') as f:
            json.dump(builds, f, indent=2)
        
        logger.info(f"Data refresh completed successfully. Found {len(builds)} builds.")
        event_queue.put({"type": "completed", "build_count": len(builds)})
    
    except Exception as e:
        logger.error(f"Error during data refresh: {e}")
        event_queue.put({"type": "error", "message": str(e)})
    
    finally:
        refresh_in_progress = False

@app.get("/api/refresh-events")
async def refresh_events():
    """Server-sent events endpoint for refresh progress."""
    async def event_generator():
        while True:
            # If there are events in the queue, yield them
            if not event_queue.empty():
                event = event_queue.get()
                yield f"data: {json.dumps(event)}\n\n"
            
            # If refresh is not in progress and queue is empty, end the stream
            elif not refresh_in_progress:
                break
            
            # Otherwise, wait a bit before checking again
            await asyncio.sleep(0.1)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

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
        "total_items": len(sorted_equipment)
    })

if __name__ == "__main__":
    # Create templates directory if it doesn't exist
    os.makedirs("templates", exist_ok=True)
    
    # Run the app
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
