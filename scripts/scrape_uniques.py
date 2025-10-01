import requests
from bs4 import BeautifulSoup
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_item_names(item_id, headers):
    """Fetch English, Simplified and Traditional Chinese names for an item"""
    try:
        # Fetch all three language versions
        en_url = f"https://diablo4.cc/us/{item_id}"
        cn_url = f"https://diablo4.cc/cn/{item_id}"
        tw_url = f"https://diablo4.cc/tw/{item_id}"
        
        en_name = None
        cn_name = None
        tw_name = None
        
        # Fetch English
        try:
            response = requests.get(en_url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            # Find the item name in the card
            item_link = soup.find('a', class_='item-name')
            if item_link:
                en_name = item_link.get_text(strip=True)
        except:
            pass
        
        # Fetch Simplified Chinese
        try:
            response = requests.get(cn_url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            item_link = soup.find('a', class_='item-name')
            if item_link:
                cn_name = item_link.get_text(strip=True)
        except:
            pass
        
        # Fetch Traditional Chinese
        try:
            response = requests.get(tw_url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            item_link = soup.find('a', class_='item-name')
            if item_link:
                tw_name = item_link.get_text(strip=True)
        except:
            pass
        
        if en_name and cn_name:
            return {
                "english": en_name,
                "simplified": cn_name,
                "traditional": tw_name or cn_name
            }
        
        return None
        
    except Exception as e:
        print(f"Error processing {item_id}: {e}")
        return None

def scrape_diablo4_uniques():
    """Scrape all unique items from diablo4.cc/cn/Unique"""
    url = "https://diablo4.cc/cn/Unique"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all item links with class 'item-name'
        all_links = soup.find_all('a', class_='item-name')
        print(f"Found {len(all_links)} item links")
        
        # Get unique item IDs
        item_ids = set()
        for link in all_links:
            href = link.get('href')
            if href:
                item_ids.add(href)
        
        print(f"Found {len(item_ids)} unique items")
        
        items = []
        
        # Process items with thread pool for faster scraping
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(get_item_names, item_id, headers): item_id for item_id in item_ids}
            
            for i, future in enumerate(as_completed(futures), 1):
                result = future.result()
                if result:
                    items.append(result)
                    print(f"[{i}/{len(item_ids)}] ✓ {result['english']}")
                else:
                    print(f"[{i}/{len(item_ids)}] ✗ Failed")
        
        return items
        
    except Exception as e:
        print(f"Error scraping: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    items = scrape_diablo4_uniques()
    print(f"\nTotal items scraped: {len(items)}")
    
    if items:
        # Sort by English name
        items.sort(key=lambda x: x['english'])
        
        with open('scraped_items.json', 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(items)} items to scraped_items.json")
