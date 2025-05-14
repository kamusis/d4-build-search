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

### Step 2: Understand the HTML structure of a specific build

From examining the HTML structure of the maxroll.gg/d4/build-guides/penetrating-shot-rogue-guide page, I can see:

