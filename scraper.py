import requests
from bs4 import BeautifulSoup
import json
import logging
import os
import time
import argparse
import re
from typing import Dict, List, Any, Optional
from item_translator import ItemTranslator

# Platform detection for ChromeDriver path
import platform

# Default to None for automatic detection
CHROMEDRIVER_PATH = None

# Use hardcoded path only on macOS ARM
if platform.system() == "Darwin" and platform.machine() == "arm64":
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
        # Internal cache file for the scraper (different from the app's all_builds.json output file)
        self.builds_data_file = "scraper_cache.json"
        self.driver = None
        
        # Initialize item translator for Chinese name support
        self.translator = ItemTranslator()
    
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
            chrome_options.add_argument("--log-level=3")  # Only show fatal errors
            chrome_options.add_argument("--silent")
            chrome_options.add_argument("--disable-logging")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--enable-unsafe-swiftshader")  # Address WebGL warnings
            chrome_options.add_argument(f"user-agent={self.headers['User-Agent']}")
            
            # Suppress console logging
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            
            # Set up Chrome driver based on platform
            if CHROMEDRIVER_PATH:
                # Use manually specified path for macOS ARM
                service = Service(executable_path=CHROMEDRIVER_PATH)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                # Use WebDriver Manager for automatic driver detection
                driver = webdriver.Chrome(options=chrome_options)
            
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
            # Initialize WebDriver
            driver = self._init_selenium_driver()
            if not driver:
                return []
                
            # Navigate to the build page
            driver.get(build_url)
            
            # Wait for the page to load
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                )
            except TimeoutException:
                logger.error(f"Timeout waiting for page to load: {build_url}")
                driver.quit()
                return []
            
            # Get the page source and parse with BeautifulSoup
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Initialize equipment list
            equipment = []
            
            # Try a more direct approach to find the unique items in the Great Uniques section
            # This is based on the HTML structure seen in the screenshot
            great_uniques_text = "Great Uniques for this build"
            
            # Look for the exact text in any element
            great_uniques_elements = [elem for elem in soup.find_all() if elem.string and great_uniques_text in elem.string]
            
            if great_uniques_elements:
                logger.info(f"Found {len(great_uniques_elements)} Great Uniques sections using direct search")
                
                for section in great_uniques_elements:
                    logger.info(f"Processing Great Uniques section: {section.text.strip()}")
                    
                    # Try to find the ordered list that follows this section
                    # First, look at parent elements to find the container
                    parent = section.parent
                    while parent and parent.name not in ['article', 'section', 'div', 'body', 'html']:
                        parent = parent.parent
                    
                    if parent:
                        # Look for all ordered lists in this container
                        ordered_lists = parent.find_all('ol')
                        for ol in ordered_lists:
                            # Check if this list is after our section
                            if ol.sourceline > section.sourceline:
                                logger.info(f"Found ordered list with {len(ol.find_all('li'))} items")
                                for item in ol.find_all('li'):
                                    # Extract the item text and clean it up
                                    item_text = item.text.strip()
                                    logger.info(f"Processing list item: {item_text}")
                                    
                                    # For these specific items, we know they're unique items
                                    # So we can directly create equipment entries
                                    # The item text might not have the number prefix if it's extracted directly from the HTML
                                    # So we'll handle both cases
                                    match = re.match(r'(?:\d+\.\s+)?(.+)', item_text)
                                    if match:
                                        item_name = match.group(1).strip()
                                        # Remove any invisible characters that might be present
                                        item_name = re.sub(r'[\u200B-\u200F\uFEFF]', '', item_name)
                                        # Determine item type based on name
                                        item_type = "Unique"
                                        if "rod" in item_name.lower():
                                            item_type = "Weapon"
                                        elif "harmony" in item_name.lower():
                                            item_type = "Weapon"
                                        elif "ring" in item_name.lower() or "signet" in item_name.lower():
                                            item_type = "Jewelry"
                                        elif "mantle" in item_name.lower() or "embrace" in item_name.lower():
                                            item_type = "Armor"
                                            
                                        # Check if this item is already in the equipment list to avoid duplicates
                                        if not any(e["name"] == item_name for e in equipment):
                                            equipment_item = {
                                                "name": item_name,
                                                "type": item_type,
                                                "is_unique": True,
                                                "category": "Great Uniques",
                                                "description": item_text
                                            }
                                            equipment.append(equipment_item)
                                break  # Only process the first ordered list after our section
            
            # If we didn't find any equipment using the direct approach, try the more general approach
            if not equipment:
                logger.info("Trying alternative approach to find Great Uniques")
                great_uniques_sections = soup.find_all(['h3', 'h4', 'strong'], string=lambda text: text and 'great uniques' in text.lower())
                
                # If we found Great Uniques sections, prioritize those
                if great_uniques_sections:
                    logger.info(f"Found {len(great_uniques_sections)} Great Uniques sections")
                    
                    for section in great_uniques_sections:
                        section_title = section.text.strip()
                        logger.info(f"Processing Great Uniques section: {section_title}")
                        
                        # Process the Great Uniques section
                        current = getattr(section, 'next_sibling', None)
                        
                        # Find the next list element
                        while current and current.name not in ['ul', 'ol', 'h1', 'h2', 'h3']:
                            current = getattr(current, 'next_sibling', None)
                        
                        # Process the list if found
                        if current and current.name in ['ul', 'ol']:
                            logger.info(f"Found list in Great Uniques section with {len(current.find_all('li'))} items")
                            for item in current.find_all('li'):
                                self._process_equipment_item(item.text.strip(), "Great Uniques", known_uniques, equipment)
            
            # Next, look for Legendaries & Uniques sections
            legendaries_uniques_sections = soup.find_all(['h2', 'h3'], string=lambda text: text and ('legendaries' in text.lower() or 'uniques' in text.lower()))
            
            # If we found Legendaries & Uniques sections, process those
            if legendaries_uniques_sections:
                logger.info(f"Found {len(legendaries_uniques_sections)} Legendaries & Uniques sections")
                
                for section in legendaries_uniques_sections:
                    section_title = section.text.strip()
                    logger.info(f"Processing priority section: {section_title}")
                    
                    # Process the main Legendaries & Uniques section
                    current = getattr(section, 'next_sibling', None)
                    while current and current.name not in ['h1', 'h2']:
                        if current.name in ['ul', 'ol']:
                            for item in current.find_all('li'):
                                self._process_equipment_item(item.text.strip(), section_title, known_uniques, equipment)
                        elif current.name == 'p' and (current.find('strong') or any(unique.lower() in current.text.lower() for unique in known_uniques)):
                            self._process_equipment_item(current.text.strip(), section_title, known_uniques, equipment)
                        current = getattr(current, 'next_sibling', None)
            
            # If we didn't find any equipment yet, look for other equipment sections
            if not equipment:
                logger.info("No equipment found in priority sections, looking for other equipment sections")
                equipment_sections = soup.find_all(['h2', 'h3'], string=lambda text: text and any(keyword in text.lower() for keyword in ['gear', 'equipment', 'items', 'jackpot']))
                
                for section in equipment_sections:
                    section_title = section.text.strip()
                    logger.info(f"Found equipment section: {section_title}")
                    
                    # Get the content following this section header
                    current = getattr(section, 'next_sibling', None)
                    
                    # Collect elements until we hit another header or run out of siblings
                    while current and current.name not in ['h1', 'h2', 'h3']:
                        if current.name in ['ul', 'ol']:
                            for item in current.find_all('li'):
                                self._process_equipment_item(item.text.strip(), section_title, known_uniques, equipment)
                        elif current.name == 'p' and (current.find('strong') or any(unique.lower() in current.text.lower() for unique in known_uniques)):
                            self._process_equipment_item(current.text.strip(), section_title, known_uniques, equipment)
                        current = getattr(current, 'next_sibling', None)
            
            # Clean up
            driver.quit()
            
            logger.info(f"Found {len(equipment)} equipment items using Selenium")
            return equipment
        
        except Exception as e:
            logger.error(f"Error fetching build equipment with Selenium: {e}")
            return []
            
    def _process_equipment_item(self, item_text: str, section_title: str, known_uniques: List[str], equipment: List[Dict[str, str]]) -> None:
        """
        Process a potential equipment item text and add it to the equipment list if valid.
        
        Args:
            item_text: The text containing potential equipment information
            section_title: The title of the section this item was found in
            known_uniques: List of known unique items to check against
            equipment: The equipment list to add to
        """
        # Check if this contains a known unique item
        item_name = "Unknown"
        item_type = "Unknown"
        is_unique = False
        
        # First check against our known uniques list
        for unique in known_uniques:
            if unique.lower() in item_text.lower():
                item_name = unique
                item_type = "Unique/Legendary"
                is_unique = True
                break
        
        # If we didn't find a known unique, try to extract the item name
        if item_name == "Unknown":
            # Check for numbered list format like "1. Item Name" or "1. Item Name (description)"
            # This pattern is common in the "Great Uniques for this build" section
            numbered_match = re.match(r'\d+\.\s+([A-Z][^\(\)\[\]\{\}\d\n]*?)(?:\s+\(|$|\s+\-)', item_text)
            if numbered_match:
                item_name = numbered_match.group(1).strip()
            else:
                # Look for specific item name patterns
                # Pattern 1: Full item name with prepositions (e.g., "Rod of Kepeleke", "Ring of the Midnight Sun")
                full_item_match = re.search(r'([A-Z][a-z]+(?:\'s|\s+of|\s+the|\s+[A-Z][a-z]+){1,4})', item_text)
                if full_item_match:
                    item_name = full_item_match.group(1).strip()
                else:
                    # Pattern 2: Simple capitalized item name (e.g., "Harmony of Ebewaka")
                    capitalized_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4})', item_text)
                    if capitalized_match:
                        item_name = capitalized_match.group(1).strip()
            
            # Clean up item name - remove trailing punctuation
            if item_name != "Unknown":
                item_name = re.sub(r'[\.,:;\s]+$', '', item_name)
            
            # Try to determine item type based on context
            if "aspect" in item_text.lower() or "aspect's" in item_text.lower():
                item_type = "Legendary Aspect"
            elif "unique" in section_title.lower() or "uniques" in section_title.lower() or "great uniques" in section_title.lower():
                item_type = "Unique"
                is_unique = True
            elif any(weapon_type in item_text.lower() for weapon_type in ["sword", "axe", "mace", "staff", "wand", "bow", "crossbow", "dagger", "rod"]):
                item_type = "Weapon"
            elif any(armor_type in item_text.lower() for armor_type in ["helm", "chest", "gloves", "boots", "pants", "shoulders", "mantle"]):
                item_type = "Armor"
            elif any(jewelry_type in item_text.lower() for jewelry_type in ["ring", "amulet", "necklace", "signet", "embrace"]):
                item_type = "Jewelry"
        
        # Determine category based on section title
        category = "Unknown"
        if "must-have" in section_title.lower():
            category = "Must Have"
        elif "nice-to-have" in section_title.lower():
            category = "Nice to Have"
        elif "great uniques" in section_title.lower():
            category = "Great Uniques"
        elif "jackpot" in section_title.lower():
            category = "Jackpot"
        elif "build-defining" in section_title.lower():
            category = "Build Defining"
        elif "legendaries & uniques" in section_title.lower():
            category = "Legendaries & Uniques"
        else:
            category = section_title
        
        # Filter out common non-item terms that might be mistakenly extracted
        common_terms = ["This", "The", "These", "Those", "That", "Each", "Every", "Some", "Your", "Their", 
                      "Build", "Best", "Alternative", "Endgame", "Leveling", "Rock Splitter Thorns", "Thrash"]
        if item_name in common_terms:
            return
        
        # Filter out items that are too short or likely not actual items
        if item_name != "Unknown" and len(item_name) > 3 and not item_name.startswith("In the") and not item_name.startswith("With the") and not item_name.startswith("Pit"):
            # Check if this item is already in the equipment list to avoid duplicates
            if not any(e["name"] == item_name for e in equipment):
                equipment_item = {
                    "name": item_name,
                    "type": item_type,
                    "is_unique": is_unique,
                    "category": category,
                    "description": item_text
                }
                equipment.append(equipment_item)

    def scrape_all_builds(self) -> List[Dict[str, Any]]:
        """
        Scrape all builds and their equipment.
        
{{ ... }}
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

    def get_equipment_for_builds(self, builds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Get equipment data for a list of builds.
        
        Args:
            builds: A list of build dictionaries.
            
        Returns:
            The same list of builds with equipment data added.
        """
        total_builds = len(builds)
        logger.info(f"Getting equipment for {total_builds} builds")
        
        for i, build in enumerate(builds):
            build_url = build['url']
            logger.info(f"Processing build {i+1}/{total_builds}: {build['title']}")
            
            try:
                # Get equipment for this build
                equipment = self.get_build_equipment(build_url)
                build['equipment'] = equipment
                logger.info(f"Found {len(equipment)} equipment items for build: {build['title']}")
                
                # Sleep briefly to avoid overloading the server
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error getting equipment for build {build['title']}: {e}")
                build['equipment'] = []
        
        return builds
    
    def _load_builds(self) -> List[Dict[str, Any]]:
        """Load builds from the JSON file.
        
        Returns:
            A list of builds.
        """
        try:
            with open("all_builds.json", 'r') as f:
                builds = json.load(f)
            logger.info(f"Loaded {len(builds)} builds from all_builds.json")
            return builds
        except (FileNotFoundError, json.JSONDecodeError):
            logger.info("No existing builds file found, fetching builds first")
            builds = self.get_build_list()
            return builds
    
    def search_builds_by_equipment(self, equipment_name: str) -> List[Dict[str, Any]]:
        """Search for builds that use a specific equipment item.
        
        Supports both English and Chinese (Simplified/Traditional) equipment names.
        
        Args:
            equipment_name: The name of the equipment item to search for.
            
        Returns:
            A list of builds that use the specified equipment item.
        """
        builds = self._load_builds()
        if not any('equipment' in build and build['equipment'] for build in builds):
            logger.info("Builds don't have equipment data, fetching equipment first")
            builds = self.get_equipment_for_builds(builds)
            # Save the updated builds data
            with open("all_builds.json", 'w') as f:
                json.dump(builds, f, indent=2)
        
        # Translate Chinese name to English if needed
        equipment_name = self.translator.translate_to_english(equipment_name)
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
                        "matched_item": item['name'],
                        "item_type": item.get('type', 'Unknown'),
                        "is_unique": item.get('is_unique', False),
                        "category": item.get('category', 'Unknown'),
                        "description": item.get('description', '')
                    })
                    break  # Only add each build once
        
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
    def main():
        parser = argparse.ArgumentParser(description="Diablo 4 Build Scraper")
        parser.add_argument("--get-all-builds", action="store_true", help="Get all builds from MaxRoll")
        parser.add_argument("--output", type=str, default="all_builds.json", help="Output file for builds data")
        parser.add_argument("--search", type=str, help="Search for builds that use a specific piece of equipment")
        parser.add_argument("--class", type=str, dest="class_filter", help="Filter builds by class (e.g., Barbarian, Rogue)")
        parser.add_argument("--tags", type=str, help="Filter builds by tags (comma-separated, e.g., endgame,hardcore)")
        parser.add_argument("--get-equipment", action="store_true", help="Get equipment for all builds")
        parser.add_argument("--build-url", type=str, help="URL of a specific build to get equipment for")
        
        args = parser.parse_args()
        
        scraper = Scraper()
        
        if args.get_all_builds:
            builds = scraper.get_build_list()
            with open(args.output, 'w') as f:
                json.dump(builds, f, indent=2)
            print(f"Extracted {len(builds)} builds and saved to {args.output}")
        elif args.get_equipment:
            # Load existing builds or get new ones
            try:
                with open(args.output, 'r') as f:
                    builds = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                logger.info(f"No existing builds file found at {args.output}, fetching builds first")
                builds = scraper.get_build_list()
        
            # Get equipment for each build
            builds_with_equipment = scraper.get_equipment_for_builds(builds)
            with open(args.output, 'w') as f:
                json.dump(builds_with_equipment, f, indent=2)
            print(f"Updated {len(builds_with_equipment)} builds with equipment data and saved to {args.output}")
        elif args.build_url:
            # Get equipment for a specific build URL
            equipment = scraper.get_build_equipment(args.build_url)
            print(f"Found {len(equipment)} equipment items for {args.build_url}:")
            for item in equipment:
                print(f"- {item['name']} ({item['type']}) - {item['category']}")
        elif args.search:
            matching_builds = scraper.search_builds_by_equipment(args.search)
            
            # Apply class filter if specified
            if args.class_filter:
                class_filter_lower = args.class_filter.lower()
                matching_builds = [b for b in matching_builds if b['class'].lower() == class_filter_lower]
                print(f"Filtered by class: {args.class_filter}")
            
            # Apply tags filter if specified
            if args.tags:
                tag_filters = [tag.strip().lower() for tag in args.tags.split(',')]
                original_count = len(matching_builds)
                
                # Load full build data to access tags
                all_builds = scraper._load_builds()
                build_tags_map = {b['url']: b.get('tags', []) for b in all_builds}
                
                # Filter builds that have ALL specified tags
                filtered_builds = []
                for build in matching_builds:
                    build_tags = [tag.lower() for tag in build_tags_map.get(build['url'], [])]
                    if all(tag in build_tags for tag in tag_filters):
                        filtered_builds.append(build)
                
                matching_builds = filtered_builds
                print(f"Filtered by tags: {args.tags} ({original_count} -> {len(matching_builds)} builds)")
            
            print(f"\nFound {len(matching_builds)} builds that use '{args.search}':")
            
            if len(matching_builds) == 0:
                print("No builds found matching the criteria.")
            else:
                print("\nSearch Results:")
                print("-" * 80)
                
                # Group builds by class for better organization
                builds_by_class = {}
                for build in matching_builds:
                    class_name = build['class']
                    if class_name not in builds_by_class:
                        builds_by_class[class_name] = []
                    builds_by_class[class_name].append(build)
                
                # Print builds grouped by class
                for class_name, builds in sorted(builds_by_class.items()):
                    print(f"\n{class_name} Builds ({len(builds)}):")
                    print("-" * 40)
                    
                    for build in builds:
                        print(f"Title: {build['title']}")
                        print(f"URL: {build['url']}")
                        print(f"Difficulty: {build['difficulty']}")
                        print(f"Item: {build['matched_item']} ({build['item_type']})")
                        if build['category'] != 'Unknown':
                            print(f"Category: {build['category']}")
                        if build['description']:
                            print(f"Description: {build['description']}")
                        print("-" * 40)
        else:
            parser.print_help()
            
    main()
