import requests
from bs4 import BeautifulSoup
import json
import logging
import os
import time
import argparse
from typing import Dict, List, Any, Optional

# Path to ChromeDriver for Apple Silicon (mac-arm64)
CHROMEDRIVER_PATH = "/Users/kamus/.wdm/drivers/chromedriver/mac64/136.0.7103.93/chromedriver-mac-arm64/chromedriver"

# Constants for Diablo 4 classes
D4_CLASSES = ["Rogue", "Barbarian", "Druid", "Sorcerer", "Necromancer", "Spiritborn"]
D4_CLASSES_LOWER = [class_name.lower() for class_name in D4_CLASSES]

# Constants for build types
BUILD_TYPES = ["endgame", "leveling"]

# Constants for skill/build tags
SKILL_TAGS = [
    # Original class skills
    "penetrating shot", "hammer of the ancients", "incinerate", "flurry", "barrage",
    "twisting blades", "blood wave", "sever", "blizzard", "blood surge", "boulder",
    "bone spear", "blight", "pulverize", "shred", "tornado", "firewall", "whirlwind",
    "ice shards", "frozen orb", "shadow step", "rend", "landslide", "thorns", "rapid fire",
    "blood lance", "double swing", "ball lightning", "lightning storm", "support", "companion",
    "chain lightning", "meteor", "infinimist", "earthquake", "death trap", "lightning spear",
    "rupture", "death blow", "stone burst", "dance of knives", "rain of arrows", "cataclysm",
    "mighty throw", "invigorating strike", "heartseeker", "bone spirit", "minion",
    
    # Spiritborn skills
    "quill volley", "eagle", "spirit surge", "spirit storm", "wrath", "panther", "snake", "bear",
    "wolf", "tiger", "gorilla", "owl", "hawk", "falcon", "vulture", "condor", "eagle form",
    "panther form", "snake form", "bear form", "wolf form", "tiger form", "gorilla form", "owl form",
    "hawk form", "falcon form", "vulture form", "condor form", "spirit guide"
]

# Constants for season tags
SEASON_TAGS = {
    "season 8": ["season 8", "belial's return"]
}

# Known unique items in Diablo 4
KNOWN_UNIQUES = [
    # Weapons
    'Eaglehorn', 'Doombringer', 'Grandfather', 'Andariel\'s Visage', 'Harlequin Crest',
    'The Butcher\'s Cleaver', 'Melted Heart of Selig', 'Maltorius\' Petrified Skull',
    # Armor
    'Fists of Fate', 'Cowl of the Nameless', 'Penitent Greaves', 'Shroud of Khanduras',
    'Shroud of False Death', 'Tyrael\'s Might', 'Iceheart Brais', 'Razorplate',
    'Tassets of the Dawning Sky', 
    # Jewelry
    'Ring of Starless Skies', 'Skull of Garesh',
    'Tibault\'s Will', 'Temptation',
    # Mythics
    'Heir of Perdition', 'Godslayer Crown', 'Banished Lord\'s Talisman',
    'Dirge of Melandru', 'Storm\'s Companion', 'Lidless Wall',
    'Wind Striker', 'Monster Hunter\'s Glow', 'Curucle\'s Favor'
]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# End of imports
logger = logging.getLogger(__name__)

