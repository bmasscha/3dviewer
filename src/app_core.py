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
        
        self.slice_indices = [0, 0, 0] # X, Y, Z
        self.slice_density = 5.0
        self.slice_threshold = 0.06
        self.volume_density = 50.0
        self.volume_threshold = 0.05
        self.light_intensity = 1.0
        self.ambient_light = 0.15
        self.diffuse_light = 0.8
        self.sampling_rate = 1.0 # Multiplier for quality
        self.lighting_mode = 0 # 0: Fixed, 1: Headlamp
        self.lighting_modes = ["Fixed", "Headlamp"]
        self.tf_slope = 1.0
        self.tf_offset = 0.0
        self.current_tf_name = "grayscale"
        self.tf_names = ["grayscale", "viridis", "plasma", "medical", "rainbow"]
        self.alpha_points = [(0.0, 0.0), (1.0, 1.0)] # Default linear ramp
        self.rendering_mode = 1 # 0: MIP, 1: Standard, 2: Cinematic
        self.render_modes = ["MIP", "Volume Rendering", "Cinematic Rendering", "MIDA Rendering"]
        
        self.clip_min = glm.vec3(0.0, 0.0, 0.0)
        self.clip_max = glm.vec3(1.0, 1.0, 1.0)


        self.slice_shader = None

        self.ray_shader = None

    def set_rendering_mode(self, index):
        if 0 <= index < len(self.render_modes):
            self.rendering_mode = index

    def load_shaders(self):
        try:
            path = os.path.dirname(__file__)
            slice_vert = open(os.path.join(path, 'shaders/slice.vert')).read()
            slice_frag = open(os.path.join(path, 'shaders/slice.frag')).read()
            ray_vert = open(os.path.join(path, 'shaders/raymarch.vert')).read()
            ray_frag = open(os.path.join(path, 'shaders/raymarch.frag')).read()
            
            self.slice_shader = ShaderProgram(slice_vert, slice_frag)
            self.ray_shader = ShaderProgram(ray_vert, ray_frag)
            return True
        except Exception as e:
            print(f"Failed to load shaders: {e}")
            return False

    def load_dataset(self, folder_path):
        if os.path.exists(folder_path):
            data = self.volume_loader.load_from_folder(folder_path)
            if data is not None:
                d, h, w = data.shape
                self.volume_renderer.create_texture(data, w, h, d)
                self.slice_indices = [w//2, h//2, d//2]
                
                # Update camera target to center of volume
                # The volume is rendered in a box from (0,0,0) to box_size
                box_size = self.get_box_size()
                center = box_size * 0.5
                self.camera.target = center
                # Reset radius to a sensible distance based on volume size
                self.camera.radius = glm.length(box_size) * 1.5
                self.camera.update_camera_vectors()
                
                return True
        return False

    def get_box_size(self):
        w, h, d = self.volume_renderer.volume_dim
        if w == 0: return glm.vec3(1.0)
        max_dim = max(w, h, d)
        return glm.vec3(w/max_dim, h/max_dim, d/max_dim)

    def set_transfer_function(self, name):
        if name in self.tf_names:
            self.current_tf_name = name
            self.update_tf_texture()

    def update_alpha_points(self, points):
        """points: list of (pos, alpha) tuples"""
        self.alpha_points = sorted(points, key=lambda x: x[0])
        # Ensure we have start/end if missing? (Editor should handle this)
        self.update_tf_texture()

    def update_tf_texture(self):
        tf_data = transfer_functions.get_combined_tf(self.current_tf_name, self.alpha_points)
        self.volume_renderer.create_tf_texture(tf_data)


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
        
        if action == 'zoom':
            val = float(params.get('value', 0))
            self.camera.process_scroll(val * 5.0)
            return True, response_msg
            
        elif action == 'rotate':
            axis = params.get('axis')
            val = float(params.get('value', 0))
            
            # Scale degrees to NDC drag amount
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
            mode_map = {'mip': 0, 'volume': 1, 'cinematic': 2, 'mida': 3}
            mode_name = params.get('mode', '').lower()
            if mode_name in mode_map:
                self.set_rendering_mode(mode_map[mode_name])
                return True, response_msg or f"Switched to {mode_name.upper()} mode."
            return False, f"Unknown rendering mode: {mode_name}"
        
        elif action == 'set_tf':
            tf_name = params.get('tf', '').lower()
            if tf_name in self.tf_names:
                self.current_tf_name = tf_name
                return True, response_msg or f"Transfer function set to {tf_name}."
            return False, f"Unknown transfer function: {tf_name}"
        
        elif action == 'set_slice':
            axis = params.get('axis', '').lower()
            axis_map = {'x': 0, 'y': 1, 'z': 2}
            if axis not in axis_map:
                return False, "Invalid slice axis. Use x, y, or z."
            
            axis_idx = axis_map[axis]
            vol_dims = self.volume_renderer.volume_dim
            
            if 'percent' in params:
                percent = float(params['percent'])
                value = int((percent / 100.0) * (vol_dims[axis_idx] - 1))
            else:
                value = int(params.get('value', 0))
            
            # Clamp to valid range
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
            self.sampling_rate = max(0.1, min(value, 5.0))  # Clamp to reasonable range
            return True, response_msg or f"Quality set to {value}x."
            
        return False, f"Action '{action}' implemented but not handled in core."

from camera import Camera # Import at bottom to avoid potential circular if any
