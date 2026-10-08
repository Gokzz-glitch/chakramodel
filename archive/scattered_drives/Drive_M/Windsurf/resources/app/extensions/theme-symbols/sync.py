#!/usr/bin/env python3
import os
import shutil
import tempfile
import subprocess
from pathlib import Path

def sync_icons():
	# Get the directory where this script is located
	current_dir = Path(__file__).parent.absolute()

	# Create a temporary directory for the sparse checkout
	with tempfile.TemporaryDirectory() as temp_dir:
		temp_dir_path = Path(temp_dir)
		print("Initializing sparse checkout...")

		try:
			# Initialize git repo
			subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)

			# Add remote
			subprocess.run(
				["git", "remote", "add", "origin", "https://github.com/miguelsolorio/vscode-symbols.git"],
				cwd=temp_dir, check=True, capture_output=True
			)

			# Configure sparse checkout
			subprocess.run(
				["git", "sparse-checkout", "set", "src/icons", "src/symbol-icon-theme.json"],
				cwd=temp_dir, check=True, capture_output=True
			)

			# Fetch only the latest version
			print("Downloading required files...")
			subprocess.run(
				["git", "pull", "origin", "main", "--depth=1"],
				cwd=temp_dir, check=True, capture_output=True
			)
		except subprocess.CalledProcessError as e:
			print(f"Error downloading files: {e.stderr}")
			return

		# Source paths in the sparse checkout
		src_icons = temp_dir_path / "src" / "icons"
		src_theme = temp_dir_path / "src" / "symbol-icon-theme.json"

		# Destination paths in our extension
		dest_icons = current_dir / "src" / "icons"
		dest_theme = current_dir / "src" / "symbol-icon-theme.json"

		# Ensure the src directory exists
		os.makedirs(dest_icons.parent, exist_ok=True)

		# Remove existing directories/files if they exist
		if dest_icons.exists():
			shutil.rmtree(dest_icons)
		if dest_theme.exists():
			dest_theme.unlink()

		# Copy the files
		print("Copying icons directory...")
		shutil.copytree(src_icons, dest_icons)

		print("Copying theme file...")
		shutil.copy2(src_theme, dest_theme)

		print("Sync completed successfully!")

if __name__ == "__main__":
	sync_icons()
