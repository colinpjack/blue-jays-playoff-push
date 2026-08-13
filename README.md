# The Push — Blue Jays playoff dashboard

A GitHub Pages site that tracks the Toronto Blue Jays' playoff chase. It refreshes **every hour** with standings, KPIs, remaining games, injuries, and the other American League clubs in the wild-card mess.

## Enable it on GitHub

1. Create a GitHub repo and push this project (default branch `main` or `master`).
2. In the repo: **Settings → Pages → Build and deployment**
   - Source: **Deploy from a branch**
   - Branch: `main` (or `master`), folder: `/ (root)`
3. In **Settings → Actions → General**, allow GitHub Actions and permit the workflow to read/write contents so it can commit `data.json`.
4. Open **Actions → Update playoff dashboard → Run workflow** once so the first hourly refresh is confirmed.

The public URL will be:

`https://<your-github-username>.github.io/<repo-name>/`

## What updates hourly

A scheduled GitHub Action runs `scripts/fetch_playoff_data.py`, which writes `data.json` from:

- [MLB Stats API](https://statsapi.mlb.com/) — standings, team stats, schedule, probable pitchers, 40-man IL flags
- ESPN’s public injury feed — player status blurbs

If nothing in the race changed that hour, the workflow skips the commit.

## Local refresh

```bash
python3 scripts/fetch_playoff_data.py
```

Then open `index.html` with a local static server (file:// may block `fetch`):

```bash
python3 -m http.server 8080
```

Visit [http://localhost:8080](http://localhost:8080).

## Notes

This is a fan dashboard, not an official MLB or Blue Jays product. Live scores can lag a few minutes behind the ballpark.
