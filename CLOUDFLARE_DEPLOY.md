# Cloudflare Pages Deployment Guide

This guide covers deploying the Fantasy Tool to Cloudflare Pages with automated nightly data updates via GitHub Actions.

## Quick Setup

### 1. Get Cloudflare API Token

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) → Profile → API Tokens
2. Click **Create Token**
3. Use the **Edit Cloudflare Workers** template or create custom token with:
   - Permissions: `Account - Cloudflare Pages - Edit`
   - Account Resources: Include your account
4. Copy the generated token (you'll need it for GitHub secrets)

### 2. Get Cloudflare Account ID

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Select **Workers & Pages**
3. Your Account ID is on the right sidebar
4. Copy the Account ID

### 3. Configure GitHub Repository Secrets

1. Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add:

   **CLOUDFLARE_API_TOKEN**
   - Value: The API token from step 1

   **CLOUDFLARE_ACCOUNT_ID**
   - Value: The Account ID from step 2

### 4. Create Cloudflare Pages Project

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) → **Workers & Pages**
2. Click **Create application** → **Pages** → **Connect to Git**
3. Select your GitHub repository: `babenaldt/FantasyLoser`
4. Configure build settings:
   - **Project name**: `fantasy-tool` (must match `projectName` in `.github/workflows/deploy.yml`)
   - **Production branch**: `main`
   - **Build command**: `npm run build`
   - **Build output directory**: `dist`
   - **Root directory**: `website`
5. Click **Save and Deploy**

### 5. Initial Deployment

Push your changes to trigger the first deployment:

```bash
git add .
git commit -m "Configure Cloudflare Pages deployment"
git push origin main
```

The GitHub Actions workflow will:
1. Generate fresh fantasy data using Python scripts
2. Build the Astro site
3. Deploy to Cloudflare Pages

Monitor progress at: `https://github.com/babenaldt/FantasyLoser/actions`

## How It Works

### GitHub Actions Workflow

The `.github/workflows/deploy.yml` workflow automates everything:

#### Triggers:
- **Push to main**: Auto-deploys when you push changes to `main` branch
- **Nightly schedule**: Runs at 3 AM EST (8 AM UTC) daily to refresh data
- **Manual**: Run via GitHub Actions UI for on-demand updates

#### Jobs:

**1. generate-data**
- Sets up Python 3.11 environment
- Installs dependencies from `requirements.txt`
- Runs `python scripts/generate_data.py --all` to generate all JSON files
- Copies generated JSON to `website/public/data/`
- Uploads data as artifacts for the deploy job

**2. deploy**
- Downloads generated data artifacts
- Sets up Node.js 20 environment
- Installs npm dependencies
- Builds Astro site with `npm run build`
- Deploys `website/dist/` to Cloudflare Pages

### Astro Configuration

The `website/astro.config.mjs` is configured for Cloudflare:

```javascript
import cloudflare from '@astrojs/cloudflare';

export default defineConfig({
  output: 'static',
  adapter: cloudflare({
    mode: 'directory'
  })
});
```

## Manual Deployment

### Option 1: GitHub Actions UI

1. Go to `https://github.com/babenaldt/FantasyLoser/actions`
2. Click **Deploy to Cloudflare Pages** workflow
3. Click **Run workflow** → Select branch `main` → **Run workflow**

### Option 2: Local Build + Manual Upload

```bash
# Generate data locally
source venv/bin/activate
python scripts/generate_data.py --all
cp output/*.json website/public/data/

# Build site
cd website
npm run build

# Deploy via Wrangler CLI (requires @cloudflare/wrangler installed)
npx wrangler pages deploy dist --project-name=fantasy-tool
```

### Option 3: Using update.sh Script

```bash
# Build and preview locally first
./update.sh --build

# Then deploy manually via Cloudflare dashboard or Wrangler CLI
```

## Customizing the Schedule

Edit `.github/workflows/deploy.yml` to change the update frequency:

```yaml
schedule:
  # Daily at 3 AM EST (8 AM UTC)
  - cron: '0 8 * * *'
  
  # Examples:
  # Every 6 hours: '0 */6 * * *'
  # Twice daily (3 AM and 3 PM EST): '0 8,20 * * *'
  # Weekdays only: '0 8 * * 1-5'
```

Cron syntax: `minute hour day month weekday`

## Monitoring Deployments

### GitHub Actions
- View workflow runs: `https://github.com/babenaldt/FantasyLoser/actions`
- Check job logs for data generation and deployment status
- Failed builds will send email notifications (if enabled in GitHub settings)

### Cloudflare Dashboard
- View deployments: `https://dash.cloudflare.com/` → Workers & Pages → fantasy-tool
- See deployment history, build logs, and analytics
- Access your live site URL (e.g., `https://fantasy-tool.pages.dev`)

## Troubleshooting

### Build Fails: "CLOUDFLARE_API_TOKEN not found"
- Verify secrets are set in GitHub repository settings
- Secret names must match exactly: `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`

### Build Fails: Python dependencies
- Check `requirements.txt` is up to date
- Review workflow logs at GitHub Actions page
- May need to update Python version in workflow (currently 3.11)

### Build Fails: npm dependencies
- Ensure `website/package-lock.json` is committed to repository
- Try deleting `node_modules` and running `npm install` locally first

### Data Generation Fails
- Check if Sleeper API is accessible
- Verify league IDs in generated scripts
- Run `python scripts/generate_data.py --all` locally to debug

### Deployment Succeeds but Site Doesn't Update
- Clear browser cache
- Check Cloudflare Pages dashboard for latest deployment time
- Verify JSON files are in `website/public/data/` in the built artifact

### Custom Domain Setup
1. In Cloudflare Pages project → **Custom domains**
2. Click **Set up a custom domain**
3. Enter your domain (e.g., `fantasy.yourdomain.com`)
4. Add the CNAME record to your DNS (if using Cloudflare DNS, this happens automatically)

## Cost

- **Cloudflare Pages**: Free tier includes:
  - 500 builds per month
  - Unlimited bandwidth
  - Unlimited sites
  
- **GitHub Actions**: Free tier includes:
  - 2,000 minutes/month for private repos
  - Unlimited for public repos
  
Both free tiers are more than sufficient for nightly updates (30 builds/month).

## Environment Variables

If you need to add environment variables (e.g., API keys):

### In GitHub Actions:
Add to repository secrets, then reference in workflow:

```yaml
- name: Generate all data files
  env:
    SLEEPER_API_KEY: ${{ secrets.SLEEPER_API_KEY }}
  run: python scripts/generate_data.py --all
```

### In Cloudflare Pages:
1. Go to Cloudflare Pages project → **Settings** → **Environment variables**
2. Add variables for Production/Preview environments
3. Access in Astro via `import.meta.env.VARIABLE_NAME`

## Next Steps

- **Custom Domain**: Set up a custom domain in Cloudflare Pages dashboard
- **Analytics**: Enable Cloudflare Web Analytics for visitor tracking
- **Caching**: Configure cache rules for optimal performance
- **Notifications**: Set up Slack/Discord webhooks for deployment notifications
- **Branch Previews**: Push to feature branches for preview deployments

## Support

- **Cloudflare Pages Docs**: https://developers.cloudflare.com/pages/
- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **Astro Cloudflare Docs**: https://docs.astro.build/en/guides/deploy/cloudflare/
