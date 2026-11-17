import os
import re
import platform
import subprocess
import pandas as pd
from pathlib import Path
from PIL import Image

def process_file(file_path):
    qr = None
    C1 = C2 = C3 = None
    
    extracted_pairs = []
    
    with open(file_path, 'r') as file:
        iterator = iter(file)
        
        for line in iterator:
            # Extract QR Code if it appears
            if "QR CODE VALUE" in line or "QR CODE" in line:
                qr_text = next(iterator, None)
                if qr_text is not None:
                    qr = "A" + qr_text.strip()
            
            # Extract Settings
            elif "SETTINGS" in line:
                for data_line in iterator:
                    data_line = data_line.strip()
                    
                    # Exit the SETTINGS block immediately when an empty line is found
                    if not data_line:
                        break
                        
                    # Only process lines with a colon separator
                    if ':' not in data_line:
                        continue
                        
                    key, val = data_line.split(':', 1)
                    key = key.strip().lower()
                    val = val.strip()
                    
                    # Skip size and pixels
                    if "size" in key or "pixel" in key or "pix count" in key:
                        continue
                    
                    # Rename specific parameters
                    if key in ["exposure (ms)", "exposure time (ms)"]:
                        clean_key = "exposure_time_ms"
                    elif key == "focus distance (mm)":
                        clean_key = "focus_distance_ms"  
                    else:
                        # For any other parameters (like "light ring"), replace spaces with underscores
                        clean_key = key.replace(' ', '_')
                    
                    extracted_pairs.append(f"{clean_key}={val}")

    # Build the C1 string 
    if extracted_pairs:
        C1 = "| ".join(extracted_pairs)

    # Return the 4 variables (C2 and C3 remain None)
    return C1, C2, C3, qr


