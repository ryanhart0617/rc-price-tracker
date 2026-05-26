"""
RC Scraper - Debug version
Takes a screenshot and saves the HTML so we can see what RC actually renders.
"""

import json
import os
import base64
from datetime import date
from playwright.sync_api import sync_playwright

DATA_FILE = "data/prices.json"

def scrape_with_playwright():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        captured_json = []

        def handle_response(response):
            url = response.url
            if response.status == 200:
                ct = response.headers.get("content-type", "")
                size = int(response.headers.get("content-length", 0) or 0)
                if "json" in ct and size > 500:
                    try:
                        data = response.json()
                        captured_json.append({"url": url, "data": data})
                        print(f"  JSON captured: {url[:100]} ({size} bytes)")
                    except Exception:
                        pass

        page.on("response", handle_response)

        print("  Navigating to RC...")
        page.goto(
            "https://www.royalcaribbean.com/cruises",
            wait_until="networkidle",
            timeout=60000
        )

        print("  Waiting extra time for JS to render...")
        page.wait_for_timeout(5000)

        # Scroll to trigger lazy loading
        for i in range(8):
            page.evaluate("window.scrollBy(0, 600)")
            page.wait_for_timeout(800)

        # Save HTML snippet to see structure
        html = page.content()
        
        # Find all class names that might be cruise cards
        classes = page.evaluate("""
        () => {
            const all = document.querySelectorAll('*');
            const found = new Set();
            all.forEach(el => {
                el.classList.forEach(c => {
                    if (/cruise|sailing|voyage|ship|itinerary|card|result/i.test(c)) {
                        found.add(c);
                    }
                });
            });
            return Array.from(found).slice(0, 50);
        }
        """)
        
        print(f"\n  Relevant CSS classes found on page:")
        for c in classes:
            print(f"    .{c}")

        # Try to find any price elements
        prices = page.evaluate("""
        () => {
            const els = document.querySelectorAll('*');
            const found = [];
            els.forEach(el => {
                const txt = el.textContent.trim();
                if (/^\$[\d,]+$/.test(txt) || /^\$[\d,]+ per/.test(txt)) {
                    found.push({
                        tag: el.tagName,
                        class: el.className,
                        text: txt,
                        parent: el.parentElement ? el.parentElement.className : ''
                    });
                }
            });
            return found.slice(0, 10);
        }
        """)
        
        print(f"\n  Price elements found: {len(prices)}")
        for p in prices:
            print(f"    {p['tag']}.{p['class'][:50]} = {p['text']}")

        print(f"\n  Total JSON responses captured: {len(captured_json)}")
        for cap in captured_json:
            print(f"    {cap['url'][:100]}")

        # Try to extract from any captured JSON
        sailings = []
        for cap in captured_json:
            data = cap["data"]
            for key in ["voyages", "results", "cruises", "sailings", "items", "data"]:
                val = data.get(key)
                if isinstance(val, list) and len(val) > 2:
                    print(f"\n  Found {len(val)} items under '{key}' in {cap['url'][:80]}")
                    print(f"  Sample keys: {list(val[0].keys()) if val else 'none'}")
                    sailings.extend(val)
                    break

        browser.close()
        return sailings, captured_json

def load_existing():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"last_updated": "", "total_sailings": 0, "sailings": {}}

def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def main():
    today = date.today().isoformat()
    print(f"\n🚢 RC Debug Scraper — {today}")
    print("=" * 50)

    sailings, captured = scrape_with_playwright()

    print(f"\nTotal raw sailings found: {len(sailings)}")
    if not sailings:
        print("No data found — check class names above to update selectors")
        return

    existing = load_existing()
    # Just save whatever we found for now
    for s in sailings[:5]:
        print(f"  Sample: {s}")

if __name__ == "__main__":
    main()
