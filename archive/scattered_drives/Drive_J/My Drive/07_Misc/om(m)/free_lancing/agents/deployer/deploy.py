#!/usr/bin/env python3
"""
AutoWeb Deployer
==================
Deploys generated static sites to Cloudflare Pages or Netlify.

Usage:
    python deploy.py --site ../output/sites/business-name --platform cloudflare
    python deploy.py --site ../output/sites/business-name --platform netlify
    python deploy.py --list  # List all generated sites ready for deployment
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SCRIPT_DIR = Path(__file__).resolve().parent
SITES_DIR = SCRIPT_DIR.parent / "output" / "sites"


def list_sites():
    """List all generated sites ready for deployment."""
    if not SITES_DIR.exists():
        print("❌ No sites directory found. Run generate.py first.")
        return

    sites = [d for d in SITES_DIR.iterdir() if d.is_dir() and (d / "index.html").exists()]

    if not sites:
        print("⚠️  No generated sites found.")
        return

    print(f"\n📁 Generated Sites ({len(sites)} total):")
    print(f"{'─'*60}")
    for site in sorted(sites):
        size = sum(f.stat().st_size for f in site.rglob("*") if f.is_file())
        print(f"  📄 {site.name}")
        print(f"     Path: {site}")
        print(f"     Size: {size / 1024:.1f} KB")
        print(f"     Preview: file:///{site / 'index.html'}")
        print()


def deploy_cloudflare(site_path: str, project_name: str):
    """Deploy to Cloudflare Pages using Wrangler CLI."""
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")

    if not api_token or api_token == "your_cloudflare_token_here":
        print("❌ Set CLOUDFLARE_API_TOKEN in your .env file")
        print("   Get one at: https://dash.cloudflare.com/profile/api-tokens")
        print("")
        print("   Alternatively, install Wrangler and deploy manually:")
        print(f"   npx wrangler pages deploy {site_path} --project-name {project_name}")
        return

    print(f"🚀 Deploying to Cloudflare Pages: {project_name}")
    print(f"   Source: {site_path}")

    try:
        # Use Wrangler CLI for deployment
        cmd = [
            "npx", "-y", "wrangler", "pages", "deploy", site_path,
            "--project-name", project_name,
        ]

        env = os.environ.copy()
        env["CLOUDFLARE_API_TOKEN"] = api_token
        if account_id:
            env["CLOUDFLARE_ACCOUNT_ID"] = account_id

        result = subprocess.run(cmd, capture_output=True, text=True, env=env)

        if result.returncode == 0:
            print(f"✅ Deployed successfully!")
            # Try to extract URL from output
            for line in result.stdout.split('\n'):
                if 'pages.dev' in line or 'http' in line:
                    print(f"   🔗 URL: {line.strip()}")
        else:
            print(f"❌ Deployment failed:")
            print(f"   {result.stderr}")

    except FileNotFoundError:
        print("❌ Wrangler CLI not found. Install it with:")
        print("   npm install -g wrangler")
        print(f"\n   Then run manually:")
        print(f"   npx wrangler pages deploy {site_path} --project-name {project_name}")


def deploy_netlify(site_path: str, site_name: str):
    """Deploy to Netlify using Netlify CLI."""
    print(f"🚀 Deploying to Netlify: {site_name}")
    print(f"   Source: {site_path}")

    try:
        cmd = [
            "npx", "-y", "netlify-cli", "deploy",
            "--dir", site_path,
            "--site", site_name,
            "--prod",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ Deployed successfully!")
            for line in result.stdout.split('\n'):
                if 'netlify.app' in line or 'http' in line:
                    print(f"   🔗 URL: {line.strip()}")
        else:
            print(f"❌ Deployment failed:")
            print(f"   {result.stderr}")
            print(f"\n   💡 You can also deploy manually:")
            print(f"   1. Go to https://app.netlify.com/drop")
            print(f"   2. Drag and drop the folder: {site_path}")

    except FileNotFoundError:
        print("❌ Netlify CLI not found.")
        print(f"\n   💡 Deploy manually instead:")
        print(f"   1. Go to https://app.netlify.com/drop")
        print(f"   2. Drag and drop the folder: {site_path}")


def deploy_github_pages(site_path: str, repo_name: str):
    """Instructions for deploying to GitHub Pages."""
    print(f"\n📋 GitHub Pages Deployment Instructions:")
    print(f"{'─'*60}")
    print(f"  1. Create a new GitHub repo: {repo_name}")
    print(f"  2. Run these commands:")
    print(f"     cd {site_path}")
    print(f"     git init")
    print(f"     git add .")
    print(f'     git commit -m "Initial website deploy"')
    print(f"     git branch -M main")
    print(f"     git remote add origin https://github.com/YOUR_USERNAME/{repo_name}.git")
    print(f"     git push -u origin main")
    print(f"  3. Go to repo Settings > Pages > Deploy from branch: main")
    print(f"  4. Your site will be at: https://YOUR_USERNAME.github.io/{repo_name}/")


def main():
    parser = argparse.ArgumentParser(
        description="🚀 AutoWeb Deployer — Deploy sites to the cloud",
    )
    parser.add_argument("--site", type=str, help="Path to the site folder to deploy")
    parser.add_argument("--platform", choices=["cloudflare", "netlify", "github"], default="cloudflare",
                        help="Deployment platform")
    parser.add_argument("--name", type=str, help="Project/site name for the platform")
    parser.add_argument("--list", action="store_true", help="List all sites ready for deployment")

    args = parser.parse_args()

    if args.list:
        list_sites()
        return

    if not args.site:
        parser.print_help()
        print("\n💡 Usage examples:")
        print("   python deploy.py --list")
        print("   python deploy.py --site ../output/sites/my-business --platform cloudflare")
        return

    site_path = os.path.abspath(args.site)
    if not os.path.exists(site_path) or not os.path.exists(os.path.join(site_path, "index.html")):
        print(f"❌ Invalid site path: {site_path}")
        print("   Must be a directory containing index.html")
        sys.exit(1)

    # Generate project name from directory name
    project_name = args.name or os.path.basename(site_path)

    if args.platform == "cloudflare":
        deploy_cloudflare(site_path, project_name)
    elif args.platform == "netlify":
        deploy_netlify(site_path, project_name)
    elif args.platform == "github":
        deploy_github_pages(site_path, project_name)


if __name__ == "__main__":
    main()
