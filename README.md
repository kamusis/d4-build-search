# Diablo 4 Build Search Tool

A tool to search Diablo 4 builds based on specific unique equipment (including Mythic uniques). It provides both a command-line interface and a web UI for searching builds and viewing equipment tier lists.

## Features

- Scrape build data from https://maxroll.gg/d4/build-guides
- Search builds by specific unique equipment, class, or tags
- **Multilingual support**: Search using English, Simplified Chinese (简体中文), or Traditional Chinese (繁體中文) equipment names
- Web interface with search, build details, and equipment tier list
- Real-time progress tracking during data refresh

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the web application:
   ```bash
   python app.py
   ```

3. Open your browser and navigate to `http://localhost:8000`

## Command-Line Usage

You can also use the scraper directly from the command line:

```bash
# Scrape builds and save to JSON file
python scraper.py --get-all-builds

# Search for builds using specific equipment (supports English and Chinese names)
python scraper.py --search "Harlequin Crest"
python scraper.py --search "谐角之冠"
python scraper.py --search "諧角之冠"

# Filter search results by class
python scraper.py --search "雷神之戒" --class Druid
python scraper.py --search "破碎冬镜" --class Sorcerer

# Filter search results by tags
python scraper.py --search "Harlequin Crest" --tags endgame

# Combine multiple filters
python scraper.py --search "Harlequin Crest" --class Sorcerer --tags endgame
```

## Web UI Guide

### Home Page / Search
- Enter equipment names, class, or tags to search for builds
- Results are grouped by character class
- Click on build titles to view detailed information

### Build Details
- View complete information about a specific build
- See all equipment items used in the build
- Find links to the original build guide

### Equipment Tier List
- View equipment ranked by popularity in builds
- Equipment is categorized into tiers (S, A, B, C, D)
- Click on equipment names to see which builds use them

### Data Refresh
- Click "Refresh Data" from any page to update the build database
- A confirmation dialog will warn about the processing time
- The refresh page shows real-time progress and logs

## Data Files

### all_items.json
Contains multilingual names for all Diablo 4 unique items:
- English names
- Simplified Chinese (简体中文)
- Traditional Chinese (繁體中文)

The data is scraped from https://diablo4.cc and includes 160+ unique items sorted alphabetically.

### Updating Item Names

To refresh the unique item names database:

```bash
python scripts/scrape_uniques.py
```

This will:
1. Fetch all unique items from diablo4.cc
2. Retrieve names in English, Simplified Chinese, and Traditional Chinese
3. Save results to `scraped_items.json`
4. You can then copy the data to `all_items.json`

## How it Works

The application scrapes build data from MaxRoll.gg and allows you to search for builds that use specific unique equipment. This helps players find viable builds utilizing particular unique or mythic items they've found. The tier list feature helps identify the most popular and effective equipment across all builds.
