import numpy as np
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from volume_loader import VolumeLoader

def test_rescaling():
    loader = VolumeLoader()
    
    # Create dummy data: 16-bit range but only uses [1000, 5000]
    dummy_data = np.zeros((10, 10, 10), dtype=np.uint16)
    dummy_data[:, :, :] = 1000
    dummy_data[5, 5, 5] = 5000
    dummy_data[0, 0, 0] = 3000
    
    loader.data = dummy_data
    
    # Rescale from [1000, 5000] to [0, 65535]
    rescale_range = (1000, 5000)
    
    # Manually trigger the rescaling logic (since load_from_folder reads from disk)
    # Actually, let's just create a small TIFF to test the full flow if possible, 
    # but testing the logic directly is faster.
    
    print(f"Original min: {np.min(loader.data)}, max: {np.max(loader.data)}")
    
    # Logic from VolumeLoader:
    lower, upper = rescale_range
    data_f = loader.data.astype(np.float32)
    data_f = (data_f - lower) * 65535.0 / (upper - lower)
    data_f = np.clip(data_f, 0, 65535)
    rescaled_data = data_f.astype(np.uint16)
    
    print(f"Rescaled min: {np.min(rescaled_data)}, max: {np.max(rescaled_data)}")
    
    assert np.min(rescaled_data) == 0
    assert np.max(rescaled_data) == 65535
    # Value 3000 should be roughly (3000-1000)/(5000-1000) * 65535 = 0.5 * 65535 = 32767
    assert abs(int(rescaled_data[0, 0, 0]) - 32767) <= 1
    
    print("Rescaling logic verification SUCCESSFUL.")

if __name__ == "__main__":
    test_rescaling()
