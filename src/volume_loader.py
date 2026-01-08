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

    def load_from_folder(self, folder_path, rescale_range=None):
        """
        Loads all .tif/.tiff files from the specified folder.
        Files are sorted alphabetically to ensure correct sequence.
        Returns the 3D numpy array (Z, Y, X) with uint16 dtype.
        
        rescale_range: tuple (min, max) to rescale from to (0, 65535).
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
        
        # Rescale if requested
        if rescale_range is not None:
            lower, upper = rescale_range
            print(f"Rescaling data from [{lower}, {upper}] to [0, 65535]...")
            
            # Use float32 for intermediate calculation to avoid overflow/underflow
            # then clip and convert back to uint16
            data_f = self.data.astype(np.float32)
            data_f = (data_f - lower) * 65535.0 / (upper - lower)
            
            # Clip to [0, 65535]
            data_f = np.clip(data_f, 0, 65535)
            self.data = data_f.astype(np.uint16)
        
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

    def get_quick_stats(self, folder_path, sample_count=5):
        """
        Fast scan of the folder to get dimensions, a few sample slices, and a histogram.
        Returns (width, height, depth, middle_slice, histogram, bin_edges)
        """
        extensions = ['*.tif', '*.tiff', '*.TIF', '*.TIFF']
        files = set()
        for ext in extensions:
            files.update(glob.glob(os.path.join(folder_path, ext)))
        files = sorted(list(files))
        
        if not files:
            return None
            
        depth = len(files)
        mid_idx = depth // 2
        
        try:
            mid_slice = tifffile.imread(files[mid_idx])
            h, w = mid_slice.shape
            
            # Sample a few more slices for a better histogram
            indices = np.linspace(0, depth - 1, sample_count, dtype=int)
            samples = []
            for idx in indices:
                samples.append(tifffile.imread(files[idx]))
            
            all_samples = np.array(samples)
            hist, bin_edges = np.histogram(all_samples, bins=256, range=(0, 65535))
            
            return {
                'width': w,
                'height': h,
                'depth': depth,
                'middle_slice': mid_slice,
                'histogram': hist,
                'bin_edges': bin_edges,
                'min': np.min(all_samples),
                'max': np.max(all_samples)
            }
        except Exception as e:
            print(f"Error in get_quick_stats: {e}")
            return None
