import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
import logging
from scraper import Scraper

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    results = scraper.search_builds_by_equipment(equipment_name)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "results": results,
        "equipment_name": equipment_name
    })

@app.get("/refresh-data")
async def refresh_data(request: Request):
    """Force a refresh of the builds data."""
    logger.info("Forcing data refresh")
    
    # Remove the cached data file if it exists
    if os.path.exists(scraper.builds_data_file):
        os.remove(scraper.builds_data_file)
        
    # Re-scrape the data
    builds = scraper.scrape_all_builds()
    return {"message": f"Data refreshed successfully. Found {len(builds)} builds."}

if __name__ == "__main__":
    # Create templates directory if it doesn't exist
    os.makedirs("templates", exist_ok=True)
    
    # Run the app
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
