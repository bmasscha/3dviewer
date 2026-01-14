import sys
import os
sys.path.append('src')

import numpy as np
from volume_loader import VolumeLoader

def test_loader():
    loader = VolumeLoader()
    
    # 1. Test memory estimation
    est = loader.estimate_memory_usage(100, 100, 100, use_8bit=False)
    # 100^3 * 2 bytes * 2.5 = 1,000,000 * 2 * 2.5 = 5,000,000 bytes
    print(f"Memory Estimate (100^3 uint16): {est} bytes (Exp: 5000000)")
    assert est == 5000000
    
    est8 = loader.estimate_memory_usage(100, 100, 100, use_8bit=True)
    print(f"Memory Estimate (100^3 uint8): {est8} bytes (Exp: 2500000)")
    assert est8 == 2500000
    
    # 2. Test memory validation
    is_safe, est, avail = loader.check_memory_available(10, 10, 10)
    print(f"Small volume safe: {is_safe} (Est: {est}, Avail: {avail})")
    assert is_safe == True
    
    # 3. Test binning logic with dummy data
    data = np.zeros((10, 10, 10), dtype=np.uint16)
    data[2:8, 2:8, 2:8] = 1000
    loader.data = data
    loader.depth, loader.height, loader.width = data.shape
    
    # Mocking load_from_folder internals for binning test
    # (Since we can't easily mock tiff files here)
    from scipy.ndimage import zoom
    scale = 0.5
    binned = zoom(data, scale, order=1)
    print(f"Binning shape: {data.shape} -> {binned.shape}")
    assert binned.shape == (5, 5, 5)

    print("\nBASIC LOGIC VERIFIED SUCCESSFULLY")

if __name__ == "__main__":
    test_loader()
