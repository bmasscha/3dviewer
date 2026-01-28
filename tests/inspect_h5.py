import h5py
import os

filepath = 'example_data/example data spectral hdf_cor_192_recon.h5'
out_file = 'h5_inspect.log'

with open(out_file, 'w') as log:
    if os.path.exists(filepath):
        try:
            with h5py.File(filepath, 'r') as f:
                log.write(f"Keys: {list(f.keys())}\n")
                for key in f.keys():
                    item = f[key]
                    if isinstance(item, h5py.Dataset):
                        log.write(f"Dataset '{key}' shape: {item.shape}, dtype: {item.dtype}\n")
                    elif isinstance(item, h5py.Group):
                        log.write(f"Group '{key}' found. Contents: {list(item.keys())}\n")
        except Exception as e:
            log.write(f"Error: {e}\n")
    else:
        log.write("File not found.\n")

print("Done writing log.")
