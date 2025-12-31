import os
import sys
import glob
import numpy as np
import tifffile

class VolumeLoader:
    def __init__(self):
        self.data = None
        self.width = 0
        self.height = 0
        self.depth = 0

    def load_from_folder(self, folder_path):
        """
        Loads all .tif/.tiff files from the specified folder.
        Files are sorted alphabetically to ensure correct sequence.
        Returns the 3D numpy array (Z, Y, X) with uint16 dtype.
        """
        # Find all tiff files
        extensions = ['*.tif', '*.tiff', '*.TIF', '*.TIFF']
        files = set() # Use set to avoid duplicates on case-insensitive filesystems
        for ext in extensions:
            files.update(glob.glob(os.path.join(folder_path, ext)))
        
        # Convert back to list and sort
        files = sorted(list(files))
        
        if not files:
            print(f"Error: No TIFF files found in {folder_path}")
            return None

        print(f"Found {len(files)} unique slices. Loading headers...")

        # Load first slice to get dimensions
        try:
            first_slice = tifffile.imread(files[0])
        except Exception as e:
            print(f"Error reading first file {files[0]}: {e}")
            return None

        self.height, self.width = first_slice.shape
        self.depth = len(files)

        print(f"Volume Dimensions: {self.width}x{self.height}x{self.depth}")

        # Pre-allocate memory (16-bit) as requested
        # Format: (Depth, Height, Width) - typical for numpy arrays of images
        self.data = np.zeros((self.depth, self.height, self.width), dtype=np.uint16)

        # Load all slices
        for i, f in enumerate(files):
            try:
                img = tifffile.imread(f)
                if img.shape != (self.height, self.width):
                    print(f"Warning: Slice {i} has different dimensions {img.shape}, resizing/skipping not implemented.")
                    continue
                self.data[i] = img
            except Exception as e:
                print(f"Error reading slice {i} ({f}): {e}")
        
        # Calculate stats
        min_val = np.min(self.data)
        max_val = np.max(self.data)
        mean_val = np.mean(self.data)
        
        print(f"Volume loaded successfully. Shape: {self.data.shape}, Dtype: {self.data.dtype}")
        print(f"Data Range: [{min_val}, {max_val}], Mean: {mean_val:.2f}")
        
        # Ensure data is little-endian (native x86) for OpenGL
        # if the data is big-endian (>u2), swap bytes
        if self.data.dtype.byteorder == '>' or (self.data.dtype.byteorder == '=' and sys.byteorder == 'big'):
            print("Converting Big-Endian data to Little-Endian for OpenGL...")
            self.data = self.data.byteswap().newbyteorder('<')
        
        # Also ensure it is contiguous in memory
        if not self.data.flags['C_CONTIGUOUS']:
             print("Making data C-contiguous...")
             self.data = np.ascontiguousarray(self.data)

        print(f"Memory usage: {self.data.nbytes / (1024*1024):.2f} MB")
        
        return self.data

    def get_texture_data(self):
        """
        Returns the data pointer or prepared data for OpenGL texture upload.
        """
        return self.data
