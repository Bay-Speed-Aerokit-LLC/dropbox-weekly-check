import os
import time
import io
import requests
from rembg import remove
from PIL import Image
import ftplib
import dropbox
from datetime import datetime

# === Dropbox Setup ===
dbx = dropbox.Dropbox(
    oauth2_refresh_token=os.environ["DROPBOX_REFRESH_TOKEN"],
    app_key=os.environ["DROPBOX_APP_KEY"],
    app_secret=os.environ["DROPBOX_APP_SECRET"],
)

# === Shared Link ===
SHARED_LINK = "https://www.dropbox.com/scl/fo/x5wa53hnnfjrru13wh1j6/h?rlkey=h9r8xsjmq43vx43ofjqq0henb&st=cxaicqpk&dl=0"

# === FTP Setup ===
FTP_HOST = os.environ["FTP_HOST"]
FTP_USER = os.environ["FTP_USER"]
FTP_PASS = os.environ["FTP_PASS"]
REMOTE_BASE_PATH = '/domains/ipwstock.com/public_html/public/dropbox/'


# ----------------------------
# Helpers for Dropbox v12
# ----------------------------
def get_access_token(dbx: dropbox.Dropbox):
    return dbx._oauth2_access_token


def list_shared_link_files(shared_link_url):
    token = get_access_token(dbx)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    endpoint = "https://api.dropboxapi.com/2/sharing/list_shared_link_files"
    payload = {"url": shared_link_url}

    entries = []
    while True:
        resp = requests.post(endpoint, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        entries.extend(data["entries"])

        if data.get("has_more"):
            endpoint = "https://api.dropboxapi.com/2/sharing/list_shared_link_files/continue"
            payload = {"cursor": data["cursor"]}
        else:
            break

    return entries


def download_shared_file(shared_link_url, file_metadata, local_dir):
    token = get_access_token(dbx)
    headers = {
        "Authorization": f"Bearer {token}",
        "Dropbox-API-Arg": '{"url": "%s", "path": "%s"}'
        % (shared_link_url, file_metadata["path_lower"]),
    }
    endpoint = "https://content.dropboxapi.com/2/sharing/get_shared_link_file"

    resp = requests.post(endpoint, headers=headers, stream=True)
    resp.raise_for_status()

    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, file_metadata["name"])
    with open(local_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"Downloaded: {local_path}")
    return local_path


# ----------------------------
# State tracking
# ----------------------------
def get_last_run_time():
    if os.path.exists(".last_run.txt"):
        with open(".last_run.txt", "r") as f:
            return datetime.fromisoformat(f.read().strip())
    return None


def update_last_run_time():
    with open(".last_run.txt", "w") as f:
        f.write(datetime.utcnow().isoformat())


