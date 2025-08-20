import dropbox
import os
from datetime import datetime

# Replace with your Dropbox OAuth access token
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]
dbx = dropbox.Dropbox(ACCESS_TOKEN)

MAIN_FOLDER = "/IPW Photos"   # your shared main folder


def list_latest_images(folder_path):
    """Return latest uploaded image file in a given subfolder."""
    try:
        result = dbx.files_list_folder(folder_path)

        latest_file = None
        for entry in result.entries:
            if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower().endswith(('.jpg', '.png')):
                if not latest_file or entry.server_modified > latest_file.server_modified:
                    latest_file = entry

        return latest_file

    except dropbox.exceptions.ApiError as err:
        print(f"Error accessing {folder_path}: {err}")
        return None


def main():
    # List all subfolders in MAIN_FOLDER
    result = dbx.files_list_folder(MAIN_FOLDER)

    subfolders_latest = []

    for entry in result.entries:
        if isinstance(entry, dropbox.files.FolderMetadata):
            latest_file = list_latest_images(entry.path_lower)
            if latest_file:
                subfolders_latest.append({
                    "subfolder": entry.name,
                    "latest_file": latest_file.name,
                    "modified": latest_file.server_modified
                })

    # Sort subfolders by latest upload date (descending)
    subfolders_latest.sort(key=lambda x: x["modified"], reverse=True)

    print("Folders with latest uploads:")
    for item in subfolders_latest[:20]:  # show top 20 most recent
        print(f"{item['subfolder']} -> {item['latest_file']} ({item['modified']})")


if __name__ == "__main__":
    main()
