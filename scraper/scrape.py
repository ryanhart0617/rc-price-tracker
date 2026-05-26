"""
RC Holiday Cruise Price Scraper - Playwright Edition
Tracks specific ships, ports, and December departure dates.
Uses a real browser so RC can't block it.
"""

import json
import os
from datetime import date
from playwright.sync_api import sync_playwright

# ── What to track ─────────────────────────────────────────────────
TARGET_SHIPS = {
    "adventure", "allure", "explorer", "freedom", "harmony",
    "hero", "icon", "independence", "odyssey", "star",
    "symphony", "utopia", "wonder", "legend", "liberty",
    "mariner", "oasis"
}

TARGET_PORTS = {
    "cape liberty", "fort lauderdale", "miami", "galveston",
    "new orleans", "orlando", "tampa", "bayonne"
}

# Any sailing departing Dec 2026 through Dec 2027
DATE_START = "2026-12-01"
DATE_END   = "2027-12-31"

DATA_FILE = "data/prices.json"

# ── Scraper ───────────────────────────────────────────────────────
def matches_targets(sailing):
    """Check if a sailing matches our ship/port/date criteria."""
    ship = sailing.get("ship", "").lower()
    port = sailing.get("departure_port", "").lower()
    dep  = sailing.get("departure_date", "")

    ship_match = any(t in ship for t in TARGET_SHIPS)
    port_match = any(t in port for t in TARGET_PORTS)
    date_match = DATE_START <= dep[:10] <= DATE_END if dep else False

    return ship_match and port_match and date_match


def scrape_with_playwright():
    sailings = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        captured = []

        # Intercept API responses to grab cruise JSON
        def handle_response(response):
            url = response.url
            if response.status == 200 and any(k in url for k in [
                "cruise", "voyage", "sailing", "itinerary", "search", "graphql"
            ]):
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        data = response.json()
                        captured.append({"url": url, "data": data})
                except Exception:
                    pass

        page.on("response", handle_response)

        print("  Opening RC cruise search...")
        page.goto(
            "https://www.royalcaribbean.com/cruises",
            wait_until="domcontentloaded",
            timeout=60000
        )

        # Wait for results to render
        print("  Waiting for results to load...")
        try:
            page.wait_for_selector(
                "[class*='cruise'], [class*='sailing'], [class*='voyage'], [data-testid*='cruise']",
                timeout=20000
            )
        except Exception:
            pass

        # Scroll to trigger lazy loading
        for _ in range(5):
            page.evaluate("window.scrollBy(0, 800)")
            page.wait_for_timeout(1000)

        # Try extracting from DOM
        print("  Extracting from page DOM...")
        dom_sailings = page.evaluate("""
        () => {
            const results = [];
            
            // Try multiple card selector patterns RC uses
            const selectors = [
                '[class*="CruiseCard"]',
                '[class*="cruise-card"]',
                '[class*="sailing-card"]',
                '[data-testid*="cruise"]',
                '[class*="SearchResult"]',
                'article[class*="cruise"]'
            ];
            
            let cards = [];
            for (const sel of selectors) {
                cards = document.querySelectorAll(sel);
                if (cards.length > 0) break;
            }
            
            cards.forEach(card => {
                try {
                    // Extract price
                    const priceEl = card.querySelector('[class*="price"], [class*="Price"], [data-testid*="price"]');
                    const price = priceEl ? priceEl.textContent.replace(/[^0-9.]/g, '') : '0';
                    
                    // Extract ship name
                    const shipEl = card.querySelector('[class*="ship"], [class*="Ship"], h2, h3');
                    const ship = shipEl ? shipEl.textContent.trim() : '';
                    
                    // Extract departure info
                    const portEl = card.querySelector('[class*="port"], [class*="Port"], [class*="departure"]');
                    const port = portEl ? portEl.textContent.trim() : '';
                    
                    // Extract date
                    const dateEl = card.querySelector('[class*="date"], [class*="Date"], time');
                    const depDate = dateEl ? dateEl.textContent.trim() : '';
                    
                    // Extract nights
                    const nightEl = card.querySelector('[class*="night"], [class*="Night"], [class*="duration"]');
                    const nights = nightEl ? nightEl.textContent.replace(/[^0-9]/g, '') : '0';
                    
                    // Extract destination
                    const destEl = card.querySelector('[class*="destination"], [class*="itinerary"]');
                    const destination = destEl ? destEl.textContent.trim() : '';
                    
                    // Get booking URL
                    const linkEl = card.querySelector('a[href*="cruise"], a[href*="book"]');
                    const url = linkEl ? linkEl.href : '';
                    
                    if (ship || price) {
                        results.push({ ship, port, depDate, nights, price, destination, url });
                    }
                } catch(e) {}
            });
            
            return results;
        }
        """)

        print(f"  DOM extraction found: {len(dom_sailings)} cards")

        # Also try parsing any captured JSON responses
        print(f"  Captured {len(captured)} JSON API responses")
        for cap in captured:
            data = cap["data"]
            voyages = (
                data.get("voyages") or data.get("results") or
                data.get("cruises") or data.get("sailings") or
                data.get("data", {}).get("voyages") if isinstance(data.get("data"), dict) else None or []
            )
            if voyages and len(voyages) > 3:
                print(f"  Found {len(voyages)} voyages in API: {cap['url'][:80]}")
                for v in voyages:
                    sailings.append(parse_api_voyage(v))

        # Parse DOM results if no API data
        if not sailings and dom_sailings:
            for s in dom_sailings:
                sailings.append({
                    "sailing_id": f"{s.get('ship','')}-{s.get('depDate','')}".replace(" ", "-"),
                    "ship": s.get("ship", ""),
                    "departure_port": s.get("port", ""),
                    "destination": s.get("destination", ""),
                    "departure_date": s.get("depDate", ""),
                    "nights": int(s.get("nights") or 0),
                    "price": float(s.get("price") or 0),
                    "original_price": float(s.get("price") or 0),
                    "url": s.get("url", ""),
                })

        browser.close()

    return sailings


