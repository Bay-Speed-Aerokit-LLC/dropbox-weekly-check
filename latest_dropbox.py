import os
import time
import io
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

MAIN_FOLDER = "/Levinbo Test Dropbox Folder"  # Shared folder name

# === FTP Setup ===
FTP_HOST = 'ipwstock.com'
FTP_USER = 'u307603549'
FTP_PASS = '@BayspeedautoFTP.1234..'
REMOTE_BASE_PATH = '/domains/ipwstock.com/public_html/public/dropbox/'


def get_last_run_time():
    if os.path.exists(".last_run.txt"):
        with open(".last_run.txt", "r") as f:
            return datetime.fromisoformat(f.read().strip())
    return None

def update_last_run_time():
    with open(".last_run.txt", "w") as f:
        f.write(datetime.utcnow().isoformat())

def download_dropbox_folder(local_base, dropbox_path, last_run):
    try:
        result = dbx.files_list_folder(dropbox_path)
    except dropbox.exceptions.ApiError as e:
        print(f"Error listing {dropbox_path}: {e}")
        return False

    new_files = False
    for entry in result.entries:
        local_path = os.path.join(local_base, entry.name)

        if isinstance(entry, dropbox.files.FileMetadata):
            # Only download images
            if entry.name.lower().endswith(('.jpg', '.png')):
                if not last_run or entry.server_modified > last_run:
                    dbx.files_download_to_file(local_path, entry.path_lower)
                    print(f"Downloaded NEW file {entry.path_lower} -> {local_path}")
                    new_files = True
        elif isinstance(entry, dropbox.files.FolderMetadata):
            os.makedirs(local_path, exist_ok=True)
            if download_dropbox_folder(local_path, entry.path_lower, last_run):
                new_files = True

    return new_files

def process_folder(base_folder, folder):
    """
    Run your original STEP 1–7 processing logic
    on a given folder that’s already downloaded locally.
    """
    folder_path = os.path.join(base_folder, folder)

    # === STEP 1: Resize to 6000x4000 & white background ===
    file_list = os.listdir(folder_path)
    for file in file_list:
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
    image_list = os.listdir(folder_path)
    for image_file in image_list:
        file_path = os.path.join(folder_path, image_file)
        if not os.path.isfile(file_path):
            continue
        try:
            img = Image.open(file_path)
        except:
            continue
        remove_bg = remove(img)
        webp_path = file_path + '.webp'
        remove_bg.save(webp_path, format="webp", optimize=True, quality=10)
        print(f"{image_file} background removed & saved as webp.")

    # === STEP 3: Clean up original images ===
    rm_image_list = os.listdir(folder_path)
    for rm_image in rm_image_list:
        rm_file_path = os.path.join(folder_path, rm_image)
        time.sleep(1)
        if rm_image.endswith('.webp'):
            filename, extension = os.path.splitext(rm_file_path)
            new_file_path = filename.split(".")[0] + extension
            os.rename(rm_file_path, new_file_path)
        elif rm_image.lower().endswith(('.jpg', '.png')):
            os.remove(rm_file_path)
            print(f"{rm_image} removed.")

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
    for image_file in os.listdir(images_folder):
        if image_file.endswith('.webp'):
            input_image_path = os.path.join(images_folder, image_file)
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
        """Uploads all files in a folder to FTP, skipping existing files."""
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

    # Upload images & PNG folders
    if os.path.exists(images_folder):
        upload_folder(images_folder, f"{remote_folder_path}/images")
    if os.path.exists(png_folder):
        upload_folder(png_folder, f"{remote_folder_path}/PNG")

    ftp.quit()

def main():
    last_run = get_last_run_time()
    local_downloads = "downloads"
    os.makedirs(local_downloads, exist_ok=True)

    result = dbx.files_list_folder(MAIN_FOLDER)
    for entry in result.entries:
        if isinstance(entry, dropbox.files.FolderMetadata):
            local_path = os.path.join(local_downloads, entry.name)
            os.makedirs(local_path, exist_ok=True)
            print(f"Checking folder: {entry.name}")
            has_new = download_dropbox_folder(local_path, entry.path_lower, last_run)
            if has_new:
                process_folder(local_downloads, entry.name)

    update_last_run_time()

if __name__ == "__main__":
    main()
