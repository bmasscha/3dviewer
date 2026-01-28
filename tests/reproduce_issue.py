import os
import sys
import numpy as np
import h5py

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from volume_loader import VolumeLoader

def test_single_slice_spectral():
    test_file = "test_single_slice.h5"
    # depth=1, height=384, width=384, channels=128
    shape = (1, 384, 384, 128)
    data = np.random.randint(0, 5000, shape, dtype=np.uint16)
    
    print(f"Creating test HDF5 file: {test_file} with shape {shape}")
    with h5py.File(test_file, 'w') as f:
        f.create_dataset('reconstruction', data=data)
    
    loader = VolumeLoader()
    
    try:
        print("Testing get_h5_quick_stats...")
        stats = loader.get_h5_quick_stats(test_file, channel_index=0)
        if stats:
            print(f"Stats result: {stats['width']}x{stats['height']}x{stats['depth']}, channels={stats['num_channels']}")
        else:
            print("Stats failed (returned None)")
            
        print("Testing load_from_h5 (channel 0)...")
        loaded_data = loader.load_from_h5(test_file, channel_index=0)
        if loaded_data is not None:
            print(f"Loaded shape: {loaded_data.shape}")
        else:
            print("Load failed (returned None)")
            
    except Exception as e:
        print(f"Exception during test: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)

if __name__ == "__main__":
    test_single_slice_spectral()
