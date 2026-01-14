"""
ZMQ Command Processor for 3D Viewer.
Translates Acquila JSON format commands to 3dviewer actions.

Command Format (Acquila standard):
{
    "component": "3dviewer",
    "command": "COMMAND_NAME",
    "arg1": "value",
    "arg2": "value",
    "uuid": "..."
}

This module must NOT be modified - it follows the acquila_zmq library structure.
"""
import logging
from typing import TYPE_CHECKING, Dict, Any, Callable, Optional

if TYPE_CHECKING:
    from app_core import AppCore

logger = logging.getLogger(__name__)


class ZMQCommandProcessor:
    """
    Processes ZMQ commands following the Acquila protocol.
    Maps command names to handler functions.
    """
    
    def __init__(self, app_core: 'AppCore'):
        self.app_core = app_core
        self._register_commands()
    
    def _register_commands(self):
        """Register all supported commands."""
        self.commands: Dict[str, Callable] = {
            # Data loading
            "load_data": self._cmd_load_data,
            
            # Rendering
            "set_rendering_mode": self._cmd_set_rendering_mode,
            "set_transfer_function": self._cmd_set_transfer_function,
            "set_threshold": self._cmd_set_threshold,
            "set_density": self._cmd_set_density,
            
            # Camera
            "rotate": self._cmd_rotate,
            "zoom": self._cmd_zoom,
            "reset_camera": self._cmd_reset_camera,
            "set_fov": self._cmd_set_fov,
            
            # Slicing
            "set_slice": self._cmd_set_slice,
            
            # Lighting & Quality
            "set_lighting": self._cmd_set_lighting,
            "set_quality": self._cmd_set_quality,
            
            # Clipping
            "crop": self._cmd_crop,
            
            # Shading
            "set_specular": self._cmd_set_specular,
            "set_shininess": self._cmd_set_shininess,
            "set_gradient_weight": self._cmd_set_gradient_weight,
            
            # Status
            "get_status": self._cmd_get_status,
        }
    
    def process(self, command_data: dict) -> dict:
        """
        Process a ZMQ command and return result dict.
        
        Args:
            command_data: Dict with 'command', 'arg1', 'arg2', etc.
            
        Returns:
            Dict with 'success', 'message', and optionally 'data'.
        """
        cmd = command_data.get("command", "")
        
        handler = self.commands.get(cmd)
        if handler:
            try:
                return handler(command_data)
            except Exception as e:
                logger.exception(f"Error executing command '{cmd}'")
                return {"success": False, "message": f"ERROR: {str(e)}"}
        else:
            return {"success": False, "message": f"Unknown command: {cmd}"}
    
    def get_supported_commands(self) -> list:
        """Return list of supported command names."""
        return list(self.commands.keys())
    
    # =========================================================================
    # Command Handlers
    # =========================================================================
    
    def _cmd_load_data(self, data: dict) -> dict:
        """Load dataset from path. arg1=path"""
        path = data.get("arg1", "")
        if not path:
            return {"success": False, "message": "ERROR: No path provided"}
        
        success = self.app_core.load_dataset(path)
        if success:
            return {"success": True, "message": f"Loaded dataset from: {path}"}
        return {"success": False, "message": f"Failed to load dataset from: {path}"}
    
    def _cmd_set_rendering_mode(self, data: dict) -> dict:
        """Set rendering mode. arg1=mode, arg2=slot (optional, default 0)"""
        mode_name = data.get("arg1", "").lower()
        slot = int(data.get("arg2", 0) or 0)
        
        mode_map = {"mip": 0, "volume": 1, "cinematic": 2, "mida": 3, "shaded": 4, "edge": 5}
        if mode_name not in mode_map:
            return {"success": False, "message": f"Unknown mode: {mode_name}. Valid: {list(mode_map.keys())}"}
        
        self.app_core.set_rendering_mode(mode_map[mode_name], slot=slot)
        target = "Overlay" if slot == 1 else "Primary"
        return {"success": True, "message": f"{target} rendering mode set to {mode_name.upper()}"}
    
    def _cmd_set_transfer_function(self, data: dict) -> dict:
        """Set transfer function. arg1=tf_name, arg2=slot (optional, default 0)"""
        tf_name = data.get("arg1", "").lower()
        slot = int(data.get("arg2", 0) or 0)
        
        if tf_name not in self.app_core.tf_names:
            return {"success": False, "message": f"Unknown TF: {tf_name}. Valid: {self.app_core.tf_names}"}
        
        self.app_core.set_transfer_function(tf_name, slot=slot)
        target = "Overlay" if slot == 1 else "Primary"
        return {"success": True, "message": f"{target} transfer function set to {tf_name}"}
    
    def _cmd_set_threshold(self, data: dict) -> dict:
        """Set threshold. arg1=value (0.0-1.0), arg2=slot (optional)"""
        try:
            value = float(data.get("arg1", 0.05))
        except ValueError:
            return {"success": False, "message": "Invalid threshold value"}
        
        slot = int(data.get("arg2", 0) or 0)
        value = max(0.0, min(value, 1.0))
        
        if slot == 1:
            self.app_core.overlay_threshold = value
            return {"success": True, "message": f"Overlay threshold set to {value:.2f}"}
        else:
            self.app_core.volume_threshold = value
            return {"success": True, "message": f"Primary threshold set to {value:.2f}"}
    
    def _cmd_set_density(self, data: dict) -> dict:
        """Set density. arg1=value (0.1-500), arg2=slot (optional)"""
        try:
            value = float(data.get("arg1", 50.0))
        except ValueError:
            return {"success": False, "message": "Invalid density value"}
        
        slot = int(data.get("arg2", 0) or 0)
        value = max(0.1, min(value, 500.0))
        
        if slot == 1:
            self.app_core.overlay_density = value
            return {"success": True, "message": f"Overlay density set to {value:.1f}"}
        else:
            self.app_core.volume_density = value
            return {"success": True, "message": f"Primary density set to {value:.1f}"}
    
    def _cmd_rotate(self, data: dict) -> dict:
        """Rotate camera. arg1=axis (x/y), arg2=degrees"""
        axis = data.get("arg1", "y").lower()
        try:
            degrees = float(data.get("arg2", 0) or data.get("arg1", 0))
        except ValueError:
            return {"success": False, "message": "Invalid rotation value"}
        
        drag_amount = degrees / 180.0
        if axis == "y":
            self.app_core.camera.rotate(0, 0, -drag_amount, 0)
        elif axis == "x":
            self.app_core.camera.rotate(0, 0, 0, -drag_amount)
        else:
            # Default: rotate Y if only degrees given
            self.app_core.camera.rotate(0, 0, -drag_amount, 0)
        
        return {"success": True, "message": f"Rotated {axis.upper()} by {degrees} degrees"}
    
    def _cmd_zoom(self, data: dict) -> dict:
        """Zoom camera. arg1=value (+/- or absolute)"""
        try:
            value = float(data.get("arg1", 0))
        except ValueError:
            return {"success": False, "message": "Invalid zoom value"}
        
        self.app_core.camera.process_scroll(value * 5.0)
        return {"success": True, "message": f"Zoomed by {value}"}
    
    def _cmd_reset_camera(self, data: dict) -> dict:
        """Reset camera to default position."""
        import glm
        self.app_core.camera.radius = 3.0
        self.app_core.camera.target = self.app_core.get_box_size() * 0.5
        self.app_core.camera.orientation = glm.quat()
        self.app_core.camera.update_camera_vectors()
        return {"success": True, "message": "Camera reset to default"}
    
    def _cmd_set_fov(self, data: dict) -> dict:
        """Set field of view. arg1=degrees (1-160)"""
        try:
            value = float(data.get("arg1", 45.0))
        except ValueError:
            return {"success": False, "message": "Invalid FOV value"}
        
        self.app_core.camera.fov = max(1.0, min(value, 160.0))
        return {"success": True, "message": f"FOV set to {self.app_core.camera.fov:.1f} degrees"}
    
    def _cmd_set_slice(self, data: dict) -> dict:
        """Set slice position. arg1=axis (x/y/z), arg2=value or percent%"""
        axis = data.get("arg1", "z").lower()
        value_str = data.get("arg2", "50%")
        
        axis_map = {"x": 0, "y": 1, "z": 2}
        if axis not in axis_map:
            return {"success": False, "message": f"Invalid axis: {axis}. Use x, y, or z"}
        
        axis_idx = axis_map[axis]
        vol_dims = self.app_core.volume_renderer.volume_dims[0]
        
        try:
            if str(value_str).endswith("%"):
                percent = float(value_str.rstrip("%"))
                value = int((percent / 100.0) * (vol_dims[axis_idx] - 1))
            else:
                value = int(float(value_str))
        except ValueError:
            return {"success": False, "message": f"Invalid slice value: {value_str}"}
        
        value = max(0, min(value, vol_dims[axis_idx] - 1))
        self.app_core.slice_indices[axis_idx] = value
        return {"success": True, "message": f"{axis.upper()} slice set to {value}"}
    
    def _cmd_set_lighting(self, data: dict) -> dict:
        """Set lighting mode. arg1=mode (fixed/headlamp)"""
        mode_name = data.get("arg1", "").lower()
        mode_map = {"fixed": 0, "headlamp": 1}
        
        if mode_name not in mode_map:
            return {"success": False, "message": f"Unknown lighting mode: {mode_name}. Valid: {list(mode_map.keys())}"}
        
        self.app_core.lighting_mode = mode_map[mode_name]
        return {"success": True, "message": f"Lighting set to {mode_name}"}
    
    def _cmd_set_quality(self, data: dict) -> dict:
        """Set sampling quality. arg1=value (0.1-5.0)"""
        try:
            value = float(data.get("arg1", 1.0))
        except ValueError:
            return {"success": False, "message": "Invalid quality value"}
        
        self.app_core.sampling_rate = max(0.1, min(value, 5.0))
        return {"success": True, "message": f"Quality set to {self.app_core.sampling_rate}x"}
    
    def _cmd_crop(self, data: dict) -> dict:
        """Crop volume. arg1=axis (x/y/z), arg2='min,max' (0.0-1.0)"""
        axis = data.get("arg1", "x").lower()
        range_str = data.get("arg2", "0.0,1.0")
        
        try:
            parts = range_str.split(",")
            c_min = float(parts[0])
            c_max = float(parts[1]) if len(parts) > 1 else 1.0
        except (ValueError, IndexError):
            return {"success": False, "message": f"Invalid crop range: {range_str}. Use 'min,max'"}
        
        if axis == "x":
            self.app_core.clip_min.x, self.app_core.clip_max.x = c_min, c_max
        elif axis == "y":
            self.app_core.clip_min.y, self.app_core.clip_max.y = c_min, c_max
        elif axis == "z":
            self.app_core.clip_min.z, self.app_core.clip_max.z = c_min, c_max
        else:
            return {"success": False, "message": f"Invalid axis: {axis}"}
        
        return {"success": True, "message": f"Crop {axis.upper()} set to [{c_min:.2f}, {c_max:.2f}]"}
    
    def _cmd_set_specular(self, data: dict) -> dict:
        """Set specular intensity. arg1=value (0.0-2.0)"""
        try:
            value = float(data.get("arg1", 0.5))
        except ValueError:
            return {"success": False, "message": "Invalid specular value"}
        
        self.app_core.specular_intensity = max(0.0, min(value, 2.0))
        return {"success": True, "message": f"Specular set to {self.app_core.specular_intensity:.2f}"}
    
    def _cmd_set_shininess(self, data: dict) -> dict:
        """Set shininess. arg1=value (1.0-128.0)"""
        try:
            value = float(data.get("arg1", 32.0))
        except ValueError:
            return {"success": False, "message": "Invalid shininess value"}
        
        self.app_core.shininess = max(1.0, min(value, 128.0))
        return {"success": True, "message": f"Shininess set to {self.app_core.shininess:.1f}"}
    
    def _cmd_set_gradient_weight(self, data: dict) -> dict:
        """Set gradient weight. arg1=value (0.0-50.0)"""
        try:
            value = float(data.get("arg1", 10.0))
        except ValueError:
            return {"success": False, "message": "Invalid gradient weight value"}
        
        self.app_core.gradient_weight = max(0.0, min(value, 50.0))
        return {"success": True, "message": f"Gradient weight set to {self.app_core.gradient_weight:.1f}"}
    
    def _cmd_get_status(self, data: dict) -> dict:
        """Return current viewer status."""
        status = {
            "rendering_mode": self.app_core.render_modes[self.app_core.rendering_mode],
            "transfer_function": self.app_core.current_tf_name,
            "threshold": self.app_core.volume_threshold,
            "density": self.app_core.volume_density,
            "slice_indices": self.app_core.slice_indices,
            "lighting_mode": self.app_core.lighting_modes[self.app_core.lighting_mode],
            "quality": self.app_core.sampling_rate,
            "fov": self.app_core.camera.fov,
            "has_data": self.app_core.current_dataset_path is not None,
            "dataset_path": self.app_core.current_dataset_path,
        }
        return {"success": True, "message": "Status retrieved", "data": status}