# ----------------------------
# Processing pipeline
# ----------------------------
def process_folder(base_folder, folder):
    folder_path = os.path.join(base_folder, folder)

    # === STEP 1: Resize to 6000x4000 & white background ===
    for file in os.listdir(folder_path):
        image_path = os.path.join(folder_path, file)
        if not os.path.isfile(image_path):
            continue
        try:
            original_image = Image.open(image_path)
        except:
            continue

        target_height, target_width = 4000, 6000
        original_width, original_height = original_image.size
        aspect_ratio = original_width / original_height

        if aspect_ratio > target_width / target_height:
            desired_width = target_width
            desired_height = int(target_width / aspect_ratio)
        else:
            desired_height = target_height
            desired_width = int(target_height * aspect_ratio)

        resized_image = original_image.resize((desired_width, desired_height), Image.LANCZOS)
        crop_left = (desired_width - target_width) // 2
        crop_top = (desired_height - target_height) // 2
        crop_right = crop_left + target_width
        crop_bottom = crop_top + target_height
        cropped_image = resized_image.crop((crop_left, crop_top, crop_right, crop_bottom))
        background_image = Image.new('RGB', (target_width, target_height), (255, 255, 255))
        paste_left = (target_width - cropped_image.width) // 2
        paste_top = (target_height - cropped_image.height) // 2
        background_image.paste(cropped_image, (paste_left, paste_top))
        background_image.save(image_path)
        print(f"{image_path} resized to 6000x4000 with white background.")

    # === STEP 2: Remove background & convert to .webp ===
    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        if not os.path.isfile(file_path):
            continue
        try:
            img = Image.open(file_path)
        except:
            continue
        remove_bg = remove(img)
        webp_path = file_path + '.webp'
        remove_bg.save(webp_path, format="webp", optimize=True, quality=80)
        print(f"{file} background removed & saved as webp.")

    # === STEP 3: Clean up originals ===
    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        time.sleep(1)
        if file.endswith('.webp'):
            filename, extension = os.path.splitext(file_path)
            new_file_path = filename.split(".")[0] + extension
            os.rename(file_path, new_file_path)
        elif file.lower().endswith(('.jpg', '.png')):
            os.remove(file_path)
            print(f"{file} removed.")

    # === STEP 4: Create PNG folder & save 500x500 PNG ===
    png_folder = os.path.join(folder_path, "PNG")
    if not os.path.exists(png_folder):
        os.mkdir(png_folder)
    for file in os.listdir(folder_path):
        if file not in ("PNG", "images") and file.lower().endswith('.webp'):
            image_path = os.path.join(folder_path, file)
            img = Image.open(image_path)
            target_height, target_width = 500, 500
            original_width, original_height = img.size
            aspect_ratio = original_width / original_height
            if aspect_ratio > target_width / target_height:
                desired_width = target_width
                desired_height = int(target_width / aspect_ratio)
            else:
                desired_height = target_height
                desired_width = int(target_height * aspect_ratio)
            resized_image = img.resize((desired_width, desired_height), Image.LANCZOS)
            crop_left = (desired_width - target_width) // 2
            crop_top = (desired_height - target_height) // 2
            crop_right = crop_left + target_width
            crop_bottom = crop_top + target_height
            cropped_image = resized_image.crop((crop_left, crop_top, crop_right, crop_bottom))
            background_image = Image.new('RGB', (target_width, target_height), (255, 255, 255))
            paste_left = (target_width - cropped_image.width) // 2
            paste_top = (target_height - cropped_image.height) // 2
            background_image.paste(cropped_image, (paste_left, paste_top))
            png_path = os.path.join(png_folder, folder + '.png')
            background_image.save(png_path, format="png", optimize=True, quality=10)
            print(f"{image_path} saved as 500x500 PNG.")

    # === STEP 5: Create images folder & save 400x270 images ===
    images_folder = os.path.join(folder_path, "images")
    if not os.path.exists(images_folder):
        os.mkdir(images_folder)
    for file in os.listdir(folder_path):
        if file not in ("PNG", "images") and file.lower().endswith('.webp'):
            image_path = os.path.join(folder_path, file)
            img = Image.open(image_path)
            resized_image = img.resize((400, 270), Image.LANCZOS)
            save_path = os.path.join(images_folder, file)
            resized_image.save(save_path)
            print(f"{image_path} resized to 400x270 in images folder.")

    # === STEP 6: Remove background again in /images & set white background ===
    for file in os.listdir(images_folder):
        if file.endswith('.webp'):
            input_image_path = os.path.join(images_folder, file)
            with open(input_image_path, "rb") as f:
                image_data = f.read()
            result = remove(image_data)
            image = Image.open(io.BytesIO(result)).convert("RGBA")
            background = Image.new('RGBA', image.size, (255, 255, 255, 255))
            background.paste(image, (0, 0), image)
            background.save(input_image_path, format="WEBP")
            print(f"{input_image_path} white background reapplied.")

    # === STEP 7: Store Image to hostinger account ===
    ftp = ftplib.FTP(FTP_HOST, FTP_USER, FTP_PASS)
    ftp.cwd(REMOTE_BASE_PATH)

    remote_folder_path = os.path.join(REMOTE_BASE_PATH, folder)
    remote_folders = ftp.nlst()
    if folder not in remote_folders:
        ftp.mkd(remote_folder_path)
        print(f"'{folder}' created on the remote server.")

    def upload_folder(local_path, remote_path):
        try:
            ftp.mkd(remote_path)
            print(f"Created remote directory: {remote_path}")
        except ftplib.error_perm as e:
            if not str(e).startswith("550"):
                raise
        for filename in os.listdir(local_path):
            local_file = os.path.join(local_path, filename)
            remote_file = f"{remote_path}/{filename}"
            if os.path.isfile(local_file):
                try:
                    ftp.size(remote_file)
                    print(f"'{remote_file}' already exists on the remote server.")
                except ftplib.error_perm as e:
                    if "550" in str(e):
                        with open(local_file, 'rb') as f:
                            ftp.storbinary(f"STOR {remote_file}", f)
                        print(f"Uploaded: {remote_file}")
                    else:
                        print(f"Error checking '{remote_file}': {str(e)}")

    # Upload main .webp
    main_webp_list = [x for x in os.listdir(folder_path) if x.endswith('.webp')]
    for webp_image in main_webp_list:
        local_image_path = os.path.join(folder_path, webp_image)
        server_path = f"{remote_folder_path}/{webp_image}"
        try:
            ftp.size(server_path)
            print(f"'{server_path}' already exists on the remote server.")
        except ftplib.error_perm as e:
            if "550" in str(e):
                with open(local_image_path, 'rb') as f:
                    ftp.storbinary(f"STOR {server_path}", f)
                print(f"'{server_path}' transferred to the remote server.")
            else:
                print(f"Error checking '{webp_image}': {str(e)}")

    if os.path.exists(images_folder):
        upload_folder(images_folder, f"{remote_folder_path}/images")
    if os.path.exists(png_folder):
        upload_folder(png_folder, f"{remote_folder_path}/PNG")

    ftp.quit()

# ----------------------------
# Main
# ----------------------------
def main():
    last_run = get_last_run_time()
    local_downloads = "downloads"
    os.makedirs(local_downloads, exist_ok=True)

    # List all files from shared link
    entries = list_shared_link_files(SHARED_LINK)

    for entry in entries:
        if entry[".tag"] == "file":
            local_file = download_shared_file(SHARED_LINK, entry, local_downloads)

            if not last_run or os.path.getmtime(local_file) > last_run.timestamp():
                folder_name = os.path.splitext(entry["name"])[0]
                folder_path = os.path.join(local_downloads, folder_name)
                os.makedirs(folder_path, exist_ok=True)
                os.rename(local_file, os.path.join(folder_path, entry["name"]))

                try:
                    process_folder(local_downloads, folder_name)
                except Exception as e:
                    print(f"Error processing {folder_name}: {e}")

    update_last_run_time()


if __name__ == "__main__":
    main()
