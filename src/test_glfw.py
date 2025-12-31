import glfw
import sys

with open("test_glfw.log", "w") as f:
    f.write("Start\n")
    if not glfw.init():
        f.write("Init failed\n")
        sys.exit(1)
    f.write("Init ok\n")
    
    window = glfw.create_window(100, 100, "Test", None, None)
    if not window:
        f.write("Window failed\n")
        glfw.terminate()
        sys.exit(1)
    f.write("Window ok\n")
    glfw.terminate()
    f.write("Done\n")
