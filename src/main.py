import glfw
import OpenGL.GL as gl
import imgui
from imgui.integrations.glfw import GlfwRenderer
import sys
import os
import numpy as np
import glm
from volume_loader import VolumeLoader
from renderer import VolumeRenderer, ShaderProgram
from camera import Camera
import transfer_functions

# Global State
window_width, window_height = 1280, 720
volume_loader = VolumeLoader()
volume_renderer = VolumeRenderer()
camera = Camera(target=(0.5, 0.5, 0.5))
slice_indices = [0, 0, 0] # X, Y, Z
show_volume = True
last_mouse_pos = (0, 0)
mouse_pressed = False
start_mouse_pos = (0, 0) # For simple drag check
density_multiplier = 50.0
threshold = 0.06 # Assuming background ~4000/65535 ~= 0.06
current_tf_name = "grayscale"
tf_names = ["grayscale", "viridis", "plasma", "medical"]

def load_shaders():
    try:
        path = os.path.dirname(__file__)
        slice_vert = open(os.path.join(path, 'shaders/slice.vert')).read()
        slice_frag = open(os.path.join(path, 'shaders/slice.frag')).read()
        ray_vert = open(os.path.join(path, 'shaders/raymarch.vert')).read()
        ray_frag = open(os.path.join(path, 'shaders/raymarch.frag')).read()
        
        slice_prog = ShaderProgram(slice_vert, slice_frag)
        ray_prog = ShaderProgram(ray_vert, ray_frag)
        return slice_prog, ray_prog
    except Exception as e:
        print(f"Failed to load shaders: {e}")
        return None, None

def render_quad():
    """Renders a full-screen quad (for slice or volume view)"""
    gl.glBegin(gl.GL_QUADS)
    gl.glTexCoord2f(0.0, 0.0); gl.glVertex3f(-1.0, -1.0, 0.0)
    gl.glTexCoord2f(1.0, 0.0); gl.glVertex3f( 1.0, -1.0, 0.0)
    gl.glTexCoord2f(1.0, 1.0); gl.glVertex3f( 1.0,  1.0, 0.0)
    gl.glTexCoord2f(0.0, 1.0); gl.glVertex3f(-1.0,  1.0, 0.0)
    gl.glEnd()

def mouse_callback(window, xpos, ypos):
    global last_mouse_pos, mouse_pressed
    if not mouse_pressed:
        last_mouse_pos = (xpos, ypos)
        return
        
    xoffset = xpos - last_mouse_pos[0]
    yoffset = last_mouse_pos[1] - ypos # reversed since y-coordinates go from bottom to top
    last_mouse_pos = (xpos, ypos)
    
    camera.process_mouse_movement(xoffset, yoffset)

def scroll_callback(window, xoffset, yoffset):
    if not imgui.get_io().want_capture_mouse:
        camera.process_scroll(yoffset)

def mouse_button_callback(window, button, action, mods):
    global mouse_pressed
    if button == glfw.MOUSE_BUTTON_LEFT:
        if action == glfw.PRESS:
            if not imgui.get_io().want_capture_mouse:
                mouse_pressed = True
        elif action == glfw.RELEASE:
            mouse_pressed = False

def framebuffer_size_callback(window, width, height):
    global window_width, window_height
    window_width = width
    window_height = height
    gl.glViewport(0, 0, width, height)

