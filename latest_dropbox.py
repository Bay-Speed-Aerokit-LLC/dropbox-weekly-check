import os
import time
import io
from rembg import remove, new_session
from PIL import Image
import ftplib
import dropbox
from datetime import datetime

# === New Configuration / Helpers ===
# Global set to track which folders have already had their single PNG file created
PNG_CREATED_FOLDERS = set()

def create_square_image(img, size, fill_color=(0, 0, 0, 0)):
    """
    Resizes an image to fit within a square boundary (maintaining aspect ratio) 
    and pads the remaining space with a transparent color.
    """
    # 1. Resize to fit within the square boundary (e.g., 2000x2000) while maintaining aspect ratio
    img.thumbnail(size, Image.Resampling.LANCZOS)
    
    # 2. Create the final square canvas with transparent background
    new_img = Image.new('RGBA', size, fill_color)
    
    # 3. Calculate position to center the resized image on the canvas
    width, height = img.size
    x_offset = (size[0] - width) // 2
    y_offset = (size[1] - height) // 2
    
    # 4. Paste the resized image onto the canvas (using itself as the mask)
    new_img.paste(img, (x_offset, y_offset), img)
    
    return new_img

# === Dropbox Setup ===
dbx = dropbox.Dropbox(
    oauth2_refresh_token=os.environ["DROPBOX_REFRESH_TOKEN"],
    app_key=os.environ["DROPBOX_APP_KEY"],
    app_secret=os.environ["DROPBOX_APP_SECRET"],
)

MAIN_FOLDER = "/Levinbo Test Dropbox Folder"  # Shared folder name

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

def download_dropbox_folder(local_base, dropbox_path, last_run):
    try:
        result = dbx.files_list_folder(dropbox_path)
    except dropbox.exceptions.ApiError as e:
        print(f"Error listing {dropbox_path}: {e}")
        return False

    new_files = False
    
    while True:
        
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
                    
        if result.has_more:
            
            result = dbx.files_list_folder_continue(result.cursor)
            
        else:
        
            break
        
    return new_files

