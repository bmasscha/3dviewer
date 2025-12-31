import os
import glob
import tifffile
import numpy as np
from PIL import Image

def inspect_first_tiff():
    folder_path = r"C:\data\bert lego\recon"
    files = sorted(glob.glob(os.path.join(folder_path, "*.tif*")))
    
    # Redirect print to file
    with open("inspection_results.txt", "w") as log:
        def print_log(msg):
            print(msg)
            log.write(str(msg) + "\n")
            
        if not files:
            print_log("No TIFF files found.")
            return

        # Pick a middle slice to avoid empty ends
        idx = len(files) // 2
        f = files[idx]
        print_log(f"Inspecting file: {f}")
        
        try:
            data = tifffile.imread(f)
            print_log(f"Shape: {data.shape}")
            print_log(f"Dtype: {data.dtype}")
            print_log(f"Min: {np.min(data)}")
            print_log(f"Max: {np.max(data)}")
            print_log(f"Mean: {np.mean(data)}")
            
            # Check unique values
            unique_vals = np.unique(data)
            print_log(f"Unique values count: {len(unique_vals)}")
            # print_log(f"Sample unique values: {unique_vals[:20] if len(unique_vals) > 20 else unique_vals}")

            # Byte order
            print_log(f"Byte order: {data.dtype.byteorder}")
            
            # Check histogramish
            # Normalize to 0-255 for visualization
            normalized = ((data - np.min(data)) / (np.max(data) - np.min(data) + 1e-5) * 255).astype(np.uint8)
            
            # Save as PNG to verify visually (if possible to open) or just ASCII art it
            # Simple ASCII art of center crop
            h, w = data.shape
            center = normalized[h//2-20:h//2+20, w//2-20:w//2+20]
            print_log("\nCenter 40x40 crop (ASCII approximate):")
            chars = " .:-=+*#%@"
            for row in center:
                line = ""
                for pixel in row:
                    line += chars[pixel // 26]
                print_log(line)

        except Exception as e:
            print_log(f"Error reading {f}: {e}")

if __name__ == "__main__":
    inspect_first_tiff()
