import os
import hashlib
import requests
import subprocess
import traceback

# Read access token from the 'token' file
def read_token(file_path="token"):
    try:
        with open(file_path, "r") as f:
            return f.read().strip()
    except Exception as e:
        log_error("Error reading token file", e)
        return ""

# Set global variables
ACCESS_TOKEN = read_token()
GRAPH_API_URL = "https://graph.microsoft.com/v1.0"
LOCAL_SAVE_PATH = "OneDrive_Download"
LOG_FILE = "onedrive_sync.log"
ERROR_LOG_FILE = "error_log.txt"

# Check if sha1sum command is available
def is_sha1sum_available():
    try:
        return subprocess.run(["which", "sha1sum"], capture_output=True, text=True).returncode == 0
    except Exception as e:
        log_error("Error checking sha1sum availability", e)
        return False

# Compute SHA-1 hash of a file using sha1sum if available, otherwise use hashlib
def compute_file_hash(file_path):
    try:
        if is_sha1sum_available():
            result = subprocess.run(["sha1sum", file_path], capture_output=True, text=True)
            return result.stdout.split()[0].lower()
        else:
            hasher = hashlib.sha1()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest().lower()
    except Exception as e:
        log_error(f"Error computing hash for {file_path}", e)
        return ""

# Get file hash stored in OneDrive metadata
def get_cloud_file_hash(file_id):
    try:
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        url = f"{GRAPH_API_URL}/me/drive/items/{file_id}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            cloud_hash = response.json().get("file", {}).get("hashes", {}).get("sha1Hash")
            return cloud_hash.lower() if cloud_hash else None
    except Exception as e:
        log_error(f"Error retrieving cloud hash for {file_id}", e)
    return None

# Log file information
def log_file_info(file_name, cloud_hash):
    try:
        with open(LOG_FILE, "a") as log:
            log.write(f"{file_name}: {cloud_hash}\n")
    except Exception as e:
        log_error("Error writing to log file", e)

# Capture and log errors
def log_error(message, exception):
    error_details = f"{message}: {str(exception)}\n{traceback.format_exc()}\n"
    print(error_details)
    with open(ERROR_LOG_FILE, "a") as error_log:
        error_log.write(error_details)

# Get all files and folders recursively
def get_drive_items(folder_id=None, folder_path=""):
    try:
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        url = f"{GRAPH_API_URL}/me/drive/root/children" if not folder_id else f"{GRAPH_API_URL}/me/drive/items/{folder_id}/children"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            items = response.json().get("value", [])
            for item in items:
                try:
                    item_name = item["name"]
                    item_id = item["id"]
                    new_path = os.path.join(folder_path, item_name)
                    
                    if "folder" in item:  # It's a folder
                        os.makedirs(new_path, exist_ok=True)
                        get_drive_items(item_id, new_path)  # Recursively get sub-folder items
                    else:  # It's a file
                        cloud_hash = get_cloud_file_hash(item_id)
                        log_file_info(item_name, cloud_hash)
                        download_file(item_id, new_path, cloud_hash)  # Download file if necessary
                except Exception as e:
                    log_error(f"Error processing item {item}", e)
        else:
            log_error("Failed to fetch items", response.json())
    except Exception as e:
        log_error("Error fetching drive items", e)

# Download a file if it's new or changed
def download_file(file_id, save_path, cloud_hash):
    try:
        if os.path.exists(save_path):
            local_hash = compute_file_hash(save_path)
            if cloud_hash and local_hash == cloud_hash:
                print(f"Skipping existing same file: {save_path}")
                return
            else:
                print(f"Downloading updated modified file: {save_path}")
        else:
            print(f"Downloading new file: {save_path}")
        
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        url = f"{GRAPH_API_URL}/me/drive/items/{file_id}/content"
        response = requests.get(url, headers=headers, stream=True)
        
        if response.status_code == 200:
            with open(save_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    file.write(chunk)
            print(f"Downloaded: {save_path}")
        else:
            log_error(f"Failed to download {save_path}", response.json())
    except Exception as e:
        log_error(f"Error downloading file {save_path}", e)

# Main function
if __name__ == "__main__":
    try:
        os.makedirs(LOCAL_SAVE_PATH, exist_ok=True)
        with open(LOG_FILE, "w") as log:
            log.write("Cloud File Log:\n")
        get_drive_items(folder_path=LOCAL_SAVE_PATH)
        print("Download completed.")
    except Exception as e:
        log_error("Error in main execution", e)

