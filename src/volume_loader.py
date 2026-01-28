import os
import sys
import glob
import numpy as np
import tifffile
import h5py
import psutil
from scipy.ndimage import zoom

class VolumeLoader:
    def __init__(self):
        self.data = None
        self.width = 0
        self.height = 0
        self.depth = 0

    def estimate_memory_usage(self, width, height, depth, use_8bit=False):
        """Estimate memory usage in bytes for the volume and OpenGL texture."""
        bytes_per_voxel = 1 if use_8bit else 2
        volume_bytes = width * height * depth * bytes_per_voxel
        # Estimate total impact including CPU array, OpenGL texture, and intermediate copies
        return volume_bytes * 2.5

    def check_memory_available(self, width, height, depth, use_8bit=False):
        """Check if enough system memory is available."""
        estimated = self.estimate_memory_usage(width, height, depth, use_8bit)
        available = psutil.virtual_memory().available
        # Allow use up to 80% of available RAM
        return estimated < (available * 0.8), estimated, available

    def load_from_folder(self, folder_path, rescale_range=None, z_range=None, binning_factor=1, use_8bit=False, progress_callback=None):
        """
        Loads .tif/.tiff files from the specified folder with optional reduction.
        
        rescale_range: tuple (min, max) to rescale from to (0, 65535) or (0, 255).
        z_range: tuple (start, end) of slice indices to load.
        binning_factor: factor for spatial downsampling (e.g. 2 for 2x2x2).
        use_8bit: if True, converts data to uint8.
        progress_callback: optional function(message) to call for progress updates.
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

        # Apply Z-range cropping if requested
        if z_range is not None:
            z_start, z_end = z_range
            z_start = max(0, z_start)
            z_end = min(self.depth, z_end)
            files = files[z_start:z_end]
            self.depth = len(files)
            print(f"Applied Z-range crop: {z_start} to {z_end}. Remaining depth: {self.depth}")

        print(f"Volume Dimensions: {self.width}x{self.height}x{self.depth}")

        # Check memory
        is_safe, estimated, available = self.check_memory_available(self.width, self.height, self.depth, use_8bit)
        print(f"Memory Check: Estimated {estimated/1e9:.2f} GB, Available {available/1e9:.2f} GB")
        if not is_safe:
            print(f"CRITICAL: Insufficient memory to load dataset!")
            # We skip hard error here for now to allow expert users to try, 
            # but in UI we will block it.

        # Pre-allocate memory
        # If rescaling will be applied, we need to load in original dtype first, then rescale
        # Otherwise we can load directly into target dtype
        if rescale_range is not None:
            # Load as original dtype, will convert after rescaling
            load_dtype = None  # Will be inferred from the data
            self.data = []  # Use list temporarily
        else:
            # No rescaling, load directly to target dtype
            target_dtype = np.uint8 if use_8bit else np.uint16
            self.data = np.zeros((self.depth, self.height, self.width), dtype=target_dtype)

        # Load slices
        for i, f in enumerate(files):
            # Report progress every 10 slices
            if progress_callback and i % 10 == 0:
                progress_callback(f"Loading slice {i+1}/{self.depth}...")
            
            try:
                img = tifffile.imread(f)
                if img.shape != (self.height, self.width):
                    print(f"Warning: Slice {i} has different dimensions {img.shape}, skipping.")
                    continue
                
                if rescale_range is not None:
                    # Keep original dtype for rescaling
                    self.data.append(img)
                else:
                    # No rescaling - convert to target dtype immediately
                    if use_8bit:
                        if img.dtype == np.uint16:
                            self.data[i] = (img >> 8).astype(np.uint8)
                        else:
                            self.data[i] = img.astype(np.uint8)
                    else:
                        self.data[i] = img
            except Exception as e:
                print(f"Error reading slice {i} ({f}): {e}")
        
        # Convert list to array if we were collecting for rescaling
        if rescale_range is not None:
            self.data = np.array(self.data)
        
        # Rescale if requested
        if rescale_range is not None:
            lower, upper = rescale_range
            target_dtype = np.uint8 if use_8bit else np.uint16
            target_max = 255 if use_8bit else 65535
            print(f"Rescaling data from [{lower}, {upper}] to [0, {target_max}]...")
            
            data_f = self.data.astype(np.float32)
            data_f = (data_f - lower) * float(target_max) / (upper - lower)
            data_f = np.clip(data_f, 0, target_max)
            self.data = data_f.astype(target_dtype)

        # Apply spatial binning if requested
        if binning_factor > 1:
            if progress_callback:
                progress_callback(f"Applying {binning_factor}x{binning_factor}x{binning_factor} binning...")
            print(f"Applying spatial binning (factor {binning_factor})...")
            # zoom expects (z, y, x)
            scale = 1.0 / binning_factor
            self.data = zoom(self.data, scale, order=1) # Linear interpolation
            self.depth, self.height, self.width = self.data.shape
            print(f"New Dimensions after binning: {self.width}x{self.height}x{self.depth}")
        
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

    def load_from_h5(self, file_path, channel_index=0, rescale_range=None, z_range=None, binning_factor=1, use_8bit=False, progress_callback=None):
        """
        Loads volumetric data from an HDF5 file. 
        Expects a 'reconstruction' dataset with shape (slices, rows, cols, channels) or (slices, rows, cols).
        """
        if not os.path.exists(file_path):
            print(f"Error: File not found {file_path}")
            return None

        try:
            with h5py.File(file_path, 'r') as f:
                if 'reconstruction' not in f:
                    print(f"Error: 'reconstruction' dataset not found in {file_path}")
                    return None
                
                ds = f['reconstruction']
                shape = ds.shape
                
                # Handle 4D (slices, rows, cols, channels)
                if len(shape) == 4:
                    self.depth, self.height, self.width, num_channels = shape
                    if channel_index >= num_channels:
                        print(f"Warning: Channel index {channel_index} out of range ({num_channels}), using 0.")
                        channel_index = 0
                elif len(shape) == 3:
                    self.depth, self.height, self.width = shape
                    num_channels = 1
                else:
                    print(f"Error: Unexpected dataset shape {shape}")
                    return None

                print(f"H5 Volume Dimensions: {self.width}x{self.height}x{self.depth}, Channels: {num_channels}")

                # Apply Z-range cropping if requested
                z_start, z_end = 0, self.depth
                if z_range is not None:
                    z_start, z_end = z_range
                    z_start = max(0, z_start)
                    z_end = min(self.depth, z_end)
                
                cur_depth = z_end - z_start
                
                # Check memory
                is_safe, estimated, available = self.check_memory_available(self.width, self.height, cur_depth, use_8bit)
                print(f"Memory Check: Estimated {estimated/1e9:.2f} GB, Available {available/1e9:.2f} GB")
                # We continue anyway, as in load_from_folder

                # Load data
                if progress_callback:
                    progress_callback(f"Reading HDF5 dataset (channel {channel_index})...")

                if len(shape) == 4:
                    raw_data = ds[z_start:z_end, :, :, channel_index]
                else:
                    raw_data = ds[z_start:z_end, :, :]

                self.depth = cur_depth

                # Rescale if requested
                if rescale_range is not None:
                    lower, upper = rescale_range
                    target_dtype = np.uint8 if use_8bit else np.uint16
                    target_max = 255 if use_8bit else 65535
                    print(f"Rescaling data from [{lower}, {upper}] to [0, {target_max}]...")
                    
                    data_f = raw_data.astype(np.float32)
                    data_f = (data_f - lower) * float(target_max) / (upper - lower)
                    data_f = np.clip(data_f, 0, target_max)
                    self.data = data_f.astype(target_dtype)
                else:
                    target_dtype = np.uint8 if use_8bit else np.uint16
                    if use_8bit:
                        if raw_data.dtype == np.uint16:
                            self.data = (raw_data >> 8).astype(np.uint8)
                        else:
                            self.data = raw_data.astype(np.uint8)
                    else:
                        self.data = raw_data.astype(np.uint16)

                # Apply spatial binning if requested
                if binning_factor > 1:
                    if progress_callback:
                        progress_callback(f"Applying {binning_factor}x{binning_factor}x{binning_factor} binning...")
                    scale = 1.0 / binning_factor
                    self.data = zoom(self.data, scale, order=1)
                    self.depth, self.height, self.width = self.data.shape

                # Stats and preparation
                min_val = np.min(self.data)
                max_val = np.max(self.data)
                print(f"Volume loaded successfully. Shape: {self.data.shape}, Dtype: {self.data.dtype}")
                print(f"Data Range: [{min_val}, {max_val}]")

                if self.data.dtype.byteorder == '>' or (self.data.dtype.byteorder == '=' and sys.byteorder == 'big'):
                    self.data = self.data.byteswap().newbyteorder('<')
                
                if not self.data.flags['C_CONTIGUOUS']:
                    self.data = np.ascontiguousarray(self.data)

                return self.data

        except Exception as e:
            print(f"Error loading HDF5 {file_path}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_h5_quick_stats(self, file_path, channel_index=0, sample_count=5):
        """
        Fast scan of HDF5 file to get dimensions, sample slices, and histogram.
        """
        if not os.path.exists(file_path):
            return None

        try:
            with h5py.File(file_path, 'r') as f:
                if 'reconstruction' not in f:
                    return None
                
                ds = f['reconstruction']
                shape = ds.shape
                
                num_channels = 1
                if len(shape) == 4:
                    d, h, w, num_channels = shape
                elif len(shape) == 3:
                    d, h, w = shape
                else:
                    return None

                mid_idx = d // 2
                indices = np.unique(np.linspace(0, d - 1, sample_count, dtype=int))
                if len(shape) == 4:
                    mid_slice = ds[mid_idx, :, :, channel_index]
                    samples = ds[indices, :, :, channel_index]
                else:
                    mid_slice = ds[mid_idx, :, :]
                    samples = ds[indices, :, :]

                hist, bin_edges = np.histogram(samples, bins=256, range=(0, 65535))
                
                return {
                    'width': w,
                    'height': h,
                    'depth': d,
                    'num_channels': num_channels,
                    'middle_slice': mid_slice,
                    'histogram': hist,
                    'bin_edges': bin_edges,
                    'min': np.min(samples),
                    'max': np.max(samples)
                }
        except Exception as e:
            print(f"Error in get_h5_quick_stats: {e}")
            return None

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
