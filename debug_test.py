
import sys
import os

with open("debug_output.txt", "w") as f:
    f.write("Debug script running.\n")
    try:
        import skimage
        f.write(f"Skimage version: {skimage.__version__}\n")
    except ImportError as e:
        f.write(f"ImportError: {e}\n")

    f.write("Running tests...\n")
    try:
        from tests import test_filters
        test_filters.test_bilateral_filter()
        test_filters.test_nlm_filter()
        test_filters.test_tv_filter()
        f.write("Tests passed.\n")
    except Exception as e:
        f.write(f"Tests failed: {e}\n")
