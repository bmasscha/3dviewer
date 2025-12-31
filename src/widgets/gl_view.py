from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QMouseEvent, QWheelEvent
import OpenGL.GL as gl
import glm

class GLViewWidget(QOpenGLWidget):
    def __init__(self, core, mode="Axial", parent=None):
        super().__init__(parent)
        self.core = core
        self.mode = mode # "Axial", "Coronal", "Sagittal", "3D"
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.last_mouse_pos = (0, 0)
        self.mouse_pressed = False
        
        # Adaptive Quality State
        self.is_interacting = False
        self.interaction_timer = QTimer()
        self.interaction_timer.setSingleShot(True)
        self.interaction_timer.timeout.connect(self.on_interaction_timeout)

    def initializeGL(self):
        print(f"initializeGL called for mode: {self.mode}")
        # Initialize OpenGL state
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        
        # Ensure shaders are loaded
        if self.core.slice_shader is None:
            print("Loading shaders from GL context...")
            if not self.core.load_shaders():
                print("Failed to load shaders in GL context")
            else:
                print("Shaders loaded successfully.")

    def resizeGL(self, w, h):
        print(f"resizeGL called: {w}x{h}")
        gl.glViewport(0, 0, w, h)

    def paintGL(self):
        # print(f"paintGL called for mode: {self.mode}") # Too much noise
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        
        if not self.core.volume_renderer.texture_id:
            return

        if not self.core.slice_shader or not self.core.ray_shader:
            return

        vol_w, vol_h, vol_d = self.core.volume_renderer.volume_dim

        if self.mode in ["Axial", "Coronal", "Sagittal"]:
            self.core.slice_shader.use()
            self.core.volume_renderer.bind_texture(0)
            self.core.slice_shader.set_int("volumeTexture", 0)
            
            # Bind and set transfer function
            self.core.volume_renderer.bind_tf_texture(1)
            self.core.slice_shader.set_int("transferFunction", 1)
            
            if self.mode == "Axial":
                axis = 0
                depth = self.core.slice_indices[2] / max(1, vol_d-1)
            elif self.mode == "Coronal":
                axis = 1
                depth = self.core.slice_indices[1] / max(1, vol_h-1)
            else: # Sagittal
                axis = 2
                depth = self.core.slice_indices[0] / max(1, vol_w-1)
                
            self.core.slice_shader.set_int("axis", axis)
            self.core.slice_shader.set_float("sliceDepth", depth)
            self.core.slice_shader.set_float("densityMultiplier", self.core.slice_density)
            self.core.slice_shader.set_float("threshold", self.core.slice_threshold)
            self.core.slice_shader.set_float("tfSlope", self.core.tf_slope)
            self.core.slice_shader.set_float("tfOffset", self.core.tf_offset)
            self.render_quad()
            
        elif self.mode == "3D":
            # print("3D render call")
            self.core.ray_shader.use()
            self.core.volume_renderer.bind_texture(0)
            self.core.ray_shader.set_int("volumeTexture", 0)
            
            self.core.volume_renderer.bind_tf_texture(1)
            self.core.ray_shader.set_int("transferFunction", 1)
            
            camera = self.core.camera
            self.core.ray_shader.set_vec3("camPos", camera.position.x, camera.position.y, camera.position.z)
            
            view = camera.get_view_matrix()
            inv_view = glm.inverse(view)
            d = -inv_view[2].xyz
            u = inv_view[1].xyz
            r = inv_view[0].xyz
            
            self.core.ray_shader.set_vec3("camDir", d.x, d.y, d.z)
            self.core.ray_shader.set_vec3("camUp", u.x, u.y, u.z)
            self.core.ray_shader.set_vec3("camRight", r.x, r.y, r.z)
            
            self.core.ray_shader.set_vec2("resolution", self.width(), self.height())
            self.core.ray_shader.set_float("fov", camera.fov)
            
            # Unified Box Size and Alignment
            box_size = self.core.get_box_size()
            self.core.ray_shader.set_vec3("boxSize", box_size.x, box_size.y, box_size.z)
            
            self.core.ray_shader.set_int("renderMode", self.core.rendering_mode)
            self.core.ray_shader.set_float("densityMultiplier", self.core.volume_density)
            self.core.ray_shader.set_float("threshold", self.core.volume_threshold)
            self.core.ray_shader.set_float("lightIntensity", self.core.light_intensity)
            self.core.ray_shader.set_float("ambientLight", self.core.ambient_light)
            self.core.ray_shader.set_float("diffuseLight", self.core.diffuse_light)
            
            # Clipping
            self.core.ray_shader.set_vec3("clipMin", self.core.clip_min.x, self.core.clip_min.y, self.core.clip_min.z)
            self.core.ray_shader.set_vec3("clipMax", self.core.clip_max.x, self.core.clip_max.y, self.core.clip_max.z)
            
            
            # Lighting Mode
            if self.core.lighting_mode == 0: # Fixed
                lx, ly, lz = 0.5, 1.0, 0.5
            else: # Headlamp
                # Fixed: Use position - target to point TOWARDS the camera (direction to light)
                to_cam = glm.normalize(camera.position - camera.target)
                lx, ly, lz = to_cam.x, to_cam.y, to_cam.z
            self.core.ray_shader.set_vec3("lightDir", lx, ly, lz)
            
            # Rendering Quality
            # Default STEP_SIZE was 0.003, MAX_STEPS 512
            quality = self.core.sampling_rate
            if self.is_interacting:
                quality *= 0.25 # Reduce quality by 4x during interaction
                
            step_size = 0.003 / quality
            max_steps = int(512 * quality)
            self.core.ray_shader.set_float("stepSize", step_size)
            self.core.ray_shader.set_int("maxSteps", max_steps)
            self.core.ray_shader.set_float("tfSlope", self.core.tf_slope)
            self.core.ray_shader.set_float("tfOffset", self.core.tf_offset)
            
            self.render_quad()

    def render_quad(self):
        gl.glBegin(gl.GL_QUADS)
        gl.glTexCoord2f(0.0, 0.0); gl.glVertex3f(-1.0, -1.0, 0.0)
        gl.glTexCoord2f(1.0, 0.0); gl.glVertex3f( 1.0, -1.0, 0.0)
        gl.glTexCoord2f(1.0, 1.0); gl.glVertex3f( 1.0,  1.0, 0.0)
        gl.glTexCoord2f(0.0, 1.0); gl.glVertex3f(-1.0,  1.0, 0.0)
        gl.glEnd()

    def mousePressEvent(self, event: QMouseEvent):
        self.last_mouse_pos = (event.position().x(), event.position().y())
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed = True
        elif event.button() == Qt.MouseButton.RightButton:
            self.right_mouse_pressed = True

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed = False
        elif event.button() == Qt.MouseButton.RightButton:
            self.right_mouse_pressed = False

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.mode != "3D":
            return
            
        curr_x, curr_y = event.position().x(), event.position().y()
        
        # Calculate NDC diffs
        prev_ndc_x, prev_ndc_y = self.to_ndc(self.last_mouse_pos[0], self.last_mouse_pos[1])
        curr_ndc_x, curr_ndc_y = self.to_ndc(curr_x, curr_y)
        
        dx = curr_ndc_x - prev_ndc_x
        dy = curr_ndc_y - prev_ndc_y
        
        if self.mouse_pressed:
            self.core.camera.rotate(prev_ndc_x, prev_ndc_y, curr_ndc_x, curr_ndc_y)
            self.start_interaction()
            self.update()
        elif hasattr(self, 'right_mouse_pressed') and self.right_mouse_pressed:
            self.core.camera.pan(dx, dy)
            self.start_interaction()
            self.update()
            
        self.last_mouse_pos = (curr_x, curr_y)

    def wheelEvent(self, event: QWheelEvent):
        if self.mode == "3D":
            delta = event.angleDelta().y() / 120.0
            self.core.camera.process_scroll(delta)
            
            self.start_interaction()
            self.update()

    def start_interaction(self):
        self.is_interacting = True
        self.interaction_timer.start(200) # 200ms delay before snapping back to high quality

    def on_interaction_timeout(self):
        self.is_interacting = False
        self.update()

    def to_ndc(self, x, y):
        ndc_x = (x / self.width()) * 2.0 - 1.0
        ndc_y = 1.0 - (y / self.height()) * 2.0
        return max(-1.0, min(1.0, ndc_x)), max(-1.0, min(1.0, ndc_y))