def process_folder(base_folder, folder):
    """
    Run your original STEP 1–7 processing logic
    on a given folder that’s already downloaded locally.
    """
    folder_path = os.path.join(base_folder, folder)

    # =========================================================================
    # REPLACED OLD LOGIC WITH NEW PROCESSING LOGIC (Start)
    # Reason: Creating non-distorted padded images and outputting PNGs instead of WebP.
    # =========================================================================

    # Initialize rembg session
    try:
        session = new_session('isnet-general-use')
    except Exception as e:
        print(f"Error initializing rembg session: {e}")
        return

    RESIZE_DIMENSION = (400, 270)
    PNG_DIMENSION = (500, 500)
    PRE_RESIZE_DIMENSION = (6000, 4000)

    # Process files
    file_list = os.listdir(folder_path)
    images_dir = os.path.join(folder_path, "images")
    png_folder = os.path.join(folder_path, "PNG") # Keep variable name compatible with old code

    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(png_folder, exist_ok=True)

    for file in file_list:
        input_path = os.path.join(folder_path, file)
        if not os.path.isfile(input_path):
            continue
        
        # Only process images
        if not file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
             continue
        
        # Skip already processed (if any, though we usually clean up)
        if file_path.lower().endswith('.png') and file not in os.listdir(original_dir): 
             # logic to avoid re-processing outputs if they are in root
             pass

        print(f"Processing: {input_path}")
        
        try:
            with open(input_path, 'rb') as i:
                input_data = i.read()
        except Exception as e:
            print(f"Error reading {input_path}: {e}")
            continue

        # --- Non-Distorted Pre-resize ---
        try:
            pre_process_img = Image.open(io.BytesIO(input_data)).convert("RGBA")
            width, height = pre_process_img.size
            
            if width > PRE_RESIZE_DIMENSION[0] or height > PRE_RESIZE_DIMENSION[1]:
                print(f"Resizing image to {PRE_RESIZE_DIMENSION} (padded) for stability.")
                pre_process_img = create_square_image(pre_process_img, PRE_RESIZE_DIMENSION, fill_color=(255, 255, 255, 255))
            
            buffer = io.BytesIO()
            pre_process_img.save(buffer, format="PNG")
            input_data = buffer.getvalue()
        except Exception as e:
             print(f"Error in pre-resize: {e}")
             continue

        # --- Background Removal ---
        try:
            output_data = remove(input_data, session=session)
            processed_img = Image.open(io.BytesIO(output_data)).convert("RGBA")
        except Exception as e:
            print(f"Error removing background: {e}")
            continue

        base_name = os.path.splitext(file)[0]

        # --- 1. Save Full-Size PNG (Root) ---
        root_output_path = os.path.join(folder_path, f"{base_name}.png")
        try:
            processed_img.save(root_output_path, "PNG")
            print(f"Saved full-size .png to root.")
        except Exception as e:
            print(f"Error saving root PNG: {e}")

        # --- 2. Save 'images' Folder (Resized 400x270 Padded PNG) ---
        final_images_img = create_square_image(processed_img, RESIZE_DIMENSION, fill_color=(0, 0, 0, 0))
        images_output_path = os.path.join(images_dir, f"{base_name}.png")
        try:
            final_images_img.save(images_output_path, "PNG")
            print(f"Saved resized .png to images/.")
        except Exception as e:
             print(f"Error saving images/ PNG: {e}")

        # --- 3. Save 'PNG' Folder (500x500 PNG, ONLY ONE FILE) ---
        if folder_path not in PNG_CREATED_FOLDERS:
            final_png_img = create_square_image(processed_img, PNG_DIMENSION, fill_color=(0, 0, 0, 0))
            png_output_path = os.path.join(png_folder, f"{base_name}.png")
            try:
                final_png_img.save(png_output_path, "PNG")
                PNG_CREATED_FOLDERS.add(folder_path)
                print(f"Saved 500x500 PNG to PNG/ (First image only).")
            except Exception as e:
                print(f"Error saving PNG/ file: {e}")
        
    # --- Cleanup Originals ---
    print("Cleaning up original files...")
    for f in os.listdir(folder_path):
        f_path = os.path.join(folder_path, f)
        if os.path.isfile(f_path) and f.lower().endswith(('.jpg', '.jpeg')):
            try:
                os.remove(f_path)
                print(f"Deleted original: {f}")
            except Exception as e:
                print(f"Error deleting {f}: {e}")

    '''
    # =========================================================================
    # OLD STEPS 1-6 COMMENTED OUT BELOW
    # =========================================================================

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
        remove_bg.save(webp_path, format="webp", optimize=True, quality=80)
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
    '''

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

    # Upload main .png
    # UPDATED: Changed from .webp to .png
    main_png_list = [x for x in os.listdir(folder_path) if x.endswith('.png')]
    for png_image in main_png_list:
        local_image_path = os.path.join(folder_path, png_image)
        server_path = f"{remote_folder_path}/{png_image}"
        try:
            ftp.size(server_path)
            print(f"'{server_path}' already exists on the remote server.")
        except ftplib.error_perm as e:
            if "550" in str(e):
                with open(local_image_path, 'rb') as f:
                    ftp.storbinary(f"STOR {server_path}", f)
                print(f"'{server_path}' transferred to the remote server.")
            else:
                print(f"Error checking '{png_image}': {str(e)}")

    '''
    # OLD WEBP UPLOAD COMMENTED OUT
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
    '''

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

    while True:
        for entry in result.entries:
            if isinstance(entry, dropbox.files.FolderMetadata):
                local_path = os.path.join(local_downloads, entry.name)
                os.makedirs(local_path, exist_ok=True)
                print(f"Checking folder: {entry.name}")
                
                has_new = download_dropbox_folder(local_path, entry.path_lower, last_run)
                if has_new:
                    try:
                        process_folder(local_downloads, entry.name)
                    except Exception as e:
                        print(f"Error processing {entry.name}: {e}")

        if result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
        else:
            break

    # Update timestamp once all folders are processed
    update_last_run_time()


if __name__ == "__main__":
    main()
