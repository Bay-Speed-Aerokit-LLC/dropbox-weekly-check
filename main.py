from rembg import remove, new_session
from PIL import Image
import os
import sys
import glob
import io

# --- Configuration ---
# IMPORTANT: Update this to your correct root path (e.g., "C:/Users/levin/Downloads")
ROOT_DIR = "/Downloads" 
IMAGE_EXTENSIONS = ["jpg", "jpeg", "png"]
# **FIX 2:** Redefined RESIZE_DIMENSION to a square for non-distorted output
RESIZE_DIMENSION = (400, 270) # For the 'images' folder (will be fit and padded to this size)
PNG_DIMENSION = (500, 500)   # For the 'PNG' folder (already a square/padded output)
# Note: PRE_RESIZE_DIMENSION is set higher than necessary, but we'll stick to it.
PRE_RESIZE_DIMENSION = (6000, 4000) 

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

def remove_wheel_rim_background_precise(input_path: str, session):
    """
    Removes the background and organizes/formats the output files as required.
    Includes non-distorted pre-resize.
    """
    global PNG_CREATED_FOLDERS
    print(f"   Processing: {input_path}")
    
    # ... (Steps 1 & 2 - Reading, Pre-Resize to PRE_RESIZE_DIMENSION, and Padding - remain the same) ...
    # 1. --- Read Input Data & Pre-checks ---
    if not os.path.exists(input_path):
        print(f"   Error: Input file not found at {input_path}")
        return
    
    try:
        with open(input_path, 'rb') as i:
            input_data = i.read()
    except Exception as e:
        print(f"   Error reading {input_path}: {e}")
        return

    # 2. --- Non-Distorted Pre-resize (Input for rembg) ---
    pre_process_img = Image.open(io.BytesIO(input_data)).convert("RGBA")
    width, height = pre_process_img.size
    
    if width > PRE_RESIZE_DIMENSION[0] or height > PRE_RESIZE_DIMENSION[1]:
        print(f"   Resizing image from ({width}x{height}) to {PRE_RESIZE_DIMENSION} (padded square) for stability.")
        
        pre_process_img = create_square_image(pre_process_img, PRE_RESIZE_DIMENSION, fill_color=(255, 255, 255, 255))
    
    # Convert the PIL image back to binary data for rembg input
    buffer = io.BytesIO()
    pre_process_img.save(buffer, format="PNG") 
    input_data = buffer.getvalue()
    buffer.close()
    
    # --- Background Removal (using the 2000x2000 input_data) ---
    output_data = remove(
        input_data, 
        session=session,
        # We assume alpha_matting is False for stability (as per the crash report)
    )
    
    # Get paths and base name
    original_dir = os.path.dirname(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    
    # Convert raw output data to a PIL Image object
    processed_img = Image.open(io.BytesIO(output_data)).convert("RGBA")

    # Define new folder paths
    images_dir = os.path.join(original_dir, "images")
    png_dir = os.path.join(original_dir, "PNG")

    # Create the target folders if they don't exist
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(png_dir, exist_ok=True)

    # --- 3. Save Root Level (Full-Size PNG) ---
    root_output_path = os.path.join(original_dir, f"{base_name}.png")
    try:
        processed_img.save(root_output_path, "PNG") 
        print(f"   Saved full-size .png to: {os.path.basename(original_dir)}/")
    except Exception as e:
        print(f"   Error saving root PNG: {e}")

    # --- 4. Save to 'images' Folder (Resized 400x400 Padded PNG) ---
    # **FIX 2:** Use create_square_image to prevent distortion in the output.
    final_images_img = create_square_image(processed_img, RESIZE_DIMENSION, fill_color=(0, 0, 0, 0))
    
    images_output_path = os.path.join(images_dir, f"{base_name}.png")
    try:
        final_images_img.save(images_output_path, "PNG")
        print(f"   Saved resized {RESIZE_DIMENSION} (padded) .png to: {os.path.basename(images_dir)}/")
    except Exception as e:
        print(f"   Error saving resized PNG: {e}")

    # --- 5. Save to 'PNG' Folder (500x500 PNG, ONLY ONE FILE) ---
    if original_dir not in PNG_CREATED_FOLDERS:
        
        # This step already uses the distortion-free function
        final_png_img = create_square_image(processed_img, PNG_DIMENSION, fill_color=(0, 0, 0, 0))
        
        png_output_path = os.path.join(png_dir, f"{base_name}.png")
        
        try:
            final_png_img.save(png_output_path, "PNG")
            PNG_CREATED_FOLDERS.add(original_dir) 
            print(f"   Saved 500x500 PNG as {base_name}.png to: {os.path.basename(png_dir)}/ (First image only)")
        except Exception as e:
            print(f"   Error saving 500x500 PNG: {e}")
    else:
        print(f"   Skipping 500x500 PNG: PNG file already saved for this folder in {os.path.basename(png_dir)}/.")
        
def cleanup_original_image_files(root_directory):
    # ... (Cleanup function remains the same) ...
    print("\n--- Starting Original Image (.JPG/.JPEG) Cleanup ---")
    deleted_count = 0
    
    target_extensions = (".jpg", ".jpeg")
    
    for root, dirs, files in os.walk(root_directory):
        if root != root_directory and (os.path.basename(root) != "images"):
            for file in files:
                if file.lower().endswith(target_extensions):
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        print(f"   Deleted: {file_path}")
                        deleted_count += 1
                    except OSError as e:
                        print(f"   Error deleting {file_path}: {e}")
                        
    print(f"--- Cleanup Complete: {deleted_count} original files deleted. ---")
    
# --- Main Execution Loop ---
if __name__ == "__main__":
    
    # **FIX 1:** Switching to 'isnet-general-use' to solve the 'bad allocation' memory crash
    print("⏳ Switching to 'isnet-general-use' for memory stability...")
    try:
        session = new_session('isnet-general-use')
        print("✅ Session initialized.")
    except Exception as e:

        print(f"❌ CRITICAL ERROR: Could not initialize rembg session. Check your onnxruntime installation. Error: {e}")
        sys.exit(1)

    total_files_processed = 0
    all_subfolders = set()
    
    # Traverse the root directory and find all subdirectories
    for root, dirs, files in os.walk(ROOT_DIR):
        if root != ROOT_DIR:
             all_subfolders.add(root)

    print(f"\nFound {len(all_subfolders)} subfolders. Starting image processing...")

    for directory in sorted(list(all_subfolders)):
        print(f"\n--- Entering Folder: {directory} ---")
        
        for ext in IMAGE_EXTENSIONS:
            search_pattern = os.path.join(directory, f"*.{ext}")
            file_paths = glob.glob(search_pattern)
            
            for input_file in file_paths:
                remove_wheel_rim_background_precise(input_file, session)
                total_files_processed += 1

    # --- FINAL CLEANUP STEP ---
    cleanup_original_image_files(ROOT_DIR)

    print("\n==============================================")
    print(f"Batch Processing Complete. Total files processed: {total_files_processed}")
    print("==============================================")
    
# // Wheels need for upgrade
# W004-HB
# W013N-GM
# W023-BMF
# W101-BML
# W215-SMF
# W260-GB
# W724-GB
# W842-C
# 854-GB

# // NOT GOOD
# W314-WRL
# W802-SML
# W1303-GB


# // RE-GENERATE
# W579-GB+IL 
# W1516-BMG



    