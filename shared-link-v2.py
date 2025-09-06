import os
# from dotenv import load_dotenv
# load_dotenv()
import io
import time
import ftplib
import dropbox
import re
from rembg import remove
from PIL import Image
from datetime import datetime
from dropbox.files import SharedLink, FileMetadata, FolderMetadata

# === Dropbox Setup ===
# Move credentials to environment variables for safety.
# DBX_REFRESH_TOKEN = "61zEUq8y83MAAAAAAAAAAS_AneoAKVJxgBWB1FDGAO962YTdCkeK7Txbxye4RFOa"
# DBX_APP_KEY = "zm91y9jxmt6r8oo"
# DBX_APP_SECRET = "jcms22p6uonya8o"

# if not (DBX_REFRESH_TOKEN and DBX_APP_KEY and DBX_APP_SECRET):
#     raise RuntimeError("Set DROPBOX_OAUTH_REFRESH_TOKEN, DROPBOX_APP_KEY and DROPBOX_APP_SECRET environment variables.")

dbx = dropbox.Dropbox(
    oauth2_refresh_token=os.environ["DROPBOX_REFRESH_TOKEN"],
    app_key=os.environ["DROPBOX_APP_KEY"],
    app_secret=os.environ["DROPBOX_APP_SECRET"],
)

# dbx = dropbox.Dropbox(
#     oauth2_refresh_token=DBX_REFRESH_TOKEN,
#     app_key=DBX_APP_KEY,
#     app_secret=DBX_APP_SECRET,
# )


# === Shared Folder Link ===
SHARED_LINK = os.environ.get("DROPBOX_SHARED_LINK") or "https://www.dropbox.com/scl/fo/x5wa53hnnfjrru13wh1j6/h?rlkey=h9r8xsjmq43vx43ofjqq0henb"

