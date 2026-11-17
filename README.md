# League History

Personal archive of a fantasy football league, 2018 through the current season. Weekly matchups are stored as JSON and published as a static site with owner profiles, career/season tables, and league-wide leaderboards.

The site lives in `docs/` and is meant to be served with GitHub Pages (`main` branch, `/docs` folder).

## What’s on the site

- **Players** — Active vs legacy rosters, search, and a profile for each owner (record, points, season-by-season table).
- **Stats** — This-season or all-time leaders (points, records, blowouts, streaks, and oddities). Expand a row to see the next five in that category. Click the avatar/name to open a profile; click the rest of the row to expand.
- **Theme** — Dark mode by default, with a toggle that persists in the browser.

Sleeper handles and older first-name dumps are merged into one identity per owner in `build_site_data.py` (for example David / Sauuuuucy).

## Layout

```
data/<year>/week-N.json   parsed matchups
docs/                     GitHub Pages site
docs/data/league.json     aggregated stats the site reads
parse_week.py             Sleeper-style weekly paste → JSON
parse_schedules.py        older per-player schedule dumps → weekly JSON
build_site_data.py        weekly JSON → docs/data/league.json
```

## Update a week

1. Save a Sleeper matchup paste as `data/<year>/week-N.txt`.
2. Parse it:

   ```bash
   python3 parse_week.py data/2026/week-11.txt
   ```

3. Rebuild the site payload:

   ```bash
   python3 build_site_data.py
   ```

4. Commit `data/` and `docs/data/league.json`, then push `main`. Pages republishes from `docs/`.

Older ESPN-style per-player schedules (one `.txt` per owner in a season folder) are converted with:

```bash
python3 parse_schedules.py data/2024
```

## Preview locally

```bash
python3 -m http.server 8765 --directory docs
```

Then open [http://127.0.0.1:8765/](http://127.0.0.1:8765/).
