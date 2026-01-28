import h5py
import numpy as np
import os

test_file = 'test_dup.h5'
data = np.random.randint(0, 100, (1, 10, 10), dtype=np.uint16)
with h5py.File(test_file, 'w') as f:
    f.create_dataset('data', data=data)

try:
    with h5py.File(test_file, 'r') as f:
        ds = f['data']
        indices = [0, 0, 0]
        print(f"Indexing with {indices}...")
        res = ds[indices, :, :]
        print(f"Result shape: {res.shape}")
except Exception as e:
    print(f"Error: {e}")

if os.path.exists(test_file):
    os.remove(test_file)
