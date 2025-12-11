# Deploy to Cloudflare Pages

This guide will help you deploy your Fantasy Football reports to Cloudflare Pages.

## Setup Steps

### 1. Prepare Your Repository

The `output/` directory contains all the static HTML files that will be published:
- `index.html` - Landing page with links to all reports
- `player_stats_*.html` - Player statistics reports
- `season_stats_*.html` - League season reports

### 2. Create Cloudflare Pages Project

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Click on "Workers & Pages" in the sidebar
3. Click "Create application" → "Pages" → "Connect to Git"
4. Select your GitHub repository: `babenaldt/FantasyLoser`
5. Configure build settings:
   - **Project name**: Choose a name (e.g., `fantasy-football-reports`)
   - **Production branch**: `main`
   - **Build command**: Leave empty (we're using pre-built static files)
   - **Build output directory**: `output`
6. Click "Save and Deploy"

### 3. Automatic Deployments

After initial setup, Cloudflare Pages will automatically deploy whenever you:
1. Push changes to the `main` branch
2. Run your scripts to generate new reports
3. Commit and push the updated `output/` files

### 4. Update Reports Workflow

To update your published reports:

```bash
# Generate new reports
python sleeperadvisor.py --player-stats
python sleeperadvisor.py

# Commit and push to trigger deployment
git add output/
git commit -m "Update reports for week X"
git push
```

Cloudflare will automatically deploy the updates within 1-2 minutes.

### 5. Custom Domain (Optional)

You can add a custom domain in the Cloudflare Pages settings:
1. Go to your Pages project
2. Click "Custom domains"
3. Add your domain and follow DNS setup instructions

### 6. Access Your Reports

Your reports will be available at:
- Production: `https://your-project-name.pages.dev`
- Or your custom domain if configured

## Important Notes

- The `output/` directory is now tracked in git (removed from .gitignore)
- Each deployment creates a unique preview URL
- Production deployments happen on the `main` branch
- You can roll back to previous deployments in the Cloudflare dashboard

## GitHub Actions (Optional)

For automatic report generation on a schedule, you can set up GitHub Actions. Create `.github/workflows/update-reports.yml`:

```yaml
name: Update Fantasy Reports

on:
  schedule:
    - cron: '0 12 * * 2'  # Every Tuesday at noon UTC
  workflow_dispatch:  # Allow manual trigger

jobs:
  update-reports:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Generate reports
        run: |
          python sleeperadvisor.py --player-stats
          python sleeperadvisor.py
      
      - name: Commit and push if changes
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add output/
          git diff --quiet && git diff --staged --quiet || (git commit -m "Auto-update reports" && git push)
```

This will automatically update your reports weekly!
