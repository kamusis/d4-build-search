## Background

The tool should allow users to search for Diablo 4 builds by entering the name of a unique or mythic unique item. The goal is to help players determine whether a specific unique item they have found is used in any recommended builds for the current season, as listed on https://maxroll.gg/d4/build-guides. Since the usefulness of unique items can vary between seasons and not all uniques are viable for builds every season, users need to quickly check if their item is included in any published, up-to-date builds. The backend should maintain a searchable database of builds and their associated unique equipment, enabling efficient equipment-based build lookup.

## Requirements
Develop a Diablo 4 build search tool focused on finding builds that use specific unique or mythic unique equipment. The build data will be sourced from https://maxroll.gg/d4/build-guides. Each build page includes a list of equipment used in that build.

To approach this project:

1. Analyze the HTML structure of the Maxroll build guides overview page to determine how to extract all build titles, permalinks, and relevant metadata.
2. Examine the HTML structure of an individual build page (e.g., https://maxroll.gg/d4/build-guides/penetrating-shot-rogue-guide) to identify how equipment lists are presented and how to extract item information.
3. Design a method to collect and store all builds and their associated equipment locally (e.g., in a JSON file) for efficient searching.

## Working plan

### Step 1: Extract build metadata from the Maxroll build guides overview page

To gather all build titles, permalinks, and relevant metadata, the scraper uses Selenium to automate a headless browser session. It navigates to the Maxroll build guides page, scrolls to the bottom to trigger dynamic loading of all builds, and then parses the fully loaded HTML. The extracted build metadata is saved locally in a JSON file for efficient searching and further processing.

### Step 2: Extract equipment data from build pages

To extract equipment data from individual build pages, we implemented a multi-step approach:

1. **Identify Equipment Sections**: The scraper looks for specific sections in the build page that contain equipment information, prioritizing sections titled "Legendaries & Uniques", "Great Uniques", and "Jackpot Drops".

2. **Extract Equipment Items**: For each identified section, the scraper extracts item names, types (Weapon, Armor, Jewelry, etc.), and categorizes them as unique or legendary based on context.

3. **Handle Special Cases**: Special handling was implemented for:
   - Ordered and unordered lists in "Great Uniques" sections
   - Invisible characters in item names
   - Duplicate items appearing in multiple sections

4. **Store Equipment Data**: Each extracted item is stored with its name, type, category, whether it's unique, and any available description.

5. **Update Build Database**: All builds in the JSON database are updated with their associated equipment, enabling efficient searching by equipment name.

### Step 3: Implement equipment-based build search

With the equipment data extracted and stored, we implemented a search function that allows users to find builds based on equipment names:

1. **Case-Insensitive Search**: The search function performs case-insensitive matching against all equipment names.

2. **Detailed Results**: Search results include comprehensive information about each matching build, including:
   - Build title, URL, and class
   - Difficulty rating
   - Matched item details (name, type, category, description)

3. **Organized Output**: Results are grouped by character class for better readability.

This implementation successfully meets the project requirements, allowing users to quickly find builds that utilize specific unique or legendary items they've found in the game.
