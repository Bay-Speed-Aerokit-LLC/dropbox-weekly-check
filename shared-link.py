import os
import time
import io
from rembg import remove
from PIL import Image
import ftplib
import dropbox
from datetime import datetime
from dropbox.files import ListFolderArg, SharedLink

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


def get_last_run_time():
    if os.path.exists(".last_run.txt"):
        with open(".last_run.txt", "r") as f:
            return datetime.fromisoformat(f.read().strip())
    return None


def update_last_run_time():
    with open(".last_run.txt", "w") as f:
        f.write(datetime.utcnow().isoformat())

def download_shared_folder(local_path, dropbox_path, last_run):
    try:
        res = dbx.files_list_folder(dropbox_path)
    except Exception as e:
        print(f"Error listing {dropbox_path}: {e}")
        return False

    has_new = False

    for entry in res.entries:
        # If it's a folder, recurse
        if isinstance(entry, dropbox.files.FolderMetadata):
            sub_local_path = os.path.join(local_path, entry.name)  # ✅ use entry.name only
            os.makedirs(sub_local_path, exist_ok=True)

            if download_shared_folder(sub_local_path, entry.path_lower, last_run):
                has_new = True

        elif isinstance(entry, dropbox.files.FileMetadata):
            local_file_path = os.path.join(local_path, entry.name)

            # ✅ Avoid re-downloading unless updated
            if not os.path.exists(local_file_path) or entry.client_modified.timestamp() > last_run.timestamp():
                with open(local_file_path, "wb") as f:
                    metadata, res = dbx.files_download(entry.path_lower)
                    f.write(res.content)
                print(f"Downloaded: {entry.path_lower}")
                has_new = True

    return has_new


def process_folder(base_folder, folder):
    """
    Step 1–7 processing logic on downloaded folder.
    """
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

    # === STEP 3: Clean up original images ===
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


def main():
    last_run = get_last_run_time()
    local_downloads = "downloads"
    os.makedirs(local_downloads, exist_ok=True)
    
    result = dbx.sharing_list_shared_link_files(
        SharedLink(url=SHARED_LINK)
    )

    while True:
        for entry in result.entries:
            if isinstance(entry, dropbox.files.FolderMetadata):
                local_path = os.path.join("downloads", entry.name)
                os.makedirs(local_path, exist_ok=True)
                print(f"Checking shared folder: {entry.name}")
                has_new = download_shared_folder(local_path, entry.path_lower, last_run)
                if has_new:
                    try:
                        process_folder("downloads", entry.name)
                    except Exception as e:
                        print(f"Error processing {entry.name}: {e}")
            elif isinstance(entry, dropbox.files.FileMetadata):
                print(f"File found: {entry.name}")

        if result.has_more:
            result = dbx.sharing_list_shared_link_files_continue(result.cursor)
        else:
            break

    update_last_run_time()


if __name__ == "__main__":
    main()
