# 🚢 RC Cruise Price Radar

Track Royal Caribbean cruise prices across all US ports — automatically, every day, for free.

## How It Works

| Piece | What it does | Cost |
|---|---|---|
| **GitHub Actions** | Runs the scraper daily at 5 AM ET | Free |
| **`data/prices.json`** | Stores all price history in the repo | Free |
| **GitHub Pages** | Hosts the dashboard at a public URL | Free |

---

## Setup (one time, ~10 minutes)

### 1. Create the GitHub repo

1. Go to [github.com](https://github.com) → **New repository**
2. Name it something like `rc-price-tracker`
3. Set it to **Public** (required for free GitHub Pages)
4. Click **Create repository**

### 2. Upload all these files

Upload everything from this folder into your new repo, preserving the folder structure:

```
rc-price-tracker/
├── index.html
├── data/
│   └── prices.json
├── scraper/
│   └── scrape.py
└── .github/
    └── workflows/
        └── daily-scrape.yml
```

You can drag-and-drop files directly on GitHub's web UI, or use Git if you're comfortable with it.

### 3. Enable GitHub Pages

1. In your repo → **Settings** → **Pages**
2. Under "Source", select **Deploy from a branch**
3. Branch: `main`, folder: `/ (root)`
4. Click **Save**

After ~1 minute, your dashboard is live at:
`https://YOUR-USERNAME.github.io/rc-price-tracker/`

### 4. Run the scraper for the first time

1. Go to your repo → **Actions** tab
2. Click **Daily RC Price Scrape** in the left sidebar
3. Click **Run workflow** → **Run workflow** (green button)
4. Wait ~1–2 minutes for it to finish
5. Refresh your dashboard — real data will appear!

After this, it runs automatically every morning at 5 AM Eastern.

---

## If the Scraper Breaks

Royal Caribbean occasionally changes their internal API. If you notice prices stop updating:

1. Open [royalcaribbean.com/cruises](https://royalcaribbean.com/cruises) in Chrome
2. Open DevTools (`F12`) → **Network** tab → filter by **Fetch/XHR**
3. Search for cruises on their site
4. Look for a request that returns JSON with voyage/cruise data
5. Copy that URL and update `API_BASE` / `SEARCH_URL` in `scraper/scrape.py`

---

## Dashboard Features

- **Price history chart** — click any sailing card to see its price over time
- **Filter** by departure port, destination, trip length
- **Sort** by lowest price, lowest per-night, or biggest recent drop
- **Trend badges** — see which sailings dropped or rose today
- Automatically reads the latest `data/prices.json` on every page load

---

## Notes

- Prices shown are **per person, double occupancy** (lowest interior cabin), matching what RC displays
- History builds up day by day — after 30 days you'll have a solid trend picture
- The `data/prices.json` file grows slowly (~a few KB per day) and won't hit GitHub's limits for years
