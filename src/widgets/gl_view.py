from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QMouseEvent, QWheelEvent, QAction
from PyQt6.QtWidgets import QMenu
import OpenGL.GL as gl
import glm

class GLViewWidget(QOpenGLWidget):
    sig_save_request = pyqtSignal(str) # "single" or "all"
    sig_export_slices = pyqtSignal(str) # Emits mode name (Axial/Coronal/Sagittal)
    sig_record_movie = pyqtSignal()

    def __init__(self, core, mode="Axial", parent=None):
        super().__init__(parent)
        self.core = core
        self.mode = mode # "Axial", "Coronal", "Sagittal", "3D"
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.last_mouse_pos = (0, 0)
        self.mouse_pressed = False
        self.right_mouse_pressed = False

        # Interaction State for Orthogonal Views
        self.view_zoom = 1.0
        self.view_offset = glm.vec2(0.0, 0.0)
        
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
        
        # Query hardware limits
        self.core.volume_renderer.query_limits()
        
        # Ensure shaders are loaded
        if self.core.slice_shader is None:
            print("Loading shaders from GL context...")
            if not self.core.load_shaders():
                print("Failed to load shaders in GL context")
            else:
                print("Shaders loaded successfully.")

        # Initialize FBO for Post-Processing
        self.init_fbo(self.width(), self.height())

    def init_fbo(self, w, h):
        # Create/Recreate FBO if size changed or not exists
        if hasattr(self, 'fbo') and self.fbo is not None:
             gl.glDeleteFramebuffers(1, [self.fbo])
             gl.glDeleteTextures(1, [self.fbo_texture])
        
        self.fbo = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        
        self.fbo_texture = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.fbo_texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, w, h, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, self.fbo_texture, 0)
        
        # Depth buffer for FBO is needed for depth testing during volume render
        self.fbo_depth = gl.glGenRenderbuffers(1)
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.fbo_depth)
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT, w, h)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER, self.fbo_depth)
        
        if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
            print("Error: Framebuffer is not complete!")
            
        # Restore default FBO
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.defaultFramebufferObject())

    def resizeGL(self, w, h):
        print(f"resizeGL called: {w}x{h}")
        gl.glViewport(0, 0, w, h)
        self.init_fbo(w, h)

    def paintGL(self):
        default_fbo = self.defaultFramebufferObject()
        
        # --- Pass 1: Render Volume to FBO ---
        if self.core.vpc_enabled and hasattr(self, 'fbo'):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        else:
            # Render directly to widget backbuffer
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, default_fbo) 
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        
        self.render_scene()
        
        # --- Pass 2: Apply VPC Filter (if enabled) ---
        if self.core.vpc_enabled and hasattr(self, 'fbo'):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, default_fbo) # Switch back to widget
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT) # Clear screen

            
            if self.core.vpc_shader:
                self.core.vpc_shader.use()
                
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self.fbo_texture)
                self.core.vpc_shader.set_int("textureSampler", 0)
                self.core.vpc_shader.set_float("distance", self.core.vpc_distance / 100.0) # Normalize?? 
                # User range 0-100, shader param usually small
                self.core.vpc_shader.set_float("wavelength", self.core.vpc_wavelength)
                self.core.vpc_shader.set_int("enabled", 1)
                
                self.render_quad()
            else:
                # Fallback: just draw the texture
                # (Ideally use a simple texture shader, but we can assume vpc_shader loads if we are here)
                pass

    def render_scene(self):
        if not self.core.volume_renderer.texture_ids:
            return

        if not self.core.slice_shader or not self.core.ray_shader:
            return

        vol_w, vol_h, vol_d = self.core.volume_renderer.volume_dims[0]

        if self.mode in ["Axial", "Coronal", "Sagittal"]:
            self.core.slice_shader.use()
            # Unit 0: Primary Volume
            self.core.volume_renderer.bind_texture(slot=0, unit=0)
            self.core.slice_shader.set_int("volumeTexture", 0)
            
            # Unit 1: Primary TF
            self.core.volume_renderer.bind_tf_texture(slot=0, unit=1)
            self.core.slice_shader.set_int("transferFunction", 1)
            
            # Overlay Volume and TF (Units 2 and 3)
            self.core.slice_shader.set_int("hasOverlay", 1 if self.core.has_overlay else 0)
            if self.core.has_overlay:
                self.core.volume_renderer.bind_texture(slot=1, unit=2)
                self.core.slice_shader.set_int("volumeTexture2", 2)
                self.core.volume_renderer.bind_tf_texture(slot=1, unit=3)
                self.core.slice_shader.set_int("transferFunction2", 3)
                
                self.core.slice_shader.set_float("densityMultiplier2", self.core.overlay_density)
                self.core.slice_shader.set_float("threshold2", self.core.overlay_threshold)
                self.core.slice_shader.set_float("tfSlope2", self.core.overlay_tf_slope)
                self.core.slice_shader.set_float("tfOffset2", self.core.overlay_tf_offset)
            
            # Common Alignment & Box Uniforms
            box_size = self.core.get_box_size(slot=0)
            self.core.slice_shader.set_vec3("boxSize", box_size.x, box_size.y, box_size.z)
            box_size2 = self.core.get_box_size(slot=1)
            self.core.slice_shader.set_vec3("boxSize2", box_size2.x, box_size2.y, box_size2.z)
            self.core.slice_shader.set_vec3("overlayOffset", self.core.overlay_offset.x, self.core.overlay_offset.y, self.core.overlay_offset.z)
            self.core.slice_shader.set_float("overlayScale", self.core.overlay_scale)

            # Clipping
            self.core.slice_shader.set_vec3("clipMin", self.core.clip_min.x, self.core.clip_min.y, self.core.clip_min.z)
            self.core.slice_shader.set_vec3("clipMax", self.core.clip_max.x, self.core.clip_max.y, self.core.clip_max.z)
            self.core.slice_shader.set_vec3("clipMin2", self.core.overlay_clip_min.x, self.core.overlay_clip_min.y, self.core.overlay_clip_min.z)
            self.core.slice_shader.set_vec3("clipMax2", self.core.overlay_clip_max.x, self.core.overlay_clip_max.y, self.core.overlay_clip_max.z)

            if self.mode == "Axial":
                axis = 0
                depth = self.core.slice_indices[2] / max(1, vol_d-1)
                aspect_data = box_size.x / box_size.y
            elif self.mode == "Coronal":
                axis = 1
                depth = self.core.slice_indices[1] / max(1, vol_h-1)
                aspect_data = box_size.x / box_size.z
            else: # Sagittal
                axis = 2
                depth = self.core.slice_indices[0] / max(1, vol_w-1)
                aspect_data = box_size.y / box_size.z
                
            self.core.slice_shader.set_int("axis", axis)
            self.core.slice_shader.set_float("sliceDepth", depth)
            self.core.slice_shader.set_float("densityMultiplier", self.core.slice_density)
            self.core.slice_shader.set_float("threshold", self.core.slice_threshold)
            self.core.slice_shader.set_float("tfSlope", self.core.tf_slope)
            self.core.slice_shader.set_float("tfOffset", self.core.tf_offset)

            # Aspect Ratio Conservation
            aspect_view = self.width() / max(1, self.height())
            scale_x, scale_y = 1.0, 1.0
            if aspect_data > aspect_view:
                scale_y = aspect_view / aspect_data
            else:
                scale_x = aspect_data / aspect_view

            # Apply View Zoom and Offset
            scale_x *= self.view_zoom
            scale_y *= self.view_zoom
            
            self.render_quad(scale_x, scale_y, self.view_offset.x, self.view_offset.y)
            
        elif self.mode == "3D":
            self.core.ray_shader.use()
            
            # Unit 0: Primary Volume
            self.core.volume_renderer.bind_texture(slot=0, unit=0)
            self.core.ray_shader.set_int("volumeTexture", 0)
            
            # Unit 1: Primary TF
            self.core.volume_renderer.bind_tf_texture(slot=0, unit=1)
            self.core.ray_shader.set_int("transferFunction", 1)
            
            # Overlay Volume and TF (Units 2 and 3)
            self.core.ray_shader.set_int("hasOverlay", 1 if self.core.has_overlay else 0)
            if self.core.has_overlay:
                self.core.volume_renderer.bind_texture(slot=1, unit=2)
                self.core.ray_shader.set_int("volumeTexture2", 2)
                
                self.core.volume_renderer.bind_tf_texture(slot=1, unit=3)
                self.core.ray_shader.set_int("transferFunction2", 3)
                
                self.core.ray_shader.set_float("densityMultiplier2", self.core.overlay_density)
                self.core.ray_shader.set_float("threshold2", self.core.overlay_threshold)
                self.core.ray_shader.set_float("tfSlope2", self.core.overlay_tf_slope)
                self.core.ray_shader.set_float("tfOffset2", self.core.overlay_tf_offset)

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
            
            box_size = self.core.get_box_size(slot=0)
            self.core.ray_shader.set_vec3("boxSize", box_size.x, box_size.y, box_size.z)
            
            box_size2 = self.core.get_box_size(slot=1)
            self.core.ray_shader.set_vec3("boxSize2", box_size2.x, box_size2.y, box_size2.z)
            
            self.core.ray_shader.set_vec3("overlayOffset", self.core.overlay_offset.x, self.core.overlay_offset.y, self.core.overlay_offset.z)
            self.core.ray_shader.set_float("overlayScale", self.core.overlay_scale)
            
            self.core.ray_shader.set_int("renderMode", self.core.rendering_mode)
            self.core.ray_shader.set_int("renderMode2", self.core.overlay_rendering_mode)
            self.core.ray_shader.set_float("densityMultiplier", self.core.volume_density)
            self.core.ray_shader.set_float("threshold", self.core.volume_threshold)
            self.core.ray_shader.set_float("lightIntensity", self.core.light_intensity)
            self.core.ray_shader.set_float("ambientLight", self.core.ambient_light)
            self.core.ray_shader.set_float("diffuseLight", self.core.diffuse_light)
            self.core.ray_shader.set_float("specularIntensity", self.core.specular_intensity)
            self.core.ray_shader.set_float("shininess", self.core.shininess)
            self.core.ray_shader.set_float("gradientWeight", self.core.gradient_weight)
            
            self.core.ray_shader.set_vec3("clipMin", self.core.clip_min.x, self.core.clip_min.y, self.core.clip_min.z)
            self.core.ray_shader.set_vec3("clipMax", self.core.clip_max.x, self.core.clip_max.y, self.core.clip_max.z)
            
            self.core.ray_shader.set_vec3("clipMin2", self.core.overlay_clip_min.x, self.core.overlay_clip_min.y, self.core.overlay_clip_min.z)
            self.core.ray_shader.set_vec3("clipMax2", self.core.overlay_clip_max.x, self.core.overlay_clip_max.y, self.core.overlay_clip_max.z)
            
            if self.core.lighting_mode == 0: # Fixed
                lx, ly, lz = 0.5, 1.0, 0.5
            else: # Headlamp (Flashlight)
                lx, ly, lz = -d.x, -d.y, -d.z
            self.core.ray_shader.set_vec3("lightDir", lx, ly, lz)
            
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

    def render_quad(self, scale_x=1.0, scale_y=1.0, offset_x=0.0, offset_y=0.0):
        gl.glBegin(gl.GL_QUADS)
        gl.glTexCoord2f(0.0, 0.0); gl.glVertex3f(-1.0 * scale_x + offset_x, -1.0 * scale_y + offset_y, 0.0)
        gl.glTexCoord2f(1.0, 0.0); gl.glVertex3f( 1.0 * scale_x + offset_x, -1.0 * scale_y + offset_y, 0.0)
        gl.glTexCoord2f(1.0, 1.0); gl.glVertex3f( 1.0 * scale_x + offset_x,  1.0 * scale_y + offset_y, 0.0)
        gl.glTexCoord2f(0.0, 1.0); gl.glVertex3f(-1.0 * scale_x + offset_x,  1.0 * scale_y + offset_y, 0.0)
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
        curr_x, curr_y = event.position().x(), event.position().y()
        
        # Calculate NDC diffs
        prev_ndc_x, prev_ndc_y = self.to_ndc(self.last_mouse_pos[0], self.last_mouse_pos[1])
        curr_ndc_x, curr_ndc_y = self.to_ndc(curr_x, curr_y)
        
        dx = curr_ndc_x - prev_ndc_x
        dy = curr_ndc_y - prev_ndc_y

        if self.mode == "3D":
            if self.mouse_pressed:
                self.core.camera.rotate(prev_ndc_x, prev_ndc_y, curr_ndc_x, curr_ndc_y)
                self.start_interaction()
                self.update()
            elif self.right_mouse_pressed:
                self.core.camera.pan(dx, dy)
                self.start_interaction()
                self.update()
        else:
            # Orthogonal Panning
            if self.mouse_pressed:
                self.view_offset.x += dx
                self.view_offset.y += dy
                self.update()
            
        self.last_mouse_pos = (curr_x, curr_y)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y() / 120.0

        if self.mode == "3D":
            self.core.camera.process_scroll(delta)
            self.start_interaction()
            self.update()
        else:
            modifiers = event.modifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                # Zooming
                zoom_factor = 1.1 if delta > 0 else 0.9
                self.view_zoom *= zoom_factor
                self.view_zoom = max(0.1, min(self.view_zoom, 50.0))
                self.update()
            else:
                # Slicing
                vol_dims = self.core.volume_renderer.volume_dims[0]
                if vol_dims[0] == 0: return

                if self.mode == "Axial":
                    idx = 2
                elif self.mode == "Coronal":
                    idx = 1
                else: # Sagittal
                    idx = 0
                
                step = 1 if delta > 0 else -1
                new_val = self.core.slice_indices[idx] + step
                self.core.slice_indices[idx] = max(0, min(new_val, vol_dims[idx] - 1))
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

    def reset_orthogonal_view(self):
        self.view_zoom = 1.0
        self.view_offset = glm.vec2(0.0, 0.0)
        self.update()

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        if self.mode != "3D":
            fit_window = QAction("Fit to Window", self)
            fit_window.triggered.connect(self.reset_orthogonal_view)
            menu.addAction(fit_window)
            menu.addSeparator()

            # Export All Slices action
            export_slices = QAction(f"Export All Slices ({self.mode})...", self)
            export_slices.triggered.connect(lambda: self.sig_export_slices.emit(self.mode))
            menu.addAction(export_slices)
            menu.addSeparator()

        if self.mode == "3D":
            record_movie = QAction("Record 360° Movie...", self)
            record_movie.triggered.connect(self.sig_record_movie.emit)
            menu.addAction(record_movie)
            menu.addSeparator()

        save_this = QAction(f"Save This View ({self.mode})", self)
        save_this.triggered.connect(lambda: self.sig_save_request.emit("single"))

        save_all = QAction("Save All Views (Composite)", self)
        save_all.triggered.connect(lambda: self.sig_save_request.emit("all"))

        menu.addAction(save_this)
        menu.addAction(save_all)
        menu.exec(event.globalPos())
