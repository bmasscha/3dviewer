import h5py

def inspect_h5(filename):
    with h5py.File(filename, 'r') as f:
        def print_item(name, obj):
            print(name)
            for key, val in obj.attrs.items():
                print(f"  Attr: {key} = {val}")
            if isinstance(obj, h5py.Dataset):
                print(f"  Shape: {obj.shape}, Dtype: {obj.dtype}")

        f.visititems(print_item)

if __name__ == "__main__":
    inspect_h5("example_data/frog_recon_fdk.h5")
