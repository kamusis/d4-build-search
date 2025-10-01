import json

# Check scraped items
with open('scripts/scraped_items.json', 'r', encoding='utf-8') as f:
    scraped = json.load(f)

# Check final items
with open('all_items.json', 'r', encoding='utf-8') as f:
    final = json.load(f)

print(f"Scraped items count: {len(scraped)}")
print(f"Final items count: {len(final)}")
print(f"\nDifference: {len(scraped) - len(final)} items")

# Check for duplicates in scraped
scraped_names = [item['english'] for item in scraped]
duplicates = [name for name in scraped_names if scraped_names.count(name) > 1]
if duplicates:
    print(f"\nDuplicates found: {set(duplicates)}")
else:
    print("\nNo duplicates in scraped items")

# Find items in scraped but not in final
scraped_set = set(item['english'] for item in scraped)
final_set = set(item['english'] for item in final)
missing = scraped_set - final_set
if missing:
    print(f"\nItems in scraped but not in final ({len(missing)}):")
    for item in sorted(missing):
        print(f"  - {item}")
