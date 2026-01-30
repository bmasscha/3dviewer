import numpy as np
import tifffile
import os
import glob

def reproduce_error(folder_path):
    extensions = ['*.tif', '*.tiff', '*.TIF', '*.TIFF']
    files = set()
    for ext in extensions:
        files.update(glob.glob(os.path.join(folder_path, ext)))
    files = sorted(list(files))
    
    if not files:
        print("No files found.")
        return
        
    sample_count = 5
    depth = len(files)
    indices = np.linspace(0, depth - 1, sample_count, dtype=int)
    samples = []
    for idx in indices:
        s = tifffile.imread(files[idx])
        print(f"Index {idx}, shape {s.shape}")
        samples.append(s)
    
    try:
        all_samples = np.array(samples)
        print("Success!")
    except Exception as e:
        print(f"Caught expected error: {e}")

if __name__ == "__main__":
    path = r"C:\code\antigravity\r2_gaussian\r2_gaussian\exports\lamino_bin2_jump4_optimized\iter_final"
    reproduce_error(path)
