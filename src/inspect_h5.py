"""
Quick diagnostic tool to inspect HDF5 file structure and identify performance issues.
"""
import h5py
import sys
import numpy as np
import time

def inspect_h5_file(file_path):
    """Inspect HDF5 file structure, chunking, and compression."""
    print(f"Inspecting: {file_path}\n")
    print("=" * 80)

    with h5py.File(file_path, 'r') as f:
        # List all datasets
        print("DATASETS:")
        def print_dataset_info(name, obj):
            if isinstance(obj, h5py.Dataset):
                print(f"\n  Dataset: {name}")
                print(f"    Shape: {obj.shape}")
                print(f"    Dtype: {obj.dtype}")
                print(f"    Size: {obj.nbytes / 1e9:.2f} GB")
                print(f"    Chunks: {obj.chunks}")
                print(f"    Compression: {obj.compression}")
                if obj.compression:
                    print(f"    Compression opts: {obj.compression_opts}")
                print(f"    Shuffle filter: {obj.shuffle}")
                print(f"    Fletcher32 checksum: {obj.fletcher32}")

        f.visititems(print_dataset_info)

        # Focus on 'reconstruction' dataset
        print("\n" + "=" * 80)
        if 'reconstruction' in f:
            ds = f['reconstruction']
            print("RECONSTRUCTION DATASET ANALYSIS:")
            print(f"  Shape: {ds.shape}")

            if len(ds.shape) == 4:
                depth, height, width, channels = ds.shape
                print(f"  Dimensions: {width}x{height}x{depth} @ {channels} channels")
                print(f"  Total voxels: {depth * height * width * channels / 1e9:.2f}B")
                print(f"  Memory (all channels): {ds.nbytes / 1e9:.2f} GB")

                # Chunking analysis
                if ds.chunks:
                    chunk_d, chunk_h, chunk_w, chunk_c = ds.chunks
                    print(f"\n  CHUNKING LAYOUT:")
                    print(f"    Chunk shape: {ds.chunks}")
                    print(f"    Chunk size: {np.prod(ds.chunks) * ds.dtype.itemsize / 1e6:.2f} MB")
                    print(f"    Chunks per dimension:")
                    print(f"      Depth: {depth // chunk_d} chunks ({depth % chunk_d} remainder)")
                    print(f"      Height: {height // chunk_h} chunks ({height % chunk_h} remainder)")
                    print(f"      Width: {width // chunk_w} chunks ({width % chunk_w} remainder)")
                    print(f"      Channels: {channels // chunk_c} chunks ({channels % chunk_c} remainder)")

                    # Estimate reads per channel
                    if chunk_c < channels:
                        print(f"\n  ⚠️  PERFORMANCE WARNING:")
                        print(f"    Chunks span multiple channels (chunk_c={chunk_c}, total={channels})")
                        print(f"    Reading one channel requires reading {channels // chunk_c} times more data!")
                        print(f"    Recommendation: Load all channels at once, then split in memory")
                    else:
                        print(f"\n  ✓ OPTIMAL: Chunks are channel-separated (chunk_c={chunk_c})")

                # Benchmark read speed
                print("\n" + "=" * 80)
                print("BENCHMARK: Read Speed Test")

                # Test 1: Read single channel (current method)
                print("\n  Test 1: Read single channel (slice-by-slice)")
                mid_slice = depth // 2
                start = time.time()
                sample_data = ds[mid_slice:mid_slice+10, :, :, 0]  # 10 slices, channel 0
                elapsed1 = time.time() - start
                print(f"    Read 10 slices of channel 0: {elapsed1:.3f}s")
                print(f"    Data shape: {sample_data.shape}")
                print(f"    Estimated time for full channel: {elapsed1 * (depth / 10):.1f}s")

                # Test 2: Read all channels at once (optimized method)
                print("\n  Test 2: Read all channels at once (full slice)")
                start = time.time()
                sample_all = ds[mid_slice:mid_slice+10, :, :, :]  # 10 slices, all channels
                elapsed2 = time.time() - start
                print(f"    Read 10 slices, all {channels} channels: {elapsed2:.3f}s")
                print(f"    Data shape: {sample_all.shape}")
                print(f"    Estimated time for all channels: {elapsed2 * (depth / 10):.1f}s")
                print(f"    Speedup vs sequential: {(elapsed1 * channels) / elapsed2:.1f}x faster")

                # Test 3: Channel extraction from pre-loaded data
                print("\n  Test 3: Extract channels from loaded data (in-memory)")
                start = time.time()
                channel_0 = sample_all[:, :, :, 0]
                channel_1 = sample_all[:, :, :, 1]
                elapsed3 = time.time() - start
                print(f"    Extract 2 channels from memory: {elapsed3:.6f}s (negligible)")

                print("\n  RECOMMENDATION:")
                if ds.chunks and ds.chunks[3] < channels:
                    print("    ⚠️  Load entire 4D volume at once, then split channels in memory")
                    print("    This avoids redundant disk reads of the same chunks")
                else:
                    print("    ✓ Current channel-by-channel loading is acceptable")
        else:
            print("ERROR: No 'reconstruction' dataset found!")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_h5.py <path_to_h5_file>")
        sys.exit(1)

    inspect_h5_file(sys.argv[1])