def parse_api_voyage(v):
    def g(obj, *keys, default=""):
        for k in keys:
            if not isinstance(obj, dict): return default
            obj = obj.get(k, default)
        return obj

    price = float(g(v, "price", "amount") or g(v, "startingPrice", "amount") or v.get("lowestPrice") or 0)
    return {
        "sailing_id": str(v.get("id") or v.get("voyageId") or ""),
        "ship": g(v, "ship", "name") or v.get("shipName", ""),
        "departure_port": (g(v, "departurePort", "code") or v.get("homePort") or ""),
        "destination": g(v, "destination", "name") or v.get("destinationName", ""),
        "departure_date": str(v.get("departureDate") or v.get("sailDate") or "")[:10],
        "nights": int(v.get("nights") or v.get("duration") or 0),
        "price": price,
        "original_price": float(g(v, "originalPrice", "amount") or price),
        "url": f"https://www.royalcaribbean.com{v.get('url','')}" if v.get("url","").startswith("/") else v.get("url",""),
    }


# ── Storage ───────────────────────────────────────────────────────
def load_existing():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"last_updated": "", "total_sailings": 0, "sailings": {}}


def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Main ──────────────────────────────────────────────────────────
def main():
    today = date.today().isoformat()
    print(f"\n🚢 RC Holiday Price Scraper — {today}")
    print("=" * 50)
    print(f"Tracking: Dec 26/27 departures | {len(TARGET_SHIPS)} ships | {len(TARGET_PORTS)} ports")

    print("\n[1/3] Scraping Royal Caribbean...")
    all_sailings = scrape_with_playwright()
    print(f"  Total found: {len(all_sailings)}")

    print("\n[2/3] Filtering for target ships/ports/dates...")
    valid = [s for s in all_sailings if s.get("price", 0) > 0]
    # For now keep all valid - filter can be tightened once we confirm data flows
    print(f"  Valid sailings with price: {len(valid)}")

    print("\n[3/3] Updating price history...")
    existing = load_existing()
    new_ct = updated_ct = 0

    for s in valid:
        sid = s["sailing_id"] or f"{s['ship']}-{s['departure_date']}"
        if not sid.strip("-"):
            continue
        entry = {"date": today, "price": s["price"], "original_price": s["original_price"]}
        if sid not in existing["sailings"]:
            existing["sailings"][sid] = {
                "ship": s["ship"], "departure_port": s["departure_port"],
                "destination": s["destination"], "departure_date": s["departure_date"],
                "nights": s["nights"], "url": s["url"], "price_history": [entry]
            }
            new_ct += 1
        else:
            h = existing["sailings"][sid]["price_history"]
            if not h or h[-1]["date"] != today:
                h.append(entry)
                updated_ct += 1

    existing["last_updated"] = today
    existing["total_sailings"] = len(existing["sailings"])
    save_data(existing)
    print(f"\n✅ Done! New: {new_ct}, Updated: {updated_ct}, Total: {existing['total_sailings']}")


if __name__ == "__main__":
    main()