def main():
    global slice_indices
    global density_multiplier
    global threshold
    global current_tf_name
    
    with open("app.log", "w", encoding="utf-8") as log_file:
        # Redirect stdout/stderr to this file
        sys.stdout = log_file
        sys.stderr = log_file
        
        def log(msg):
            print(msg)
            # log_file.write(msg + "\n") # Print already writes to log_file now
            log_file.flush()

        log("Starting main...")
        try:
            if not glfw.init():
                log("GLFW initialization failed!")
                return
            log("GLFW initialized.")
            
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3) 
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
            glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_COMPAT_PROFILE)

            window = glfw.create_window(window_width, window_height, "Volume Viewer", None, None)
            if not window:
                log("Failed to create GLFW window")
                glfw.terminate()
                return
            log("Window created.")

            glfw.make_context_current(window)
            
            # --- Input Handling Setup ---
            # Callback for Scroll (chained)
            imgui.create_context()
            impl = GlfwRenderer(window)
            
            # Note: GlfwRenderer installs its own callbacks. We need to chain ours for scroll.
            # For mouse position/buttons, we will POLL in the main loop to handle "drag" behavior 
            # more flexibly without fighting ImGui's consumption logic on every event.
            
            imgui_scroll_callback = glfw.set_scroll_callback(window, None)
            
            def user_scroll_callback(window, xoffset, yoffset):
                if imgui_scroll_callback:
                    imgui_scroll_callback(window, xoffset, yoffset)
                if not imgui.get_io().want_capture_mouse:
                    camera.process_scroll(yoffset)

            glfw.set_scroll_callback(window, user_scroll_callback)
            glfw.set_framebuffer_size_callback(window, framebuffer_size_callback)

            log("Context made current and inputs hooked.")
            
            # Load Shaders
            slice_shader, ray_shader = load_shaders()
            if not slice_shader or not ray_shader:
                log("Failed to load shaders")
                return

            # Init default Transfer Function
            log(f"Generating colormap for {current_tf_name}...")
            tf_data = transfer_functions.get_colormap(current_tf_name)
            log(f"Colormap generated. Shape: {tf_data.shape}. Calling create_tf_texture...")
            volume_renderer.create_tf_texture(tf_data)
            log("create_tf_texture returned.")

            # Dummy Data initialization (commented out or functional as needed)
            
            # Generate on startup
            folder_path_default = r"C:\data\bert lego\recon"
            if os.path.exists(folder_path_default):
                if volume_loader.data is None:
                     log(f"Loading default data from {folder_path_default}")
                     data = volume_loader.load_from_folder(folder_path_default)
                     if data is not None:
                         d, h, w = data.shape
                         volume_renderer.create_texture(data, w, h, d)
                         slice_indices = [w//2, h//2, d//2]

            while not glfw.window_should_close(window):
                glfw.poll_events()
                impl.process_inputs()
                
                # --- POLLING INPUT ---
                # Handle mouse drag for camera (Arcball)
                state = glfw.get_mouse_button(window, glfw.MOUSE_BUTTON_LEFT)
                if state == glfw.PRESS:
                    # Current Mouse Position
                    xpos, ypos = glfw.get_cursor_pos(window)
                    
                    # specific viewport handling (Bottom-Right)? Or global?
                    # Let's use Global Window for interaction to be easy.
                    # Normalize to [-1, 1]
                    ndc_x = (xpos / window_width) * 2.0 - 1.0
                    ndc_y = 1.0 - (ypos / window_height) * 2.0 # Flip Y
                    
                    # Clamp for safety (though not strictly needed if outside)
                    ndc_x = max(-1.0, min(1.0, ndc_x))
                    ndc_y = max(-1.0, min(1.0, ndc_y))

                    if not mouse_pressed:
                        # Just pressed
                        if not imgui.get_io().want_capture_mouse:
                            mouse_pressed = True
                            last_mouse_pos = (ndc_x, ndc_y)
                    else:
                        # Dragging
                        # Pass previous and current NDC to camera
                        camera.rotate(last_mouse_pos[0], last_mouse_pos[1], ndc_x, ndc_y)
                        last_mouse_pos = (ndc_x, ndc_y) # Update 'prev' for next frame (incremental)
                else:
                    mouse_pressed = False
                # ---------------------

                imgui.new_frame()
                
                # --- UI Logic ---
                imgui.begin("Controls")
                
                # dummy buttons
                if imgui.button("Generate Dummy Data"):
                    # inline generate dummy data logic
                     print("Generating dummy data...")
                     volume_loader.data = np.random.randint(0, 65535, (100, 256, 256), dtype=np.uint16)
                     volume_renderer.create_texture(volume_loader.data, 256, 256, 100)
                     slice_indices = [256//2, 256//2, 100//2]
                     # Ensure TF is up to date (though generic is fine)
                     volume_renderer.create_tf_texture(transfer_functions.get_colormap(current_tf_name))

                # Text input for folder path
                changed, folder_path = imgui.input_text("Folder Path", folder_path_default, 256)
                if imgui.button("Load"):
                    if os.path.exists(folder_path):
                        data = volume_loader.load_from_folder(folder_path)
                        if data is not None:
                            d, h, w = data.shape
                            volume_renderer.create_texture(data, w, h, d)
                            slice_indices = [w//2, h//2, d//2]
                
                if volume_loader.data is not None:
                    max_d, max_h, max_w = volume_loader.data.shape
                    _, slice_indices[0] = imgui.slider_int("Slice X", slice_indices[0], 0, max_w - 1)
                    _, slice_indices[1] = imgui.slider_int("Slice Y", slice_indices[1], 0, max_h - 1)
                    _, slice_indices[2] = imgui.slider_int("Slice Z", slice_indices[2], 0, max_d - 1)

                    _, density_multiplier = imgui.slider_float("Density", density_multiplier, 0.1, 100.0)
                    _, threshold = imgui.slider_float("Threshold", threshold, 0.0, 1.0)
                    
                    # Transfer Function Selector
                    if imgui.begin_combo("Transfer Function", current_tf_name):
                        for name in tf_names:
                            is_selected = (name == current_tf_name)
                            if imgui.selectable(name, is_selected)[0]:
                                current_tf_name = name
                                # Update texture
                                tf_data = transfer_functions.get_colormap(current_tf_name)
                                volume_renderer.create_tf_texture(tf_data)
                            if is_selected:
                                imgui.set_item_default_focus()
                        imgui.end_combo()

                imgui.text(f"FPS: {imgui.get_io().framerate:.1f}")
                imgui.end()

                # --- Rendering Logic ---
                gl.glClearColor(0.0, 0.0, 0.0, 1.0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
                
                if volume_renderer.texture_ids:
                    volume_renderer.bind_texture(0)
                    # Correct unpacking based on renderer: volume_dim = (Width, Height, Depth)
                    vol_w, vol_h, vol_d = volume_renderer.volume_dims[0]
                    
                    # Split screen into 4 quadrants
                    # Top-Left: Axial (Z) - XY Plane
                    gl.glViewport(0, window_height//2, window_width//2, window_height//2)
                    slice_shader.use()
                    slice_shader.set_int("volumeTexture", 0)
                    slice_shader.set_int("axis", 0)
                    slice_shader.set_float("sliceDepth", slice_indices[2] / max(1, vol_d-1))
                    slice_shader.set_float("densityMultiplier", density_multiplier)
                    slice_shader.set_float("threshold", threshold)
                    render_quad()

                    # Top-Right: Coronal (Y) - XZ Plane
                    gl.glViewport(window_width//2, window_height//2, window_width//2, window_height//2)
                    slice_shader.use()
                    slice_shader.set_int("axis", 1)
                    slice_shader.set_float("sliceDepth", slice_indices[1] / max(1, vol_h-1))
                    slice_shader.set_float("densityMultiplier", density_multiplier)
                    slice_shader.set_float("threshold", threshold)
                    render_quad()

                    # Bottom-Left: Sagittal (X) - YZ Plane
                    gl.glViewport(0, 0, window_width//2, window_height//2)
                    slice_shader.use()
                    slice_shader.set_int("axis", 2)
                    slice_shader.set_float("sliceDepth", slice_indices[0] / max(1, vol_w-1))
                    slice_shader.set_float("densityMultiplier", density_multiplier)
                    slice_shader.set_float("threshold", threshold)
                    render_quad()

                    # Bottom-Right: 3D Raymarching
                    gl.glViewport(window_width//2, 0, window_width//2, window_height//2)
                    ray_shader.use()
                    ray_shader.set_int("volumeTexture", 0)
                    ray_shader.set_vec3("camPos", camera.position.x, camera.position.y, camera.position.z)
                    
                    # Construct camera frame for shader
                    view = camera.get_view_matrix() # 4x4
                    # Extract direction vectors from view matrix (inverse)
                    inv_view = glm.inverse(view)
                    
                    # Forward is -Z in view space usually, checking GLM... GLM lookAt: -Z is forward
                    # Unpack vectors for set_vec3
                    d = -inv_view[2].xyz
                    u = inv_view[1].xyz
                    r = inv_view[0].xyz
                    ray_shader.set_vec3("camDir", d.x, d.y, d.z) 
                    ray_shader.set_vec3("camUp", u.x, u.y, u.z)
                    ray_shader.set_vec3("camRight", r.x, r.y, r.z)
                    
                    ray_shader.set_vec3("camRight", r.x, r.y, r.z)
                    
                    ray_shader.set_vec2("resolution", window_width//2, window_height//2)
                    ray_shader.set_float("fov", camera.fov)

                    # Bind Transfer Function
                    volume_renderer.bind_tf_texture(1) # Unit 1
                    ray_shader.set_int("transferFunction", 1)

                    # Aspect Ratio Correction
                    max_dim = max(vol_w, max(vol_h, vol_d))
                    # Map (W, H, D) -> (X, Y, Z)
                    box_size = glm.vec3(vol_w/max_dim, vol_h/max_dim, vol_d/max_dim)
                    ray_shader.set_vec3("boxSize", box_size.x, box_size.y, box_size.z)
                    
                    render_quad()

                # Render UI over everything (reset viewport)
                gl.glViewport(0, 0, window_width, window_height)
                imgui.render()
                impl.render(imgui.get_draw_data())
                
                glfw.swap_buffers(window)

            impl.shutdown()
            glfw.terminate()
        except Exception as e:
            import traceback
            log(f"Crash during initialization: {e}")
            log(traceback.format_exc())
            return

if __name__ == "__main__":
    main()
