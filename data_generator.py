import numpy as np
import tifffile
import os

def generate_dummy_volume(output_dir="dummy_data", width=256, height=256, depth=100):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    print(f"Generating {width}x{height}x{depth} volume in {output_dir}...")
    
    # Create simple structure: Sphere in center + gradients
    x = np.linspace(-1, 1, width)
    y = np.linspace(-1, 1, height)
    z = np.linspace(-1, 1, depth)
    X, Y, Z = np.meshgrid(x, y, z, indexing='xy')
    
    radius = np.sqrt(X**2 + Y**2 + Z**2)
    
    # Normalize to 0-65535
    volume = np.clip(1.0 - radius, 0, 1) * 65535
    volume = volume.astype(np.uint16)
    
    # Save slices
    # Meshgrid result is (H, W, D) if indexing='xy' ? Wait using indexing='xy' 
    # meshgrid documentation:
    # x: columns (width), y: rows (height)
    # returns X (H,W,D), Y(H,W,D)
    
    # Transposing to (Depth, Height, Width) for saving
    # volume is currently (Height, Width, Depth)
    volume = volume.transpose(2, 0, 1) 
    
    for i in range(depth):
        filename = os.path.join(output_dir, f"slice_{i:04d}.tif")
        tifffile.imwrite(filename, volume[i])
        
    print("Done.")

if __name__ == "__main__":
    generate_dummy_volume()
