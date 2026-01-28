import os
import sys
import numpy as np
import h5py

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from volume_loader import VolumeLoader

def test_h5_loader():
    test_file = "test_volume.h5"
    shape = (10, 20, 30, 2) # 10 slices, 20 rows, 30 cols, 2 channels
    data = np.random.randint(0, 5000, shape, dtype=np.uint16)
    
    print(f"Creating test HDF5 file: {test_file}")
    with h5py.File(test_file, 'w') as f:
        f.create_dataset('reconstruction', data=data)
    
    loader = VolumeLoader()
    
    # Test loading channel 0
    print("Testing load_from_h5 (channel 0)...")
    loaded_data = loader.load_from_h5(test_file, channel_index=0)
    assert loaded_data is not None
    assert loaded_data.shape == (10, 20, 30)
    assert np.all(loaded_data == data[:, :, :, 0])
    
    # Test loading channel 1
    print("Testing load_from_h5 (channel 1)...")
    loaded_data = loader.load_from_h5(test_file, channel_index=1)
    assert loaded_data is not None
    assert loaded_data.shape == (10, 20, 30)
    assert np.all(loaded_data == data[:, :, :, 1])
    
    # Test stats
    print("Testing get_h5_quick_stats...")
    stats = loader.get_h5_quick_stats(test_file, channel_index=1)
    assert stats is not None
    assert stats['width'] == 30
    assert stats['height'] == 20
    assert stats['depth'] == 10
    assert stats['num_channels'] == 2
    
    print("All tests passed!")
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)

if __name__ == "__main__":
    test_h5_loader()
