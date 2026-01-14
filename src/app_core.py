import os
import sys
import numpy as np
import glm
from volume_loader import VolumeLoader
from renderer import VolumeRenderer, ShaderProgram
from camera import Camera
import transfer_functions
from command_interpreter import CommandInterpreter

class AppCore:
    def __init__(self):
        self.volume_loader = VolumeLoader()
        self.volume_renderer = VolumeRenderer()
        self.camera = Camera(target=(0.5, 0.5, 0.5))
        self.command_interpreter = CommandInterpreter()
        self.current_dataset_path = None
        
        self.slice_indices = [0, 0, 0] # X, Y, Z
        self.slice_density = 0.25
        self.slice_threshold = 0.06
        
        # Primary Volume
        self.volume_density = 50.0
        self.volume_threshold = 0.05
        self.tf_slope = 1.0
        self.tf_offset = 0.0
        self.current_tf_name = "grayscale"
        self.alpha_points = [(0.0, 0.0), (1.0, 1.0)] # Default linear ramp
        
        # Secondary (Overlay) Volume
        self.has_overlay = False
        self.overlay_density = 50.0
        self.overlay_threshold = 0.05
        self.overlay_tf_slope = 1.0
        self.overlay_tf_offset = 0.0
        self.overlay_tf_name = "plasma" # Default overlay TF
        self.overlay_alpha_points = [(0.0, 0.0), (1.0, 1.0)]
        self.overlay_offset = glm.vec3(0.0, 0.0, 0.0)
        self.overlay_scale = 1.0

        self.light_intensity = 1.0
        self.ambient_light = 0.15
        self.diffuse_light = 0.8
        self.specular_intensity = 0.5
        self.shininess = 32.0
        self.gradient_weight = 10.0
        self.sampling_rate = 1.0 # Multiplier for quality
        self.lighting_mode = 0 # 0: Fixed, 1: Headlamp
        self.lighting_modes = ["Fixed", "Headlamp"]

        # Virtual Phase Contrast (Post-Processing)
        self.vpc_enabled = False
        self.vpc_distance = 50.0 # Virtual propagation distance
        self.vpc_wavelength = 1.0 # Virtual wavelength factor

        
        self.tf_names = ["grayscale", "viridis", "plasma", "medical", "rainbow", 
                         "ct_bone", "ct_soft_tissue", "ct_muscle", "ct_lung", 
                         "cool_warm", "ct_sandstone", "ct_body"]
        self.rendering_mode = 1 # 0: MIP, 1: Standard, 2: Cinematic, 3: MIDA, 4: Shaded, 5: Edge
        self.overlay_rendering_mode = 1
        self.render_modes = ["MIP", "Volume Rendering", "Cinematic Rendering", "MIDA Rendering", "Shaded Volume", "Edge Enhanced"]
        
        self.clip_min = glm.vec3(0.0, 0.0, 0.0)
        self.clip_max = glm.vec3(1.0, 1.0, 1.0)
        self.overlay_clip_min = glm.vec3(0.0, 0.0, 0.0)
        self.overlay_clip_max = glm.vec3(1.0, 1.0, 1.0)

        self.slice_shader = None
        self.ray_shader = None
        self.vpc_shader = None

    def set_rendering_mode(self, index, slot=0):
        if 0 <= index < len(self.render_modes):
            if slot == 0:
                self.rendering_mode = index
            else:
                self.overlay_rendering_mode = index

    def load_shaders(self):
        try:
            path = os.path.dirname(__file__)
            slice_vert = open(os.path.join(path, 'shaders/slice.vert')).read()
            slice_frag = open(os.path.join(path, 'shaders/slice.frag')).read()
            ray_vert = open(os.path.join(path, 'shaders/raymarch.vert')).read()
            ray_frag = open(os.path.join(path, 'shaders/raymarch.frag')).read()
            
            self.slice_shader = ShaderProgram(slice_vert, slice_frag)
            self.ray_shader = ShaderProgram(ray_vert, ray_frag)
            
            # Load VPC Filter Shader (uses same vertex shader as slice/quad)
            vpc_frag = open(os.path.join(path, 'shaders/vpc_filter.frag')).read()
            self.vpc_shader = ShaderProgram(slice_vert, vpc_frag)
            
            return True
        except Exception as e:
            print(f"Failed to load shaders: {e}")
            return False

    def load_dataset(self, folder_path, is_overlay=False, rescale_range=None, z_range=None, binning_factor=1, use_8bit=False):
        if os.path.exists(folder_path):
            data = self.volume_loader.load_from_folder(
                folder_path, 
                rescale_range=rescale_range,
                z_range=z_range,
                binning_factor=binning_factor,
                use_8bit=use_8bit
            )
            if data is not None:
                d, h, w = data.shape
                slot = 1 if is_overlay else 0
                self.volume_renderer.create_texture(data, w, h, d, slot=slot)
                
                if not is_overlay:
                    self.current_dataset_path = folder_path
                    self.slice_indices = [w//2, h//2, d//2]
                    # Update camera target to center of volume
                    box_size = self.get_box_size(slot=0)
                    center = box_size * 0.5
                    self.camera.target = center
                    self.camera.radius = glm.length(box_size) * 1.5
                    self.camera.update_camera_vectors()
                    self.update_tf_texture(slot=0)
                else:
                    self.has_overlay = True
                    self.update_tf_texture(slot=1)
                    w2, h2, d2 = self.volume_renderer.volume_dims[1]
                    w1, h1, d1 = self.volume_renderer.volume_dims[0]
                    print(f"Overlay loaded: {w2}x{h2}x{d2} vs Primary: {w1}x{h1}x{d1}")
                
                return True
        else:
            print(f"AppCore Error: Path not found: '{folder_path}'")
        return False

    def get_box_size(self, slot=0):
        w, h, d = self.volume_renderer.volume_dims[slot]
        if w == 0: return glm.vec3(1.0)
        max_dim = max(w, h, d)
        return glm.vec3(w/max_dim, h/max_dim, d/max_dim)

    def set_transfer_function(self, name, slot=0):
        if name in self.tf_names:
            if slot == 0:
                self.current_tf_name = name
            else:
                self.overlay_tf_name = name
            self.update_tf_texture(slot=slot)

    def update_alpha_points(self, points, slot=0):
        """points: list of (pos, alpha) tuples"""
        sorted_points = sorted(points, key=lambda x: x[0])
        if slot == 0:
            self.alpha_points = sorted_points
        else:
            self.overlay_alpha_points = sorted_points
        self.update_tf_texture(slot=slot)

    def update_tf_texture(self, slot=0):
        if slot == 0:
            name = self.current_tf_name
            points = self.alpha_points
        else:
            name = self.overlay_tf_name
            points = self.overlay_alpha_points
            
        tf_data = transfer_functions.get_combined_tf(name, points)
        self.volume_renderer.create_tf_texture(tf_data, slot=slot)


    def execute_command_text(self, text):
        """
        Parses and executes a text command.
        Returns (success: bool, response_message: str)
        """
        action_dict, response_msg = self.command_interpreter.interpret(text)
        
        if not action_dict:
            return False, response_msg or "I'm not sure how to do that yet."
        
        action = action_dict.get('action')
        params = action_dict.get('params', {})
        
        # Smarter overlay detection: check if keywords are standalone words, usually at the start
        import re
        is_overlay_cmd = bool(re.search(r'\b(overlay|secondary)\b', text.lower()))
        
        if action == 'zoom':
            val = float(params.get('value', 0))
            self.camera.process_scroll(val * 5.0)
            return True, response_msg
            
        elif action == 'rotate':
            axis = params.get('axis')
            val = float(params.get('value', 0))
            drag_amount = (val / 180.0)
            if axis == 'y':
                self.camera.rotate(0, 0, -drag_amount, 0)
            elif axis == 'x':
                self.camera.rotate(0, 0, 0, -drag_amount)
            return True, response_msg
                
        elif action == 'reset':
            self.camera.radius = 3.0
            self.camera.target = self.get_box_size() * 0.5
            self.camera.orientation = glm.quat()
            self.camera.update_camera_vectors()
            return True, response_msg
        
        elif action == 'set_mode':
            mode_map = {'mip': 0, 'volume': 1, 'cinematic': 2, 'mida': 3, 'shaded': 4, 'edge': 5}
            mode_name = params.get('mode', '').lower()
            if mode_name in mode_map:
                slot = 1 if is_overlay_cmd else 0
                self.set_rendering_mode(mode_map[mode_name], slot=slot)
                target = "Overlay" if slot == 1 else "Primary"
                return True, response_msg or f"{target} switched to {mode_name.upper()} mode."
            return False, f"Unknown rendering mode: {mode_name}"
        
        elif action == 'set_tf':
            tf_name = params.get('tf', '').lower()
            if tf_name in self.tf_names:
                slot = 1 if is_overlay_cmd else 0
                self.set_transfer_function(tf_name, slot=slot)
                target = "Overlay" if slot == 1 else "Primary"
                return True, response_msg or f"{target} transfer function set to {tf_name}."
            return False, f"Unknown transfer function: {tf_name}"
        
        elif action == 'set_slice':
            axis = params.get('axis', '').lower()
            axis_map = {'x': 0, 'y': 1, 'z': 2}
            if axis not in axis_map:
                return False, "Invalid slice axis. Use x, y, or z."
            
            axis_idx = axis_map[axis]
            vol_dims = self.volume_renderer.volume_dims[0]
            
            if 'percent' in params:
                percent = float(params['percent'])
                value = int((percent / 100.0) * (vol_dims[axis_idx] - 1))
            else:
                value = int(params.get('value', 0))
            
            value = max(0, min(value, vol_dims[axis_idx] - 1))
            self.slice_indices[axis_idx] = value
            return True, response_msg or f"{axis.upper()} slice set to {value}."
        
        elif action == 'set_lighting':
            mode_name = params.get('mode', '').lower()
            mode_map = {'fixed': 0, 'headlamp': 1}
            if mode_name in mode_map:
                self.lighting_mode = mode_map[mode_name]
                return True, response_msg or f"Lighting set to {mode_name}."
            return False, f"Unknown lighting mode: {mode_name}"
        
        elif action == 'adjust_quality':
            value = float(params.get('value', 1.0))
            self.sampling_rate = max(0.1, min(value, 5.0))
            return True, response_msg or f"Quality set to {value}x."
            
        elif action == 'set_threshold':
            value = float(params.get('value', 0.05))
            # Auto-scale: If user says "set threshold 10", they likely mean 0.1
            if value > 1.0:
                value /= 100.0
            
            if is_overlay_cmd:
                self.overlay_threshold = value
                return True, f"Overlay threshold set to {value:.2f} (Range: 0.0 to 1.0)"
            else:
                self.volume_threshold = value
                return True, f"Primary threshold set to {value:.2f} (Range: 0.0 to 1.0)"

        elif action == 'set_density':
            value = float(params.get('value', 50.0))
            # No auto-scale for density as it can be large, but clamped
            value = max(0.1, min(value, 500.0))
            
            if is_overlay_cmd:
                self.overlay_density = value
                return True, f"Overlay density set to {value:.1f} (Recommended range: 10 to 100)"
            else:
                self.volume_density = value
                return True, f"Primary density set to {value:.1f} (Recommended range: 10 to 100)"

        elif action == 'set_specular':
            value = float(params.get('value', 0.5))
            self.specular_intensity = max(0.0, min(value, 2.0))
            return True, response_msg or f"Specular intensity set to {self.specular_intensity:.2f}"

        elif action == 'set_shininess':
            value = float(params.get('value', 32.0))
            self.shininess = max(1.0, min(value, 128.0))
            return True, response_msg or f"Shininess set to {self.shininess:.1f}"

        elif action == 'set_gradient_weight':
            value = float(params.get('value', 0.0))
            self.gradient_weight = max(0.0, min(value, 50.0))
            return True, response_msg or f"Gradient weight (Edge Enhancement) set to {self.gradient_weight:.1f}"

        elif action == 'set_fov':
            value = float(params.get('value', 45.0))
            self.camera.fov = max(1.0, min(value, 160.0))
            return True, response_msg or f"Field of View set to {self.camera.fov:.1f} degrees"
            
        elif action == 'load':
            path = params.get('path')
            if not path:
                return False, "Please specify a folder path to load."
            
            success = self.load_dataset(path, is_overlay=is_overlay_cmd)
            if success:
                target = "Overlay" if is_overlay_cmd else "Primary"
                return True, f"Successfully loaded {target} from {path}"
            return False, f"Failed to load dataset from {path}"

        elif action == 'crop':
            axis = params.get('axis', 'x').lower()
            c_min = float(params.get('min', 0.0))
            c_max = float(params.get('max', 1.0))
            
            target = "Overlay" if is_overlay_cmd else "Primary"
            if is_overlay_cmd:
                if axis == 'x': self.overlay_clip_min.x, self.overlay_clip_max.x = c_min, c_max
                elif axis == 'y': self.overlay_clip_min.y, self.overlay_clip_max.y = c_min, c_max
                elif axis == 'z': self.overlay_clip_min.z, self.overlay_clip_max.z = c_min, c_max
            else:
                if axis == 'x': self.clip_min.x, self.clip_max.x = c_min, c_max
                elif axis == 'y': self.clip_min.y, self.clip_max.y = c_min, c_max
                elif axis == 'z': self.clip_min.z, self.clip_max.z = c_min, c_max
            
            return True, f"{target} crop {axis.upper()} set to [{c_min:.2f}, {c_max:.2f}]"

        elif action == 'set_offset' and is_overlay_cmd:
            nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
            if nums:
                val = float(nums[0])
                text_lower = text.lower()
                if re.search(r'\bx\b', text_lower): self.overlay_offset.x = val
                elif re.search(r'\by\b', text_lower): self.overlay_offset.y = val
                elif re.search(r'\bz\b', text_lower): self.overlay_offset.z = val
                return True, f"Overlay offset set to {self.overlay_offset}"
                
        elif action == 'set_scale' and is_overlay_cmd:
            nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
            if nums:
                self.overlay_scale = float(nums[0])
                return True, f"Overlay scale set to {self.overlay_scale}"
                
        elif action == 'fit_overlay' and is_overlay_cmd:
            # Scale overlay to match physical size of primary along Z
            size1 = self.get_box_size(0)
            size2 = self.get_box_size(1)
            if size2.z > 0:
                self.overlay_scale = size1.z / size2.z
                self.overlay_offset = glm.vec3(0.0)
                return True, f"Overlay scaled by {self.overlay_scale:.2f} to fit Primary Z."
            return False, "Could not determine overlay size for fitting."

        elif action == 'center_overlay' and is_overlay_cmd:
             # Just a simple center for now
             self.overlay_offset = glm.vec3(0.0, 0.0, 0.4)
             return True, "Overlay offset moved to center (approx)."

        return False, f"Action '{action}' implemented but not handled in core."

from camera import Camera # Import at bottom to avoid potential circular if any
