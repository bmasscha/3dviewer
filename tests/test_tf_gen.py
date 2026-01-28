
import sys
import os
import numpy as np

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import transfer_functions

def test_tf_generation():
    tfs = ["grayscale", "viridis", "plasma", "medical", "legacy_rainbow", 
           "ct_bone", "ct_soft_tissue", "ct_muscle", "ct_lung", 
           "legacy_cool_warm", "ct_sandstone", "ct_body",
           "cet_fire", "cet_rainbow", "cet_coolwarm", "cet_bkr", "cet_bky", "cet_glasbey", "cet_glasbey_dark",
           "cet_bgyw", "cet_bmy", "cet_kgy", "cet_gray", "cet_cwr", "cet_linear_kry_5_95_c72", "cet_blues", "cet_isolum"]
    
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
