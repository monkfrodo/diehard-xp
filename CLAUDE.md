# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Diehard XP is an experience tracking system for the **Diehard** guild on **Luminera** (Tibia MMORPG). It scrapes XP data from external sources and displays rankings via a static web page hosted on GitHub Pages.

## Development Commands

```bash
# Install Python dependencies
pip install requests beautifulsoup4

# Run the scraper locally
python scraper/buscar_dados.py

# Serve the site locally
python -m http.server 8000
```

## Architecture

### Data Flow
1. **Scraper** (`scraper/buscar_dados.py`) fetches data from two sources:
   - **TibiaData API**: Guild member list, vocations, and levels
   - **GuildStats.eu**: XP data (yesterday, 7-day, 30-day)
2. Outputs JSON files to `dados/`:
   - `ranking.json`: Full ranking data with all periods
   - `status.json`: Execution status and validation info
   - `debug_guildstats.html`: Raw HTML for debugging
3. **Frontend** (`index.html`) is a single-file static page that loads `dados/ranking.json` and renders the UI

### Scraper Retry Logic
The scraper implements automatic retry (up to 36 attempts, 5-minute intervals) because GuildStats.eu updates asynchronously. It waits until at least 10 members have positive XP for "yesterday" before considering data valid.

### GitHub Actions
Runs daily at 7:00 AM Brasília (10:00 UTC) via `.github/workflows/atualizar.yml`. The workflow has a 210-minute timeout to accommodate the retry logic.

### Extras System
Players outside the guild can be tracked by adding them to `dados/extras.json`. The scraper fetches their data individually from GuildStats character pages.

## Key Files

- `index.html`: Complete frontend (HTML/CSS/JS) - uses html2canvas for screenshot generation
- `scraper/buscar_dados.py`: Python scraper with retry logic
- `dados/extras.json`: Manual list of non-guild players to track
