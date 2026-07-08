import io
import urllib.request
import zipfile

from data.raw.repo_link import *

# 2. Construct the GitHub zip download URL
ZIP_URL = f"https://github.com{REPO_OWNER}/{REPO_NAME}/archive/refs/heads/{BRANCH}.zip"
OUTPUT_DIR = "data/processed"

def download_and_read_code():
    print(f"Downloading source code archive from {ZIP_URL}...")
    
    try:
        # Request the zip file from GitHub
        req = urllib.request.Request(ZIP_URL, headers={'User-Agent': 'Python-Script'})
        with urllib.request.urlopen(req) as response:
            zip_data = response.read()
        
        # Open the zip file completely in memory
        with zipfile.ZipFile(io.BytesIO(zip_data)) as archive:
            # Loop through every file inside the repository archive
            for file_path in archive.namelist():
                # Filter specifically for .ts and .tsx files
                if file_path.endswith('.ts') or file_path.endswith('.tsx'):
                    print(f"\n--- READING FILE: {file_path} ---")
                    
                    # Read the binary data and decode it into a text string
                    with archive.open(file_path) as file:
                        file_text = file.read().decode('utf-8', errors='ignore')
                        
                        # Process your text data here (Printing the first 500 chars as an example)
                        print(file_text[:500]) 
                        if len(file_text) > 500:
                            print("... [TRUNCATED] ...")
                            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    download_and_read_code()