# === FTP Setup ===
# FTP_HOST = "ipwstock.com"
# FTP_USER = "u307603549"
# FTP_PASS = "@BayspeedautoFTP.1234.."
FTP_HOST = os.environ["FTP_HOST"]
FTP_USER = os.environ["FTP_USER"]
FTP_PASS = os.environ["FTP_PASS"]
REMOTE_BASE_PATH = '/domains/ipwstock.com/public_html/public/dropbox/'


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
    os.makedirs(folder_path, exist_ok=True)

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
    try:
        ftp.cwd(REMOTE_BASE_PATH)
    except Exception:
        # try to create base path
        try:
            ftp.mkd(REMOTE_BASE_PATH)
            ftp.cwd(REMOTE_BASE_PATH)
        except Exception as e:
            ftp.quit()
            raise

    remote_folder_path = os.path.join(REMOTE_BASE_PATH, folder).replace("\\", "/")
    remote_folders = ftp.nlst()
    if folder not in remote_folders:
        try:
            ftp.mkd(remote_folder_path)
            print(f"'{folder}' created on the remote server.")
        except Exception:
            pass

    def upload_folder(local_path, remote_path):
        try:
            ftp.mkd(remote_path)
        except ftplib.error_perm as e:
            # 550 means folder exists on many servers
            if not str(e).startswith("550"):
                print(f"FTP mkdir error: {e}")
        for filename in os.listdir(local_path):
            local_file = os.path.join(local_path, filename)
            remote_file = f"{remote_path}/{filename}"
            if os.path.isfile(local_file):
                # remove remote file if it exists, ignore permission errors
                try:
                    ftp.delete(remote_file)
                    print(f"Removed remote {remote_file} (will replace).")
                except ftplib.error_perm:
                    pass
                with open(local_file, 'rb') as f:
                    ftp.storbinary(f"STOR {remote_file}", f)
                print(f"Uploaded/Updated: {remote_file}")

    # Upload main .webp (always replace on remote)
    main_webp_list = [x for x in os.listdir(folder_path) if x.lower().endswith('.webp')]
    for webp_image in main_webp_list:
        local_image_path = os.path.join(folder_path, webp_image)
        server_path = f"{remote_folder_path}/{webp_image}"
        try:
            ftp.delete(server_path)
            print(f"Removed old remote {server_path}.")
        except ftplib.error_perm:
            pass
        with open(local_image_path, 'rb') as f:
            ftp.storbinary(f"STOR {server_path}", f)
        print(f"'{server_path}' transferred to the remote server.")

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

    # Create SharedLink object
    link = SharedLink(url=SHARED_LINK)

    # List root contents of the shared link
    result = dbx.files_list_folder(path="", shared_link=link)
    entries = result.entries
    while result.has_more:
        result = dbx.files_list_folder_continue(result.cursor)
        entries.extend(result.entries)

    # Only top-level folders with "-" in the name
    target_folders = [
        e for e in entries
        if (
            isinstance(e, dropbox.files.FolderMetadata)
            and "-" in e.name
            and "disc" not in e.name.lower()           # exclude "Discontinue" variants
            and "undone" not in e.name.lower()         # exclude "Undone" variants
            and "single drill" not in e.name.lower()   # exclude "Single Drill" variants
            and "828-1" not in e.name.lower()          # exclude "828-1" variants
            and not any("  " in part for part in e.name.split("-"))  # exclude extra spaces between segments
        )
    ]

    for folder in target_folders:
        print(f"Processing folder: {folder.name}")
        # SharedLink object just needs the URL
        link = SharedLink(url=SHARED_LINK)

        # The path inside the shared link is "/" + folder name
        folder_result = dbx.files_list_folder(
            path="/" + folder.name,
            shared_link=link
        )

        folder_entries = folder_result.entries
        while folder_result.has_more:
            folder_result = dbx.files_list_folder_continue(folder_result.cursor)
            folder_entries.extend(folder_result.entries)

        # Only .jpg and .png files that end with a numeric suffix like "-04", "_05", etc.
        numeric_suffix_re = re.compile(r".*[-_]\d+$")
        files_to_download = [
            f for f in folder_entries
            if (
                isinstance(f, dropbox.files.FileMetadata)
                and f.name.lower().endswith((".jpg", ".png", ".jpeg"))
                and numeric_suffix_re.match(os.path.splitext(f.name)[0].lower())
            )
        ]

        # prepare local folder
        local_folder_path = os.path.join(local_downloads, folder.name)
        os.makedirs(local_folder_path, exist_ok=True)

        # download files into local folder
        now = datetime.utcnow()
        MIN_FILES = int(os.environ.get("MIN_FILES_TO_PROCESS", "3"))  # set to 5 via env if you prefer

        # filter files by timestamp (only current month)
        eligible_files = []
        for f in files_to_download:
            file_ts = getattr(f, "server_modified", None) or getattr(f, "client_modified", None)
            if file_ts is None:
                print(f"Skipping {f.name}: no timestamp available on metadata.")
                continue
            if file_ts.year == now.year and file_ts.month == now.month:
                eligible_files.append(f)

        if not eligible_files:
            print(f"Skipping folder {folder.name}: no images from current month ({now.strftime('%Y-%m')}).")
            continue
        if len(eligible_files) < MIN_FILES:
            print(f"Skipping folder {folder.name}: only {len(eligible_files)} file(s) from current month (min {MIN_FILES}).")
            continue

        for f in eligible_files:
            local_path = os.path.join(local_folder_path, f.name)
            dropbox_path = "/" + folder.name + "/" + f.name
            try:
                md, res = dbx.sharing_get_shared_link_file(url=SHARED_LINK, path=dropbox_path)
                with open(local_path, "wb") as out_f:
                    out_f.write(res.content)
                print(f"Downloaded {dropbox_path} -> {local_path}")
            except Exception as e:
                print(f"Failed to download {dropbox_path}: {e}")

        # process the downloaded folder once
        process_folder(local_downloads, folder.name)

    update_last_run_time()


if __name__ == "__main__":
    main()
