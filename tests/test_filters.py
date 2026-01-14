import numpy as np
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import filters
import logging
logging.basicConfig(level=logging.INFO)

def test_bilateral_filter():
    # Create a noisy cube with LARGE integer range (simulating uint16)
    data = np.zeros((32, 32, 32), dtype=np.float32)
    data[10:22, 10:22, 10:22] = 40000.0 # High value
    noise = np.random.normal(0, 500, data.shape) # Large noise
    noisy_data = data + noise
    
    # Apply Bilateral
    # Use slightly stronger parameters for test stability
    filtered = filters.apply_3d_bilateral(noisy_data, sigma_spatial=2.0, sigma_color=0.1)
    
    assert filtered.shape == data.shape
    
    # Check Range Preservation
    assert np.max(filtered) > 1000.0, f"Max value {np.max(filtered)} implies data was not denormalized!"
    
    # Check if noise variance reduced
    std_in = np.std(noisy_data[:10,:10,:10])
    std_out = np.std(filtered[:10,:10,:10])
    print(f"Bilateral: Std IN={std_in:.2f}, Std OUT={std_out:.2f}")
    assert std_out < std_in
    print("Bilateral filter passed (Range Preserved).")

def test_nlm_filter():
    # Smaller volume for NLM speed
    data = np.zeros((16, 16, 16), dtype=np.float32)
    data[4:12, 4:12, 4:12] = 1.0
    noise = np.random.normal(0, 0.1, data.shape)
    noisy_data = data + noise
    
    # Apply NLM
    filtered = filters.apply_3d_nlm(noisy_data, h=1.15, patch_size=3, patch_distance=3)
    
    assert filtered.shape == data.shape
    assert np.std(filtered[:4,:4,:4]) < np.std(noisy_data[:4,:4,:4])
    print("NLM filter passed.")

def test_tv_filter():
    # Noisy cube
    data = np.zeros((32, 32, 32), dtype=np.float32)
    data[10:22, 10:22, 10:22] = 1.0
    noise = np.random.normal(0, 0.1, data.shape)
    noisy_data = data + noise
    
    # Apply TV
    filtered = filters.apply_3d_tv(noisy_data, weight=0.1)
    
    assert filtered.shape == data.shape
    # TV should make flat regions very flat
    assert np.std(filtered[:5,:5,:5]) < np.std(noisy_data[:5,:5,:5])
    print("TV filter passed.")

if __name__ == "__main__":
    try:
        test_bilateral_filter()
        test_nlm_filter()
        test_tv_filter()
        print("All filter tests passed!")
    except ImportError as e:
        print(f"ImportError: {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Test failed: {e}")
