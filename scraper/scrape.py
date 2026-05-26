"""
Royal Caribbean Price Scraper
==============================
Scrapes sailing prices from Royal Caribbean's internal API and stores
price history in data/prices.json.

How it works:
  1. Calls RC's search API (found by inspecting network requests on royalcaribbean.com)
  2. Filters for US departure ports
  3. Appends today's prices to each sailing's history
  4. Saves updated data/prices.json

If RC changes their API (it happens), open DevTools → Network tab on
royalcaribbean.com → search for cruises → look for an XHR/Fetch request
that returns JSON with voyage data. Update API_URL below.
"""

import requests
import json
import os
import time
from datetime import date

# ── Config ────────────────────────────────────────────────────────
# RC's internal search endpoint (inspect network tab if this breaks)
API_BASE = "https://www.royalcaribbean.com"
SEARCH_URL = f"{API_BASE}/next/api/search/cruise"

US_PORTS = {
    "MIA", "FLL", "GAL", "LAX", "SAN", "SEA", "NOR", "NYC",
    "BOS", "TPA", "JAX", "PTL", "HNL", "BAL", "NWO", "NFK"
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.royalcaribbean.com/cruises",
    "Origin": "https://www.royalcaribbean.com",
}

DATA_FILE = "data/prices.json"


# ── Fetch ─────────────────────────────────────────────────────────
def fetch_page(page=0, size=50):
    """Fetch one page of cruise search results."""
    params = {
        "country": "US",
        "currency": "USD",
        "language": "en",
        "page": page,
        "size": size,
    }
    try:
        resp = requests.get(SEARCH_URL, headers=HEADERS, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        print(f"  HTTP error on page {page}: {e}")
        return None
    except Exception as e:
        print(f"  Error fetching page {page}: {e}")
        return None


def fetch_all_sailings():
    """Paginate through all RC cruise results."""
    all_voyages = []
    page = 0

    while True:
        print(f"  Fetching page {page}...")
        data = fetch_page(page=page)

        if not data:
            break

        # RC's response structure — adjust keys if they change their API
        # Common structures: data['voyages'], data['results'], data['cruises']
        voyages = (
            data.get("voyages")
            or data.get("results")
            or data.get("cruises")
            or data.get("data", {}).get("voyages")
            or []
        )

        if not voyages:
            print(f"  No voyages on page {page}, stopping.")
            break

        all_voyages.extend(voyages)
        print(f"  Got {len(voyages)} voyages (total: {len(all_voyages)})")

        # Check if there are more pages
        total = (
            data.get("total")
            or data.get("totalResults")
            or data.get("pagination", {}).get("total")
            or 0
        )
        if (page + 1) * 50 >= total:
            break

        page += 1
        time.sleep(1.5)  # Be polite to RC's servers

    return all_voyages


# ── Parse ─────────────────────────────────────────────────────────
def parse_voyage(voyage):
    """
    Extract relevant fields from a voyage object.
    RC changes field names occasionally — update mappings here if needed.
    """
    today = date.today().isoformat()

    def get_nested(obj, *keys, default=None):
        for key in keys:
            if not isinstance(obj, dict):
                return default
            obj = obj.get(key, default)
        return obj

    # Try multiple possible field name patterns
    ship = (
        get_nested(voyage, "ship", "name")
        or get_nested(voyage, "shipName")
        or get_nested(voyage, "vessel", "name")
        or "Unknown"
    )

    port_code = (
        get_nested(voyage, "departurePort", "code")
        or get_nested(voyage, "homePort", "code")
        or get_nested(voyage, "embarkPortCode")
        or ""
    ).upper()

    destination = (
        get_nested(voyage, "destination", "name")
        or get_nested(voyage, "destinationName")
        or get_nested(voyage, "region", "name")
        or "Unknown"
    )

    depart_date = (
        get_nested(voyage, "departureDate")
        or get_nested(voyage, "sailDate")
        or get_nested(voyage, "embarkDate")
        or ""
    )

    nights = (
        voyage.get("nights")
        or voyage.get("duration")
        or voyage.get("numberOfNights")
        or 0
    )

    price = (
        get_nested(voyage, "price", "amount")
        or get_nested(voyage, "startingPrice", "amount")
        or get_nested(voyage, "lowestPrice")
        or get_nested(voyage, "priceFrom")
        or 0
    )

    original_price = (
        get_nested(voyage, "originalPrice", "amount")
        or get_nested(voyage, "strikethroughPrice", "amount")
        or get_nested(voyage, "wasPrice")
        or price
    )

    voyage_id = (
        voyage.get("id")
        or voyage.get("voyageId")
        or voyage.get("sailingId")
        or ""
    )

    url_path = (
        voyage.get("url")
        or voyage.get("bookingUrl")
        or ""
    )
    full_url = f"{API_BASE}{url_path}" if url_path.startswith("/") else url_path

    return {
        "sailing_id": str(voyage_id),
        "ship": ship,
        "departure_port": port_code,
        "destination": destination,
        "departure_date": str(depart_date)[:10] if depart_date else "",
        "nights": int(nights) if nights else 0,
        "price": float(price) if price else 0,
        "original_price": float(original_price) if original_price else 0,
        "url": full_url,
        "date_scraped": today,
    }


# ── Storage ───────────────────────────────────────────────────────
def load_existing():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"last_updated": "", "total_sailings": 0, "sailings": {}}


def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved to {DATA_FILE}")


# ── Main ──────────────────────────────────────────────────────────
def main():
    today = date.today().isoformat()
    print(f"\n🚢 RC Price Scraper — {today}")
    print("=" * 50)

    # 1. Fetch
    print("\n[1/3] Fetching sailings from Royal Caribbean...")
    raw_voyages = fetch_all_sailings()
    print(f"  Total fetched: {len(raw_voyages)}")

    # 2. Parse & filter US ports
    print("\n[2/3] Parsing & filtering...")
    parsed = [parse_voyage(v) for v in raw_voyages]
    us_sailings = [s for s in parsed if s["departure_port"] in US_PORTS]
    valid = [s for s in us_sailings if s["price"] > 0 and s["sailing_id"]]
    print(f"  US sailings with price data: {len(valid)}")

    # 3. Merge into history
    print("\n[3/3] Updating price history...")
    existing = load_existing()
    updated = 0
    new_entries = 0

    for s in valid:
        sid = s["sailing_id"]
        today_entry = {"date": today, "price": s["price"], "original_price": s["original_price"]}

        if sid not in existing["sailings"]:
            existing["sailings"][sid] = {
                "ship": s["ship"],
                "departure_port": s["departure_port"],
                "destination": s["destination"],
                "departure_date": s["departure_date"],
                "nights": s["nights"],
                "url": s["url"],
                "price_history": [today_entry],
            }
            new_entries += 1
        else:
            # Update metadata in case ship/port info changed
            existing["sailings"][sid]["ship"] = s["ship"]
            existing["sailings"][sid]["url"] = s["url"] or existing["sailings"][sid]["url"]

            # Avoid duplicate entries for same day
            history = existing["sailings"][sid]["price_history"]
            if not history or history[-1]["date"] != today:
                history.append(today_entry)
                updated += 1

    existing["last_updated"] = today
    existing["total_sailings"] = len(existing["sailings"])

    save_data(existing)

    print(f"\n✅ Done!")
    print(f"   New sailings: {new_entries}")
    print(f"   Updated sailings: {updated}")
    print(f"   Total in database: {existing['total_sailings']}")


if __name__ == "__main__":
    main()
