import requests
from bs4 import BeautifulSoup

url = "https://diablo4.cc/cn/Unique"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

response = requests.get(url, headers=headers, timeout=30)
response.encoding = 'utf-8'
soup = BeautifulSoup(response.text, 'html.parser')

# Save full HTML
with open('page_structure.html', 'w', encoding='utf-8') as f:
    f.write(soup.prettify())

print("Saved page structure to page_structure.html")

# Find all links
all_links = soup.find_all('a', href=True)
print(f"\nTotal links found: {len(all_links)}")

# Print first 20 links to see the pattern
print("\nFirst 20 links:")
for i, link in enumerate(all_links[:20]):
    print(f"{i+1}. href='{link.get('href')}' text='{link.get_text(strip=True)[:50]}'")

# Try to find item cards or containers
print("\n\nLooking for item containers...")
cards = soup.find_all('div', class_=lambda x: x and 'card' in x.lower())
print(f"Found {len(cards)} card divs")

# Check for any data attributes
print("\n\nChecking for data attributes...")
data_elements = soup.find_all(attrs=lambda x: any(k.startswith('data-') for k in (x or {})))
print(f"Found {len(data_elements)} elements with data attributes")
if data_elements:
    print("First few data elements:")
    for elem in data_elements[:5]:
        print(f"  {elem.name}: {elem.attrs}")
