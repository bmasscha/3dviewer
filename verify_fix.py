
import sys
import os
import numpy as np

# Add src to path
sys.path.append(os.path.abspath('src'))

from volume_loader import VolumeLoader

def test_load_with_extra_args():
    loader = VolumeLoader()
    # Mocking a folder with no tiffs but we just want to see if the CALL works without TypeError
    # We expect it to fail gracefully with "No TIFF files found" but NOT with "unexpected keyword argument"
    try:
        loader.load_from_folder("non_existent_folder", channel_index=0)
        print("Call to load_from_folder with channel_index succeeded (expectedly didn't crash).")
    except TypeError as e:
        print(f"FAILED: Still getting TypeError: {e}")
    except Exception as e:
        # Other exceptions are expected since the folder doesn't exist
        print(f"Got expected exception (not a TypeError): {e}")

if __name__ == "__main__":
    test_load_with_extra_args()