class Scraper:
    """A scraper to extract Diablo 4 build data from MaxRoll.gg."""
    
    def __init__(self, base_url: str = "https://maxroll.gg"):
        """
        Initialize the scraper.
        
        Args:
            base_url: The base URL for the MaxRoll website.
        """
        self.base_url = base_url
        self.builds_url = f"{base_url}/d4/build-guides"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.builds_data_file = "builds_data.json"
        self.driver = None
    
    def __del__(self):
        """
        Clean up resources when the scraper is garbage collected.
        """
        self.close()
    
    def close(self):
        """
        Close the Selenium WebDriver and clean up resources.
        """
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None
    
    def _init_selenium_driver(self):
        """
        Initialize the Selenium WebDriver for Chrome.
        
        Returns:
            A configured WebDriver instance.
        """
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")  # Run Chrome in headless mode (no GUI)
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument(f"user-agent={self.headers['User-Agent']}")
            
            # Set up Chrome driver using the manually specified path for Apple Silicon (mac-arm64)
            service = Service(executable_path=CHROMEDRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            return driver
        except Exception as e:
            logger.error(f"Error initializing Selenium WebDriver: {e}")
            return None

    def get_build_list(self) -> List[Dict[str, Any]]:
        """
        Get the list of all builds from the build guides page.
        
        Returns:
            A list of dictionaries containing build information.
        """
        logger.info(f"Fetching build list from {self.builds_url}")
        
        try:
            return self._get_build_list_selenium()
        except Exception as e:
            logger.error(f"Error fetching build list: {e}")
            raise RuntimeError(f"Failed to fetch build list: {e}")
    
    def _get_build_list_selenium(self) -> List[Dict[str, Any]]:
        """
        Get the list of all builds using Selenium to handle JavaScript-loaded content.
        
        Returns:
            A list of dictionaries containing build information.
        """
        logger.info("Using Selenium to fetch build list")
        
        try:
            # Initialize the driver if not already done
            if not self.driver:
                logger.info("Initializing Selenium WebDriver...")
                self.driver = self._init_selenium_driver()
                if not self.driver:
                    logger.error("Failed to initialize Selenium WebDriver")
                    raise Exception("Failed to initialize Selenium WebDriver")
            
            logger.info(f"Navigating to build guides page: {self.builds_url}")
            self.driver.get(self.builds_url)
            logger.info("Page requested, waiting for build cards to appear...")
            
            # Try 'article' selector first, then fallback to others if needed
            selectors = ["article", ".d4-build-card", ".build-card", ".guide-card", ".guide-item", ".content-card"]
            wait = WebDriverWait(self.driver, 10)
            found_selector = None

            logger.info("Trying primary selector: article")
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article")))
                logger.info("Found build cards with selector: article")
                found_selector = "article"
            except TimeoutException:
                logger.info("Timeout waiting for selector: article; trying fallback selectors...")
                # Try other selectors as fallback
                for selector in selectors[1:]:
                    logger.info(f"Waiting for selector: {selector}")
                    try:
                        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                        logger.info(f"Found build cards with selector: {selector}")
                        found_selector = selector
                        break
                    except TimeoutException:
                        logger.info(f"Timeout waiting for selector: {selector}")
                        continue
            if not found_selector:
                logger.warning("No build card selectors found after waiting.")
            else:
                logger.info(f"Proceeding to parse page source using selector: {found_selector}")

            # Scroll to the bottom of the page to load all builds (infinite scroll)
            logger.info("Scrolling to load all builds...")
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_attempt = 1
            while True:
                logger.info(f"Scroll attempt {scroll_attempt}: Scrolling to bottom...")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)  # Wait for new builds to load
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    logger.info("No more content loaded after scrolling. Assuming all builds are loaded.")
                    break
                last_height = new_height
                scroll_attempt += 1
            logger.info("Fetching page source and parsing with BeautifulSoup...")
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Try to find build cards with various selectors
            builds = []
            for selector in selectors:
                build_cards = soup.select(selector)
                if build_cards:
                    logger.info(f"Found {len(build_cards)} build cards with selector: {selector}")
                    
                    # Save a sample build card HTML to a file for inspection
                    if len(build_cards) > 0:
                        with open("sample_build_card.html", "w", encoding="utf-8") as f:
                            f.write(str(build_cards[0]))
                        logger.info("Saved sample build card HTML to sample_build_card.html")
                    for card in build_cards:
                        # Try to extract title and link (several possible selectors)
                        title_elem = card.select_one(".title, h2, h3, .card-title, .guide-title, a")
                        if not title_elem:
                            logger.info("Skipping card: No title element found")
                            continue
                        
                        title = title_elem.text.strip()
                        # Skip if title is too short
                        if len(title) < 5:
                            logger.info(f"Skipping card: Title too short: '{title}'")
                            continue
                            
                        # Check if it looks like a build guide title
                        if not any(class_name in title.lower() for class_name in D4_CLASSES_LOWER):
                            logger.info(f"Skipping card: No class name in title: '{title}'")
                            continue
                        
                        link_elem = card.select_one("a")
                        if not link_elem:
                            logger.info(f"Skipping card with title '{title}': No link element found")
                            continue
                        
                        link = link_elem.get("href")
                        if not link:
                            logger.info(f"Skipping card with title '{title}': Empty link")
                            continue
                            
                        if not "/d4/build-guides/" in link:
                            logger.info(f"Skipping card with title '{title}': Not a build guide link: {link}")
                            continue
                            
                        full_url = f"{self.base_url}{link}" if link.startswith("/") else link
                        
                        # Extract class name from the title or dedicated element
                        class_elem = card.select_one(".class, .character-class, .build-class")
                        class_name = class_elem.text.strip() if class_elem else "Unknown"
                        
                        # If class name is unknown, try to extract it from the title
                        if class_name == "Unknown":
                            for c in D4_CLASSES:
                                if c.lower() in title.lower():
                                    class_name = c
                                    break
                        
                        # Extract difficulty
                        difficulty_elem = card.select_one(".difficulty, .build-difficulty")
                        difficulty_text = difficulty_elem.text.strip() if difficulty_elem else "Medium"
                        
                        # Extract tags from the title since MaxRoll doesn't have explicit tag elements
                        title_lower = title.lower()
                        tags = []
                        
                        # Extract build type tag (Endgame or Leveling)
                        for build_type in BUILD_TYPES:
                            if build_type in title_lower:
                                tags.append(build_type)
                                break
                        
                        # Extract class tag
                        for class_tag in D4_CLASSES_LOWER:
                            if class_tag in title_lower:
                                tags.append(class_tag)
                        
                        # Extract skill/build type tags
                        for skill_tag in SKILL_TAGS:
                            if skill_tag in title_lower:
                                tags.append(skill_tag)
                        
                        # Add Season tags
                        for season_key, season_values in SEASON_TAGS.items():
                            if season_key in title_lower or any(tag in title_lower for tag in season_values):
                                for tag in season_values:
                                    tags.append(tag)
                        
                        # Create a build entry
                        build_data = {
                            "title": title,
                            "url": full_url,
                            "class": class_name,
                            "difficulty": difficulty_text,
                            "tags": tags,
                            "equipment": []  # Will be populated later
                        }
                        
                        # Avoid duplicates
                        if any(b["url"] == full_url for b in builds):
                            logger.info(f"Skipping duplicate build: {title} ({full_url})")
                        else:
                            builds.append(build_data)
                    
                    # If we found builds with this selector, we can break
                    if builds:
                        break
            
            logger.info(f"Found {len(builds)} builds using Selenium")
            return builds if builds else self._get_build_list_fallback()
            
        except Exception as e:
            logger.error(f"Error fetching build list with Selenium: {e}")
            return self._get_build_list_fallback()
    
    # BeautifulSoup method removed as we're focusing solely on Selenium implementation
    
    def _get_build_list_fallback(self) -> List[Dict[str, Any]]:
        """
        Return a predefined list of known builds as a fallback.
        
        Returns:
            A list of dictionaries containing build information for known builds.
        """
        logger.info("Using fallback build list")
        
        # Our predefined list of known builds
        known_builds = [
            {
                "title": "Penetrating Shot Rogue Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/penetrating-shot-rogue-guide",
                "class": "Rogue",
                "difficulty": "High",
                "tags": ["ranged", "aoe"],
                "equipment": []
            },
            # ... (other builds from the previous implementation)
            {
                "title": "Pulverize Druid Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/pulverize-druid-guide",
                "class": "Druid",
                "difficulty": "Medium",
                "tags": ["melee", "aoe"],
                "equipment": []
            }
        ]
        
        return known_builds

    def get_build_equipment(self, build_url: str) -> List[Dict[str, str]]:
        """
        Extract equipment information from a build page.
        
        Args:
            build_url: The URL of the build page.
            
        Returns:
            A list of dictionaries containing equipment information.
        """
        logger.info(f"Fetching equipment from {build_url}")
        
        try:
            return self._get_build_equipment_selenium(build_url, KNOWN_UNIQUES)
        except Exception as e:
            logger.error(f"Error fetching build equipment: {e}")
            return []
    
    def _get_build_equipment_selenium(self, build_url: str, known_uniques: List[str] = None) -> List[Dict[str, str]]:
        """
        Extract equipment information from a build page using Selenium.
        
        Args:
            build_url: The URL of the build page.
            known_uniques: Optional list of known unique items to look for. If None, uses the global KNOWN_UNIQUES list.
            
        Returns:
            A list of dictionaries containing equipment information.
        """
        # Use the global KNOWN_UNIQUES list if none provided
        if known_uniques is None:
            known_uniques = KNOWN_UNIQUES
        logger.info(f"Using Selenium to fetch equipment from {build_url}")
        
        try:
            # Initialize the driver if not already done
            if not self.driver:
                self.driver = self._init_selenium_driver()
                if not self.driver:
                    raise Exception("Failed to initialize Selenium WebDriver")
            
            # Navigate to the build page
            self.driver.get(build_url)
            
            # Wait for the page to load
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Get the page source after JavaScript has loaded the content
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Initialize equipment list
            equipment = []
            
            # 1. Look for structured equipment sections
            equipment_sections = soup.select(".equipment-item, .d4-item, .d4-gear-item, .item-card, .gear")
            for item in equipment_sections:
                item_name_elem = item.select_one(".item-name, .gear-name, h3, strong, .name")
                item_name = item_name_elem.text.strip() if item_name_elem else "Unknown Item"
                
                item_type_elem = item.select_one(".item-type, .gear-type, .item-slot, .slot")
                item_type = item_type_elem.text.strip() if item_type_elem else "Unknown Type"
                
                # Check if it's a unique/legendary item
                is_unique = False
                if item.get('class'):
                    is_unique = any(unique_term in item.get('class').lower() for unique_term in ['unique', 'legendary', 'mythic'])
                elif item_name_elem and item_name_elem.get('class'):
                    is_unique = any(unique_term in item_name_elem.get('class').lower() for unique_term in ['unique', 'legendary', 'mythic'])
                
                # Also check if name matches any known unique
                if not is_unique:
                    is_unique = any(unique_name.lower() in item_name.lower() for unique_name in known_uniques)
                
                equipment.append({
                    "name": item_name,
                    "type": item_type,
                    "is_unique": is_unique
                })
            
            # 2. Extract text content for analysis
            # Get all text from the page
            all_text = soup.get_text(" ")
            
            # 3. Find mentions of known unique items in the text
            for unique_item in known_uniques:
                if unique_item in all_text:
                    # Check if we already found this item
                    if not any(item['name'] == unique_item for item in equipment):
                        equipment.append({
                            "name": unique_item,
                            "type": "Unique/Legendary",
                            "is_unique": True
                        })
            
            # 4. Extract text from likely content areas
            content_sections = soup.select(".content, .guide-content, article, .build-guide, main")
            paragraphs = []
            
            # If we found content sections, use those
            if content_sections:
                for section in content_sections:
                    paragraphs.extend(section.find_all(['p', 'li', 'div', 'h3', 'h4', 'span']))
            # Otherwise, get all paragraphs and list items
            else:
                paragraphs = soup.find_all(['p', 'li', 'div', 'h3', 'h4', 'span'])
            
            # 5. Advanced pattern matching for item detection
            text_blocks = [p.get_text() for p in paragraphs]
            for block in text_blocks:
                # Look for item-like patterns
                # Pattern 1: Capitalized phrases that might be item names followed by verbs
                potential_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})\s+(?:provides|gives|offers|helps|grants|is)', block)
                
                # Pattern 2: Item references like "X is best in slot" or "X is optional"
                bos_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})\s+(?:is best in slot|is mandatory|is optional)', block)
                potential_matches.extend(bos_matches)
                
                # Pattern 3: "Pick up X for..."
                pickup_matches = re.findall(r'(?:Pick up|Use|Equip)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})\s+for', block)
                potential_matches.extend(pickup_matches)
                
                for match in potential_matches:
                    # Filter out common non-item terms
                    if (len(match) > 3 and 
                        not match in ['This', 'The', 'These', 'Those', 'That', 'Each', 'Every', 'Some', 'Your', 'Their'] and
                        not any(item['name'] == match for item in equipment)):
                        equipment.append({
                            "name": match,
                            "type": "Unique/Legendary (Detected)",
                            "is_unique": True
                        })
            
            logger.info(f"Found {len(equipment)} equipment items using Selenium")
            return equipment
        
        except Exception as e:
            logger.error(f"Error fetching build equipment with Selenium: {e}")
            return []

    def scrape_all_builds(self) -> List[Dict[str, Any]]:
        """
        Scrape all builds and their equipment.
        
        Returns:
            A list of dictionaries containing build and equipment information.
        """
        # Check if we have cached data
        if os.path.exists(self.builds_data_file):
            try:
                with open(self.builds_data_file, 'r', encoding='utf-8') as f:
                    builds = json.load(f)
                    logger.info(f"Loaded {len(builds)} builds from cache")
                    return builds
            except Exception as e:
                logger.error(f"Error loading cached data: {e}")
        
        # Fetch new data
        builds = self.get_build_list()
        
        # For each build, get its equipment
        for i, build in enumerate(builds):
            logger.info(f"Processing build {i+1}/{len(builds)}: {build['title']}")
            build['equipment'] = self.get_build_equipment(build['url'])
            
            # Be nice to the server
            time.sleep(1)
        
        # Save to cache
        try:
            with open(self.builds_data_file, 'w', encoding='utf-8') as f:
                json.dump(builds, f, indent=2)
                logger.info(f"Saved {len(builds)} builds to cache")
        except Exception as e:
            logger.error(f"Error saving data to cache: {e}")
        
        return builds

    def search_builds_by_equipment(self, equipment_name: str) -> List[Dict[str, Any]]:
        """
        Search for builds that use a specific piece of equipment.
        
        Args:
            equipment_name: The name of the equipment to search for.
            
        Returns:
            A list of builds that use the specified equipment.
        """
        builds = self.scrape_all_builds()
        equipment_name = equipment_name.lower()
        
        matching_builds = []
        for build in builds:
            for item in build.get('equipment', []):
                if equipment_name in item.get('name', '').lower():
                    matching_builds.append({
                        "title": build['title'],
                        "url": build['url'],
                        "class": build['class'],
                        "difficulty": build.get('difficulty', 'Unknown'),
                        "matched_item": item['name']
                    })
                    break
        
        logger.info(f"Found {len(matching_builds)} builds matching '{equipment_name}'")
        return matching_builds

def save_all_builds(output_file: str = "all_builds.json") -> list[dict]:
    """
    Extract all builds from MaxRoll and save to a JSON file.

    Args:
        output_file (str): The file to save the builds data to.

    Returns:
        list[dict]: A list of dictionaries containing build information.
    """
    try:
        scraper = Scraper()
        builds = scraper.get_build_list()
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(builds, f, indent=2)
        logger.info(f"Saved {len(builds)} builds to {output_file}")
        return builds
    except Exception as e:
        logger.error(f"Failed to save builds: {e}")
        raise

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Diablo 4 Build Scraper")
    parser.add_argument("--get-all-builds", action="store_true", help="Extract all builds and save to JSON")
    parser.add_argument("--output", default="all_builds.json", help="Output file for builds data")
    parser.add_argument("--search", help="Search for builds using a specific piece of equipment")
    
    args = parser.parse_args()
    
    if args.get_all_builds:
        builds = save_all_builds(args.output)
        print(f"Extracted {len(builds)} builds and saved to {args.output}")
    
    elif args.search:
        scraper = Scraper()
        results = scraper.search_builds_by_equipment(args.search)
        print(json.dumps(results, indent=2))
    
    else:
        # No arguments provided, show usage
        parser.print_help()
