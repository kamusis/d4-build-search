import requests
from bs4 import BeautifulSoup
import json
import os
import time
import logging
import re
import argparse
from typing import Dict, List, Any, Optional

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Scraper:
    """A scraper to extract Diablo 4 build data from MaxRoll.gg."""
    
    def __init__(self, base_url: str = "https://maxroll.gg", use_selenium: bool = True):
        """
        Initialize the scraper.
        
        Args:
            base_url: The base URL for the MaxRoll website.
            use_selenium: Whether to use Selenium for scraping (better for dynamic content).
        """
        self.base_url = base_url
        self.builds_url = f"{base_url}/d4/build-guides"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.builds_data_file = "builds_data.json"
        self.use_selenium = use_selenium
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
            
            # Set up Chrome driver
            service = Service(ChromeDriverManager().install())
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
        
        # Fallback list of known builds in case our scraping methods fail
        known_builds = [
            {
                "title": "Penetrating Shot Rogue Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/penetrating-shot-rogue-guide",
                "class": "Rogue",
                "difficulty": "High",
                "tags": ["ranged", "aoe"],
                "equipment": []
            },
            {
                "title": "Flurry Rogue Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/flurry-rogue-guide",
                "class": "Rogue",
                "difficulty": "Medium",
                "tags": ["melee", "aoe"],
                "equipment": []
            },
            {
                "title": "Twisting Blades Rogue Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/twisting-blades-rogue-guide",
                "class": "Rogue",
                "difficulty": "Medium",
                "tags": ["melee", "aoe"],
                "equipment": []
            },
            {
                "title": "Trap Rogue Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/trap-rogue-guide",
                "class": "Rogue",
                "difficulty": "Medium",
                "tags": ["traps", "control"],
                "equipment": []
            },
            {
                "title": "Siphon Necromancer Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/siphon-necromancer-guide",
                "class": "Necromancer",
                "difficulty": "Medium",
                "tags": ["ranged", "aoe"],
                "equipment": []
            },
            {
                "title": "Bone Spear Necromancer Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/bone-spear-necromancer-guide",
                "class": "Necromancer",
                "difficulty": "Medium",
                "tags": ["ranged", "aoe"],
                "equipment": []
            },
            {
                "title": "Whirlwind Barbarian Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/whirlwind-barbarian-guide", 
                "class": "Barbarian",
                "difficulty": "Low",
                "tags": ["melee", "aoe"],
                "equipment": []
            },
            {
                "title": "Hammer of the Ancients Barbarian Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/hammer-of-the-ancients-barbarian-guide",
                "class": "Barbarian",
                "difficulty": "Low",
                "tags": ["melee", "aoe"],
                "equipment": []
            },
            {
                "title": "Ball Lightning Sorcerer Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/ball-lightning-sorcerer-guide",
                "class": "Sorcerer",
                "difficulty": "Medium",
                "tags": ["ranged", "aoe"],
                "equipment": []
            },
            {
                "title": "Firewall Sorcerer Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/firewall-sorcerer-guide",
                "class": "Sorcerer",
                "difficulty": "Medium",
                "tags": ["ranged", "aoe"],
                "equipment": []
            },
            {
                "title": "Thorns Golem Druid Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/thorns-golem-druid-guide",
                "class": "Druid",
                "difficulty": "Medium",
                "tags": ["pet", "thorns"],
                "equipment": []
            },
            {
                "title": "Pulverize Druid Endgame Build Guide",
                "url": "https://maxroll.gg/d4/build-guides/pulverize-druid-guide",
                "class": "Druid",
                "difficulty": "Medium",
                "tags": ["melee", "aoe"],
                "equipment": []
            }
        ]
        
        try:
            if self.use_selenium:
                return self._get_build_list_selenium()
            else:
                # Try traditional scraping approach
                return self._get_build_list_beautifulsoup()
        except Exception as e:
            logger.error(f"Error fetching build list: {e}")
            # Fall back to known builds if there's an error
            logger.info("Falling back to predefined builds list.")
            return known_builds
    
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
                self.driver = self._init_selenium_driver()
                if not self.driver:
                    raise Exception("Failed to initialize Selenium WebDriver")
            
            # Navigate to the build guides page
            self.driver.get(self.builds_url)
            
            # Wait for the page to load and the build cards to appear
            # We'll try several possible selectors for the build cards
            selectors = [".d4-build-card", ".build-card", ".guide-card", ".guide-item", ".content-card", "article"]
            
            # Wait for at least one of the selectors to appear on the page
            wait = WebDriverWait(self.driver, 10)
            for selector in selectors:
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    logger.info(f"Found build cards with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            # Get the page source after JavaScript has loaded the content
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Try to find build cards with various selectors
            builds = []
            for selector in selectors:
                build_cards = soup.select(selector)
                if build_cards:
                    logger.info(f"Found {len(build_cards)} build cards with selector: {selector}")
                    for card in build_cards:
                        # Try to extract title and link (several possible selectors)
                        title_elem = card.select_one(".title, h2, h3, .card-title, .guide-title, a")
                        if not title_elem:
                            continue
                        
                        title = title_elem.text.strip()
                        # Skip if title is too short or doesn't look like a build guide title
                        if len(title) < 5 or not any(class_name in title.lower() for class_name in ["rogue", "barbarian", "druid", "sorcerer", "necromancer"]):
                            continue
                        
                        link_elem = card.select_one("a")
                        if not link_elem:
                            continue
                        
                        link = link_elem.get("href")
                        if not link or not "/d4/build-guides/" in link:
                            continue
                            
                        full_url = f"{self.base_url}{link}" if link.startswith("/") else link
                        
                        # Extract class name from the title or dedicated element
                        class_elem = card.select_one(".class, .character-class, .build-class")
                        class_name = class_elem.text.strip() if class_elem else "Unknown"
                        
                        # If class name is unknown, try to extract it from the title
                        if class_name == "Unknown":
                            for c in ["Rogue", "Barbarian", "Druid", "Sorcerer", "Necromancer"]:
                                if c.lower() in title.lower():
                                    class_name = c
                                    break
                        
                        # Extract difficulty
                        difficulty_elem = card.select_one(".difficulty, .build-difficulty")
                        difficulty_text = difficulty_elem.text.strip() if difficulty_elem else "Medium"
                        
                        # Extract tags if available
                        tag_elems = card.select(".tag, .build-tag, .content-tag")
                        tags = [tag.text.strip() for tag in tag_elems] if tag_elems else []
                        
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
                        if not any(b["url"] == full_url for b in builds):
                            builds.append(build_data)
                    
                    # If we found builds with this selector, we can break
                    if builds:
                        break
            
            logger.info(f"Found {len(builds)} builds using Selenium")
            return builds if builds else self._get_build_list_fallback()
            
        except Exception as e:
            logger.error(f"Error fetching build list with Selenium: {e}")
            return self._get_build_list_fallback()
    
    def _get_build_list_beautifulsoup(self) -> List[Dict[str, Any]]:
        """
        Get the list of all builds using BeautifulSoup (this may not work for JS-loaded content).
        
        Returns:
            A list of dictionaries containing build information.
        """
        logger.info("Using BeautifulSoup to fetch build list")
        
        try:
            # Try to extract data from the page structure
            response = requests.get(self.builds_url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try different selector patterns that might be used on the site
            selectors = [".d4-build-card", ".build-card", ".guide-card", "article", ".content-card"]
            
            builds = []
            for selector in selectors:
                build_cards = soup.select(selector)
                if build_cards:
                    logger.info(f"Found {len(build_cards)} build cards with selector: {selector}")
                    for card in build_cards:
                        # Process each card similar to the Selenium method
                        # ... (similar extraction logic)
                        title_elem = card.select_one(".title, h2, h3, .card-title, .guide-title, a")
                        if not title_elem:
                            continue
                        
                        title = title_elem.text.strip()
                        link_elem = card.select_one("a")
                        if not link_elem:
                            continue
                        
                        link = link_elem.get("href")
                        full_url = f"{self.base_url}{link}" if link.startswith("/") else link
                        
                        # Extract class and difficulty
                        class_elem = card.select_one(".class, .character-class, .build-class")
                        class_name = class_elem.text.strip() if class_elem else "Unknown"
                        
                        difficulty_elem = card.select_one(".difficulty, .build-difficulty")
                        difficulty_text = difficulty_elem.text.strip() if difficulty_elem else "Unknown"
                        
                        # Extract tags if available
                        tag_elems = card.select(".tag, .build-tag, .content-tag")
                        tags = [tag.text.strip() for tag in tag_elems] if tag_elems else []
                        
                        builds.append({
                            "title": title,
                            "url": full_url,
                            "class": class_name,
                            "difficulty": difficulty_text,
                            "tags": tags,
                            "equipment": []  # Will be populated later
                        })
                    
                    # If we found builds with this selector, we can break
                    if builds:
                        break
            
            logger.info(f"Found {len(builds)} builds using BeautifulSoup")
            return builds if builds else self._get_build_list_fallback()
            
        except Exception as e:
            logger.error(f"Error fetching build list with BeautifulSoup: {e}")
            return self._get_build_list_fallback()
    
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
        
        # Compile a list of known unique items in Diablo 4
        # This list can be expanded over time
        known_uniques = [
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
        
        try:
            if self.use_selenium:
                return self._get_build_equipment_selenium(build_url, known_uniques)
            else:
                return self._get_build_equipment_beautifulsoup(build_url, known_uniques)
        except Exception as e:
            logger.error(f"Error fetching build equipment: {e}")
            return []
    
    def _get_build_equipment_selenium(self, build_url: str, known_uniques: List[str]) -> List[Dict[str, str]]:
        """
        Extract equipment information from a build page using Selenium.
        
        Args:
            build_url: The URL of the build page.
            known_uniques: List of known unique items to look for.
            
        Returns:
            A list of dictionaries containing equipment information.
        """
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
            return self._get_build_equipment_beautifulsoup(build_url, known_uniques)
    
    def _get_build_equipment_beautifulsoup(self, build_url: str, known_uniques: List[str]) -> List[Dict[str, str]]:
        """
        Extract equipment information from a build page using BeautifulSoup.
        
        Args:
            build_url: The URL of the build page.
            known_uniques: List of known unique items to look for.
            
        Returns:
            A list of dictionaries containing equipment information.
        """
        logger.info(f"Using BeautifulSoup to fetch equipment from {build_url}")
        
        try:
            response = requests.get(build_url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Initialize equipment list
            equipment = []
            
            # Traditional approach - structured HTML elements
            equipment_sections = soup.select(".equipment-item, .d4-item, .d4-gear-item")
            for item in equipment_sections:
                item_name_elem = item.select_one(".item-name, .gear-name, h3, strong")
                item_name = item_name_elem.text.strip() if item_name_elem else "Unknown Item"
                
                item_type_elem = item.select_one(".item-type, .gear-type, .item-slot")
                item_type = item_type_elem.text.strip() if item_type_elem else "Unknown Type"
                
                # Check if it's a unique/legendary item
                is_unique = False
                if item.get('class'):
                    is_unique = 'unique' in item.get('class') or 'legendary' in item.get('class')
                elif item_name_elem and item_name_elem.get('class'):
                    is_unique = 'unique' in item_name_elem.get('class') or 'legendary' in item_name_elem.get('class')
                
                equipment.append({
                    "name": item_name,
                    "type": item_type,
                    "is_unique": is_unique
                })
            
            # New approach - text-based extraction from paragraphs
            # Look for paragraphs that might mention equipment
            paragraphs = soup.find_all(['p', 'li', 'div'])
            
            # Extract text from all elements
            all_text = ' '.join([p.get_text() for p in paragraphs])
            
            # Find mentions of unique items in the text
            for unique_item in known_uniques:
                if unique_item in all_text:
                    # Check if we already found this item
                    if not any(item['name'] == unique_item for item in equipment):
                        equipment.append({
                            "name": unique_item,
                            "type": "Unique/Legendary",
                            "is_unique": True
                        })
            
            # Advanced extraction - search for patterns like "Unique Name provides/gives/offers..."
            # This tries to find unique items even if they're not in our known list
            text_blocks = [p.get_text() for p in paragraphs]
            for block in text_blocks:
                # Look for capitalized terms that might be item names followed by verbs
                potential_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})\s+(?:provides|gives|offers|helps)', block)
                
                for match in potential_matches:
                    # Filter out common non-item terms
                    if (len(match) > 3 and 
                        not match in ['This', 'The', 'These', 'Those', 'That', 'Each', 'Every', 'Some'] and
                        not any(item['name'] == match for item in equipment)):
                        equipment.append({
                            "name": match,
                            "type": "Unique/Legendary (Detected)",
                            "is_unique": True
                        })
            
            logger.info(f"Found {len(equipment)} equipment items using BeautifulSoup")
            return equipment
        
        except Exception as e:
            logger.error(f"Error fetching build equipment with BeautifulSoup: {e}")
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

def save_all_builds(output_file="all_builds.json"):
    """
    Extract all builds from MaxRoll and save to a JSON file.
    
    Args:
        output_file: The file to save the builds data to.
    """
    scraper = Scraper()
    builds = scraper.get_build_list()
    
    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(builds, f, indent=2)
    
    logger.info(f"Saved {len(builds)} builds to {output_file}")
    return builds

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
