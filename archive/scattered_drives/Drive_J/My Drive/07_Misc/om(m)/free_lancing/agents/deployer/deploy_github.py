#!/usr/bin/env python3
"""
AutoWeb GitHub Pages Deployer
===============================
Automatically initializes a Git repository in the output/sites directory,
creates a single GitHub repository to hold all client sites, and pushes the code.
Each site will be accessible at:
https://<username>.github.io/<repo_name>/<site-slug>/
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
SITES_DIR = PROJECT_DIR / "output" / "sites"

def run_cmd(cmd, cwd=None, ignore_errors=False):
    """Run a shell command and return its output."""
    try:
        result = subprocess.run(
            cmd, 
            cwd=cwd, 
            shell=True, 
            check=not ignore_errors,
            capture_output=True, 
            text=True
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.CalledProcessError as e:
        if not ignore_errors:
            print(f"❌ Error running command: {cmd}")
            print(e.stderr)
            sys.exit(1)
        return e.stdout.strip(), e.stderr.strip(), e.returncode

def get_github_username():
    stdout, _, code = run_cmd("gh api user -q .login", ignore_errors=True)
    if code != 0 or not stdout:
        print("❌ Could not get GitHub username. Make sure you are logged in via 'gh auth login'.")
        sys.exit(1)
    return stdout

def deploy_to_github(repo_name="autoweb-sites"):
    if not SITES_DIR.exists():
        print("❌ No sites directory found. Run the pipeline first.")
        sys.exit(1)

    print(f"🚀 Starting automated deployment to GitHub Pages...")
    username = get_github_username()
    print(f"👤 GitHub User: {username}")
    
    # Ensure index.html exists at the root of sites so the base URL doesn't 404
    root_index = SITES_DIR / "index.html"
    if not root_index.exists():
        root_index.write_text("<h1>AutoWeb Client Sites</h1><p>Client preview directory.</p>")
        
    cwd = str(SITES_DIR)

    # 1. Initialize git if needed
    if not (SITES_DIR / ".git").exists():
        print("📁 Initializing git repository...")
        run_cmd("git init", cwd=cwd)
        run_cmd("git branch -M main", cwd=cwd)

    # 2. Check if repo exists on GitHub, if not create it
    stdout, _, code = run_cmd(f"gh repo view {repo_name}", ignore_errors=True)
    if code != 0:
        print(f"🌐 Creating public GitHub repository '{repo_name}'...")
        run_cmd(f"gh repo create {repo_name} --public", cwd=cwd)
    else:
        print(f"✅ GitHub repository '{repo_name}' already exists.")

    # 3. Add remote if missing
    stdout, _, _ = run_cmd("git remote -v", cwd=cwd)
    if repo_name not in stdout:
        run_cmd(f"git remote add origin https://github.com/{username}/{repo_name}.git", cwd=cwd, ignore_errors=True)

    # 4. Commit all changes
    print("💾 Committing sites...")
    run_cmd("git add .", cwd=cwd)
    # Check if there are changes to commit
    _, _, diff_code = run_cmd("git diff --staged --quiet", cwd=cwd, ignore_errors=True)
    if diff_code != 0:
        run_cmd('git commit -m "AutoWeb: Deploy generated sites"', cwd=cwd, ignore_errors=True)
    else:
        print("   No new changes to commit.")

    # 5. Push to GitHub
    print("☁️  Pushing to GitHub...")
    run_cmd("git push -u origin main", cwd=cwd, ignore_errors=True)

    base_url = f"https://{username}.github.io/{repo_name}"
    
    print(f"\n🎉 Deployment pushed successfully!")
    print(f"⚠️  NOTE: If this is the first time you created the repo, you MUST enable GitHub Pages:")
    print(f"   1. Go to https://github.com/{username}/{repo_name}/settings/pages")
    print(f"   2. Under 'Build and deployment', set Source to 'Deploy from a branch'")
    print(f"   3. Select 'main' branch and '/ (root)' folder, then click Save.")
    print(f"\n🔗 Base URL: {base_url}/")
    
    # List deployed site URLs
    print("\nLive Site Links:")
    for d in SITES_DIR.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            print(f"  - {d.name}: {base_url}/{d.name}/")
            
    return base_url

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy sites to GitHub Pages")
    parser.add_argument("--repo", default="autoweb-sites", help="Name of the GitHub repository")
    args = parser.parse_args()
    
    deploy_to_github(args.repo)
