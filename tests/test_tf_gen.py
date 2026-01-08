
import sys
import os
import numpy as np

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import transfer_functions

def test_tf_generation():
    tfs = ["ct_bone", "ct_soft_tissue", "ct_muscle", "ct_lung", 
           "cool_warm", "ct_sandstone", "ct_body"]
    
    for name in tfs:
        print(f"Testing {name}...", end="", flush=True)
        try:
            tf = transfer_functions.get_colormap(name, size=256)
            
            # Check shape
            assert tf.shape == (256, 4), f"Shape mismatch: {tf.shape}"
            
            # Check range
            assert tf.min() >= 0.0, "Values < 0"
            assert tf.max() <= 1.0, "Values > 1"
            
            # Check for NaNs
            assert not np.isnan(tf).any(), "Contains NaNs"
            
            print("OK")
        except Exception as e:
            print(f"FAILED: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_tf_generation()
