import os
import time
import io
from rembg import remove
from PIL import Image
import pandas as pd
import ftplib

base_folder = "/Downloads"
ipw_folder_list = os.listdir(base_folder)

for folder in ipw_folder_list:
    
    folder_path = os.path.join(base_folder, folder)
    if not os.path.isdir(folder_path):
        continue

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
    # FTP CREDENTIALS
    ftp = ftplib.FTP('ipwstock.com', 'u307603549', 'password')
    remote_base_path = '/domains/ipwstock.com/public_html/public/dropbox/'
    
    remote_folder_path = os.path.join(remote_base_path, folder)
    ftp.cwd('/domains/ipwstock.com/public_html/public/dropbox/')

    # Check if the remote folder exists
    remote_folders = ftp.nlst()

    if folder not in remote_folders:
        ftp.mkd(remote_folder_path)
        print(f"'{folder}' created on the remote server.")

    # === Helper function to upload a folder recursively ===
    def upload_folder(local_path, remote_path):
        """Uploads all files in a folder to FTP, skipping existing files."""
        # Ensure remote directory exists
        try:
            ftp.mkd(remote_path)
            print(f"Created remote directory: {remote_path}")
        except ftplib.error_perm as e:
            if not str(e).startswith("550"):
                raise  # Only ignore 'already exists' errors

        # Upload all files in the folder
        for filename in os.listdir(local_path):
            local_file = os.path.join(local_path, filename)
            remote_file = f"{remote_path}/{filename}"

            if os.path.isfile(local_file):
                try:
                    ftp.size(remote_file)  # Check if file exists
                    print(f"'{remote_file}' already exists on the remote server.")
                except ftplib.error_perm as e:
                    if "550" in str(e):  # File not found
                        with open(local_file, 'rb') as f:
                            ftp.storbinary(f"STOR {remote_file}", f)
                        print(f"Uploaded: {remote_file}")
                    else:
                        print(f"Error checking '{remote_file}': {str(e)}")

    # === Upload main .webp files ===
    main_webp_list = [x for x in os.listdir(os.path.join(base_folder, folder)) if x.endswith('.webp')]
    for webp_image in main_webp_list:
        local_image_path = os.path.join(base_folder, folder, webp_image)
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

    # === Upload 'images' folder ===
    images_local = os.path.join(base_folder, folder, "images")
    if os.path.exists(images_local):
        images_remote = f"{remote_folder_path}/images"
        upload_folder(images_local, images_remote)

    # === Upload 'PNG' folder ===
    png_local = os.path.join(base_folder, folder, "PNG")
    if os.path.exists(png_local):
        png_remote = f"{remote_folder_path}/PNG"
        upload_folder(png_local, png_remote)
ftp.quit()