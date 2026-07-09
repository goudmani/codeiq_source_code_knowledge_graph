import io
import os
import urllib.request
import zipfile

from repo_link import *

ZIP_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/heads/{BRANCH}.zip"
OUTPUT_DIR = "data/raw"

def download_and_extract_ts_files():
    print(f"Downloading source from {ZIP_URL}...")
    
    try:
        # Fetch zip archive into memory
        req = urllib.request.Request(ZIP_URL, headers={'User-Agent': 'Python-Script'})
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
                    dest_file_path = os.path.join(OUTPUT_DIR, relative_path)
                    
                    # Create parent directories if they don't exist
                    os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
                    
                    # Extract and write the file
                    with archive.open(file_path) as source_file, open(dest_file_path, 'wb') as dest_file:
                        dest_file.write(source_file.read())
                        print(f"Saved: {relative_path}")
                        
        print(f"\nExtraction complete! Files saved to: {os.path.abspath(OUTPUT_DIR)}")
                            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    download_and_extract_ts_files()
