# Quick Start Guide

## First Time Setup (5 minutes)

```bash
# 1. Clone and enter directory
cd FantasyTool

# 2. Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Setup Node environment  
cd website
npm install
cd ..

# 4. Generate data and run
./update.sh --dev
```

Visit `http://localhost:4321` to see your site! 🎉

---

## Daily Workflow

### Update Stats and Preview
```bash
./update.sh --dev
```

### Update Stats and Build for Production
```bash
./update.sh --build
```

### Deploy to Cloudflare (Automated)
```bash
git add .
git commit -m "Update data"
git push origin main
# GitHub Actions handles the rest!
```

### Just Generate New Data
```bash
source venv/bin/activate
python scripts/generate_data.py
```

---

## Common Tasks

### Generate Specific Data Only
```bash
python scripts/generate_data.py --players   # Players
python scripts/generate_data.py --defense   # Defense
python scripts/generate_data.py --dst       # DST
python scripts/generate_data.py --kickers   # Kickers
python scripts/generate_data.py --season    # Leagues
```

### Preview Production Build
```bash
cd website
npm run preview
```

### Deploy to Cloudflare Pages
```bash
./update.sh --build
# Then upload website/dist/ folder to Cloudflare Pages
```

---

## File Locations

| What | Where |
|------|-------|
| Python scripts | `scripts/` |
| Generated data | `output/` |
| Website source | `website/src/` |
| Website data | `website/public/data/` |
| Built site | `website/dist/` |

---

## Configuration

### Change League IDs
Edit `scripts/generate_season_stats.py`:
```python
LEAGUES = {
    'dynasty': {'id': 'YOUR_LEAGUE_ID', 'name': 'Dynasty League'},
    'chopped': {'id': 'YOUR_LEAGUE_ID', 'name': 'Chopped League'}
}
```

### Change Scoring
Edit `scripts/core_data.py` - look for `SCORING_PRESETS`

---

## Deployment

See [CLOUDFLARE_DEPLOY.md](./CLOUDFLARE_DEPLOY.md) for full setup guide.

**TL;DR:**
1. Add `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` to GitHub secrets
2. Create Cloudflare Pages project named `fantasy-tool`
3. Push to `main` branch
4. Site auto-updates nightly at 3 AM EST

---

## Troubleshooting

### Script can't find modules
```bash
source venv/bin/activate
```

### Old data showing
```bash
python scripts/generate_data.py
# Then refresh browser
```

### Port 4321 already in use
```bash
# Kill existing process
lsof -ti:4321 | xargs kill -9
# Then try again
./update.sh --dev
```

### GitHub Actions deployment fails
- Check GitHub secrets are set correctly
- Verify Cloudflare project name matches workflow (`fantasy-tool`)
- Review workflow logs at github.com/babenaldt/FantasyLoser/actions

---

## Need More Help?

See [README.md](README.md) for full documentation.