def rename_and_convert_bmp_files(base_dir, exiftool_cmd, cccc, bbbb):
    # Resolve converts a relative path like "." to a full absolute path
    base_path = Path(base_dir).resolve()
    
    # Define the shadow base path (e.g., D:\Downloads\ABC -> D:\Downloads\ABC_PNG)
    shadow_base_path = base_path.parent / f"{base_path.name}_PNG"
    
    # Dictionary to group files by their parent directory
    dir_files = {}
    
    # Use a set to prevent duplicate files on Windows 
    found_files = set()
    for ext in ['*.BMP', '*.bmp']:
        found_files.update(base_path.rglob(ext))

    # Group the unique files by their parent folder
    for file_path in found_files:
        parent_dir = file_path.parent
        if parent_dir not in dir_files:
            dir_files[parent_dir] = []
        dir_files[parent_dir].append(file_path)

    # Process each directory
    for parent_dir, files in dir_files.items():
        # Sort files chronologically by the timestamp/name (alphabetical order)
        files.sort(key=lambda x: x.name)
        
        # Determine SSSS based on parent folder name
        folder_name = parent_dir.name.upper()
        if folder_name == "TOP":
            ssss = "TOP1"
        elif folder_name == "BOTTOM":
            ssss = "BOT1"
        else:
            continue 

        # Look for log.txt in the parent of TOP/BOTTOM (e.g., BOARD1)
        log_path = parent_dir.parent / "log.txt"
        
        if log_path.exists():
            # Extract variables from log.txt
            C1, C2, C3, qr_variable = process_file(log_path)
            
            # Fallback if QR was not found in the log
            if not qr_variable:
                print(f"Warning: QR CODE not found in {log_path}. Using default.")
                qr_variable = "NO_QR"
        else:
            print(f"Warning: No log.txt found at {log_path}. Skipping folder {parent_dir}.")
            continue

        # Process files in sequence
        for index, file_path in enumerate(files):
            orig_name = file_path.stem  
            orig_ext = file_path.suffix 
            
            parts = orig_name.split('_')
            
            # --- Safely check if file is already renamed dynamically based on cccc/bbbb ---
            if orig_name.startswith(f"{cccc}_{bbbb}_"):
                new_file_path = file_path
                new_filename = file_path.name
                
                # In the new format (CCCC_BBBB_NNNN_SSSS_XXXX_YYYY_ZZZZ_PPPP), PPPP is index 7
                if len(parts) >= 8:
                    pppp = parts[7]
                else:
                    pppp = "P001" # fallback
                    
                print(f"Already renamed: {new_filename}. Proceeding to PNG conversion.")
            
            # --- If not yet renamed, rely entirely on alphabetical index logic ---
            else:
                if cccc == "CGNX":
                    # CGNX format: 1 frame per angle
                    angle_val = (index // 1) * 15
                    pppp = "P001"
                else:
                    # Original KYNC format: 3 frames per angle
                    angle_val = (index // 3) * 15
                    # Cycle through P001, P002, P003 based on index
                    pppp = f"P00{(index % 3) + 1}"

                nnnn = qr_variable 
                xxxx = "X000"
                yyyy = "Y000"
                zzzz = f"Z{angle_val:03d}"
                
                # Construct the new filename
                new_filename = f"{cccc}_{bbbb}_{nnnn}_{ssss}_{xxxx}_{yyyy}_{zzzz}_{pppp}{orig_ext}"
                new_file_path = parent_dir / new_filename
                
                if file_path.name != new_filename:
                    print(f"Renaming: {file_path.name} -> {new_filename}")
                    file_path.rename(new_file_path)

            # --- PNG Shadow Conversion ---
            relative_path = new_file_path.relative_to(base_path)
            shadow_file_path = (shadow_base_path / relative_path).with_suffix('.png')
            shadow_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Only convert to PNG if it hasn't already been created in a previous run
            if not shadow_file_path.exists():
                try:
                    with Image.open(new_file_path) as img:
                        img.save(shadow_file_path, "PNG")
                    print(f"  -> Converted and saved shadow PNG: {shadow_file_path.name}")
                    
                    # --- EXIF Tagging ---
                    comment = None
                    if pppp == "P001":
                        comment = C1
                    elif pppp == "P002":
                        comment = C2
                    elif pppp == "P003":
                        comment = C3
                    
                    if comment:
                        try:
                            subprocess.run([
                                exiftool_cmd,
                                f"-XMP:Description={comment}",
                                "-overwrite_original", 
                                str(shadow_file_path)
                            ], check=True, capture_output=True)
                            print(f"  -> Added EXIF tag to {shadow_file_path.name}")
                        except subprocess.CalledProcessError as e:
                            print(f"  -> Failed to add EXIF to {shadow_file_path.name}: {e.stderr.decode('utf-8')}")
                            
                except Exception as e:
                    print(f"  -> Failed to process PNG for {new_filename}: {e}")
            else:
                print(f"  -> PNG already exists, skipping conversion: {shadow_file_path.name}")


if __name__ == "__main__":    

    # Toggle these variables between CGNX and KYNC folders
    # TARGET_DIRECTORY = r"D:\Downloads\Keyence"; cccc = "KYNC"
    #TARGET_DIRECTORY = r"D:\Downloads\Cognex"; cccc = "CGNX"
    # TARGET_DIRECTORY = r"C:\Users\ank35\OneDrive - NIST\Code\pprs_projects\pcb_inspection\Downloads\Keyence"; cccc="KYNC"
    TARGET_DIRECTORY = r"C:\Users\ank35\OneDrive - NIST\Code\pprs_projects\pcb_inspection\Downloads\Cognex"; cccc="CGNX"


    bbbb = "RPI2"        
    
    # Determine the correct ExifTool command based on the OS
    if platform.system() == "Windows":
        EXIFTOOL_EXE = str(Path(__file__).with_name("exiftool.exe"))
    else:
        EXIFTOOL_EXE = "exiftool"
    
    rename_and_convert_bmp_files(TARGET_DIRECTORY, EXIFTOOL_EXE, cccc, bbbb)