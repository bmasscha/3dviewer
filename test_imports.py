import sys
print("Testing imports...")
try:
    import glfw
    print("glfw imported")
except ImportError as e:
    print(f"Failed to import glfw: {e}")

try:
    import OpenGL.GL as gl
    print("OpenGL imported")
except ImportError as e:
    print(f"Failed to import OpenGL: {e}")

try:
    import imgui
    print("imgui imported")
except ImportError as e:
    print(f"Failed to import imgui: {e}")

try:
    from imgui.integrations.glfw import GlfwRenderer
    print("imgui.integrations.glfw imported")
except ImportError as e:
    print(f"Failed to import imgui.integrations.glfw: {e}")

try:
    import numpy as np
    print("numpy imported")
except ImportError as e:
    print(f"Failed to import numpy: {e}")

try:
    import glm
    print("glm imported")
except ImportError as e:
    print(f"Failed to import glm: {e}")

try:
    import tifffile
    print("tifffile imported")
except ImportError as e:
    print(f"Failed to import tifffile: {e}")

try:
    import PIL
    print("Pillow imported")
except ImportError as e:
    print(f"Failed to import Pillow: {e}")

print("Import test complete.")
