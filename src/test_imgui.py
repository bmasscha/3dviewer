import glfw
import imgui
from imgui.integrations.glfw import GlfwRenderer
import sys

with open("test_imgui.log", "w") as f:
    f.write("Start\n")
    if not glfw.init():
        sys.exit(1)
    
    window = glfw.create_window(100, 100, "Test", None, None)
    if not window:
        glfw.terminate()
        sys.exit(1)
    glfw.make_context_current(window)
    f.write("Window created\n")
    
    try:
        imgui.create_context()
        f.write("Context created\n")
        impl = GlfwRenderer(window)
        f.write("Renderer created\n")
        
        imgui.new_frame()
        f.write("New frame\n")
        imgui.render()
        f.write("Render\n")
        impl.shutdown()
        f.write("Shutdown\n")
    except Exception as e:
        f.write(f"Error: {e}\n")
        
    glfw.terminate()
    f.write("Done\n")
