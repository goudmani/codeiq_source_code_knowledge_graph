import argparse
import io
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path

# Default repository details
REPO_OWNER = "bluesky-social"       # Replace with the GitHub username or organization
REPO_NAME = "social-app"            # Replace with the repository name
BRANCH = "main"                     # Replace with target branch


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download a GitHub repo's .ts/.tsx files into data/raw/."
    )
    parser.add_argument(
        "--repo-owner",
        default=os.environ.get("REPO_OWNER"),
        help="GitHub repo owner (default: REPO_OWNER)",
    )
    parser.add_argument(
        "--repo-name",
        default=os.environ.get("REPO_NAME"),
        help="GitHub repo name (default: REPO_NAME)",
    )
    parser.add_argument(
        "--branch",
        default=os.environ.get("BRANCH"),
        help="Branch to download (default: BRANCH)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download and overwrite even if the output directory already exists",
    )

    args = parser.parse_args()

    missing = [
        name
        for name, val in [
            ("--repo-owner/REPO_OWNER", args.repo_owner),
            ("--repo-name/REPO_NAME", args.repo_name),
            ("--branch/BRANCH", args.branch),
        ]
        if not val
    ]
    if missing:
        parser.error(
            f"Missing required value(s): {', '.join(missing)}. "
            "Pass them as CLI args or set them in .env."
        )

    return args


def download_and_extract_ts_files(repo_owner, repo_name, branch, force=False):
    zip_url = f"https://github.com/{repo_owner}/{repo_name}/archive/refs/heads/{branch}.zip"
    output_dir = f"data/raw/{repo_owner}_{repo_name}_{branch}"

    if os.path.exists(output_dir):
        if force:
            print(f"Warning: '{output_dir}' already exists. Re-cloning and overwriting it (--force).")
            shutil.rmtree(output_dir)
        else:
            print(
                f"Warning: '{output_dir}' already exists. Skipping download. "
                "Use --force to re-clone and overwrite it."
            )
            return

    print(f"Downloading source from {zip_url}...")

    try:
        # Fetch zip archive into memory
        req = urllib.request.Request(zip_url, headers={'User-Agent': 'Python-Script'})
        with urllib.request.urlopen(req) as response:
            zip_data = response.read()
        
        # Open the zip archive
        with zipfile.ZipFile(io.BytesIO(zip_data)) as archive:
            for file_path in archive.namelist():
                # Filter for target extensions and ignore directory-only entries
                if (file_path.endswith('.ts') or file_path.endswith('.tsx')) and not file_path.endswith('/'):
                    
                    # Split path to remove GitHub's top-level root folder (e.g., 'repo-main/')
                    parts = file_path.split('/', 1)
                    if len(parts) < 2:
                        continue
                    relative_path = parts[1]
                    
                    # Construct the final destination file path
                    dest_file_path = os.path.join(output_dir, relative_path)
                    
                    # Create parent directories if they don't exist
                    os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
                    
                    # Extract and write the file
                    with archive.open(file_path) as source_file, open(dest_file_path, 'wb') as dest_file:
                        dest_file.write(source_file.read())
                        print(f"Saved: {relative_path}")
                        
        print(f"\nExtraction complete! Files saved to: {os.path.abspath(output_dir)}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    args = parse_args()
    download_and_extract_ts_files(
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        branch=args.branch,
        force=args.force,
    )