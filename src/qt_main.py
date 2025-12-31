import sys
import os
import traceback
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QLabel, QSlider, 
                             QPushButton, QComboBox, QFileDialog, QFrame,
                             QScrollArea, QLineEdit, QTextEdit)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from app_core import AppCore
from widgets.gl_view import GLViewWidget
from widgets.tf_editor import TFEditorWidget

class AIWorker(QThread):
    finished = pyqtSignal(object, str) # returns (action_dict, response_msg)
    
    def __init__(self, interpreter, text):
        super().__init__()
        self.interpreter = interpreter
        self.text = text
        
    def run(self):
        try:
            action_dict, response_msg = self.interpreter.interpret(self.text)
            self.finished.emit(action_dict, response_msg)
        except Exception as e:
            self.finished.emit(None, f"Internal Error: {str(e)}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Volume Viewer - PyQt Professional")
        self.resize(1600, 900)
        
        self.core = AppCore()
        # Delay shader loading until GL context is ready
        self.setup_ui()
        self.apply_stylesheet()
        
        # MainWindow fully initialized.

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Left Sidebar ---
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        left_widget = QWidget()
        left_sidebar = QVBoxLayout(left_widget)
        left_sidebar.setSpacing(15)
        left_sidebar.setContentsMargins(0, 0, 10, 0)
        
        # Dataset Selection
        self.create_dataset_panel(left_sidebar)
        
        # Rendering Methods
        self.create_rendering_panel(left_sidebar)
        
        # Slice Controls
        self.create_slice_panel(left_sidebar)

        # Clipping Controls
        self.create_clipping_panel(left_sidebar)

        # Command Control
        self.create_command_panel(left_sidebar)
        
        left_sidebar.addStretch()
        left_scroll.setWidget(left_widget)
        main_layout.addWidget(left_scroll, 1)

        # --- Center Grid (Viewports) ---
        grid_layout = QGridLayout()
        grid_layout.setSpacing(5)
        
        self.view_axial = GLViewWidget(self.core, "Axial")
        self.view_coronal = GLViewWidget(self.core, "Coronal")
        self.view_sagittal = GLViewWidget(self.core, "Sagittal")
        self.view_3d = GLViewWidget(self.core, "3D")
        
        grid_layout.addWidget(self.view_axial, 0, 0)
        grid_layout.addWidget(self.view_sagittal, 0, 1) # Match drawing: Axial, Sagittal
        grid_layout.addWidget(self.view_coronal, 1, 0)
        grid_layout.addWidget(self.view_3d, 1, 1)
        
        # Set titles for views
        self.add_viewport_overlay(grid_layout, "Axial", 0, 0)
        self.add_viewport_overlay(grid_layout, "Sagittal", 0, 1)
        self.add_viewport_overlay(grid_layout, "Coronal", 1, 0)
        self.add_viewport_overlay(grid_layout, "Rendering (3D)", 1, 1)

        main_layout.addLayout(grid_layout, 4)

        # --- Right Sidebar ---
        right_sidebar = QVBoxLayout()
        self.create_tf_panel(right_sidebar)
        right_sidebar.addStretch()
        main_layout.addLayout(right_sidebar, 1)

    def add_viewport_overlay(self, layout, text, r, c):
        # This is a bit tricky with QGridLayout, let's just use labels inside the widgets area for now
        # Or better, wrap each GL view in a frame
        pass

    def create_rendering_panel(self, layout):
        container = QFrame()
        container.setObjectName("SidePanel")
        vbox = QVBoxLayout(container)
        
        title = QLabel("RENDERING METHODS")
        title.setObjectName("PanelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(title)
        
        self.combo_render_mode = QComboBox()
        self.combo_render_mode.addItems(self.core.render_modes)
        self.combo_render_mode.setCurrentIndex(self.core.rendering_mode)
        self.combo_render_mode.currentIndexChanged.connect(self.on_render_mode_changed)
        vbox.addWidget(self.combo_render_mode)
        
        # 3D Density
        vbox.addWidget(QLabel("3D Density Multiplier"))
        self.slider_vol_density = QSlider(Qt.Orientation.Horizontal)
        self.slider_vol_density.setRange(1, 2000)
        self.slider_vol_density.setValue(int(self.core.volume_density * 10))
        self.slider_vol_density.valueChanged.connect(self.on_vol_density_changed)
        vbox.addWidget(self.slider_vol_density)
        
        # Light Intensity
        vbox.addWidget(QLabel("Light Intensity"))
        self.slider_light = QSlider(Qt.Orientation.Horizontal)
        self.slider_light.setRange(1, 1000) # Increased range for flexibility
        self.slider_light.setValue(int(self.core.light_intensity * 100))
        self.slider_light.valueChanged.connect(self.on_light_intensity_changed)
        vbox.addWidget(self.slider_light)
        
        # Ambient Light
        vbox.addWidget(QLabel("Ambient Light"))
        self.slider_ambient = QSlider(Qt.Orientation.Horizontal)
        self.slider_ambient.setRange(0, 100) # 0.0 to 1.0
        self.slider_ambient.setValue(int(self.core.ambient_light * 100))
        self.slider_ambient.valueChanged.connect(self.on_ambient_changed)
        vbox.addWidget(self.slider_ambient)
        
        # Diffuse Light
        vbox.addWidget(QLabel("Diffuse Light"))
        self.slider_diffuse = QSlider(Qt.Orientation.Horizontal)
        self.slider_diffuse.setRange(0, 200) # 0.0 to 2.0
        self.slider_diffuse.setValue(int(self.core.diffuse_light * 100))
        self.slider_diffuse.valueChanged.connect(self.on_diffuse_changed)
        vbox.addWidget(self.slider_diffuse)
        
        # Sampling Quality
        vbox.addWidget(QLabel("Sampling Quality"))
        self.slider_quality = QSlider(Qt.Orientation.Horizontal)
        self.slider_quality.setRange(5, 40) # 0.5 to 4.0
        self.slider_quality.setValue(int(self.core.sampling_rate * 10))
        self.slider_quality.valueChanged.connect(self.on_quality_changed)
        vbox.addWidget(self.slider_quality)
        
        # Lighting Mode
        vbox.addWidget(QLabel("Lighting Mode"))
        self.combo_light_mode = QComboBox()
        self.combo_light_mode.addItems(self.core.lighting_modes)
        self.combo_light_mode.setCurrentIndex(self.core.lighting_mode)
        self.combo_light_mode.currentIndexChanged.connect(self.on_lighting_mode_changed)
        vbox.addWidget(self.combo_light_mode)
        
        # TF Slope
        vbox.addWidget(QLabel("TF Slope"))
        self.slider_tf_slope = QSlider(Qt.Orientation.Horizontal)
        self.slider_tf_slope.setRange(1, 100) # 0.1 to 10.0
        self.slider_tf_slope.setValue(int(self.core.tf_slope * 10))
        self.slider_tf_slope.valueChanged.connect(self.on_tf_slope_changed)
        vbox.addWidget(self.slider_tf_slope)
        
        # TF Offset
        vbox.addWidget(QLabel("TF Offset"))
        self.slider_tf_offset = QSlider(Qt.Orientation.Horizontal)
        self.slider_tf_offset.setRange(-200, 200) # -2.0 to 2.0
        self.slider_tf_offset.setValue(int(self.core.tf_offset * 100))
        self.slider_tf_offset.valueChanged.connect(self.on_tf_offset_changed)
        vbox.addWidget(self.slider_tf_offset)
        
        layout.addWidget(container)

    def on_render_mode_changed(self, index):
        self.core.set_rendering_mode(index)
        self.update_views()

    def on_vol_density_changed(self, val):
        self.core.volume_density = val / 10.0
        self.update_views()

    def on_light_intensity_changed(self, val):
        self.core.light_intensity = val / 100.0
        self.update_views()

    def on_ambient_changed(self, val):
        self.core.ambient_light = val / 100.0
        self.update_views()

    def on_diffuse_changed(self, val):
        self.core.diffuse_light = val / 100.0
        self.update_views()

    def on_quality_changed(self, val):
        self.core.sampling_rate = val / 10.0
        self.update_views()

    def on_lighting_mode_changed(self, index):
        self.core.lighting_mode = index
        self.update_views()

    def on_tf_slope_changed(self, val):
        self.core.tf_slope = val / 10.0
        self.update_views()

    def on_tf_offset_changed(self, val):
        self.core.tf_offset = val / 100.0
        self.update_views()

    def create_dataset_panel(self, layout):
        container = QFrame()
        container.setObjectName("SidePanel")
        vbox = QVBoxLayout(container)
        
        title = QLabel("DATASET SELECTION")
        title.setObjectName("PanelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(title)
        
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setWordWrap(True)
        vbox.addWidget(self.folder_label)
        
        btn_browse = QPushButton("Browse Folder")
        btn_browse.clicked.connect(self.on_browse)
        vbox.addWidget(btn_browse)
        
        btn_load = QPushButton("Load Dataset")
        btn_load.clicked.connect(self.on_load)
        btn_load.setObjectName("PrimaryButton")
        vbox.addWidget(btn_load)
        
        layout.addWidget(container)

    def create_slice_panel(self, layout):
        container = QFrame()
        container.setObjectName("SidePanel")
        vbox = QVBoxLayout(container)
        
        title = QLabel("SLICE & DENSITY")
        title.setObjectName("PanelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(title)
        
        # Density
        vbox.addWidget(QLabel("Slice Density"))
        self.slider_density = QSlider(Qt.Orientation.Horizontal)
        self.slider_density.setRange(1, 1000)
        self.slider_density.setValue(int(self.core.slice_density * 10))
        self.slider_density.valueChanged.connect(self.on_density_changed)
        vbox.addWidget(self.slider_density)
        
        # Threshold
        vbox.addWidget(QLabel("Slice Threshold"))
        self.slider_threshold = QSlider(Qt.Orientation.Horizontal)
        self.slider_threshold.setRange(0, 100)
        self.slider_threshold.setValue(int(self.core.slice_threshold * 100))
        self.slider_threshold.valueChanged.connect(self.on_threshold_changed)
        vbox.addWidget(self.slider_threshold)
        
        # Slices
        self.slider_x = self.create_named_slider(vbox, "Slice X", 0, self.on_slice_x_changed)
        self.slider_y = self.create_named_slider(vbox, "Slice Y", 1, self.on_slice_y_changed)
        self.slider_z = self.create_named_slider(vbox, "Slice Z", 2, self.on_slice_z_changed)
        
        layout.addWidget(container)

    def create_clipping_panel(self, layout):
        container = QFrame()
        container.setObjectName("SidePanel")
        vbox = QVBoxLayout(container)
        
        title = QLabel("VOLUME CROPPING")
        title.setObjectName("PanelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(title)
        
        self.slider_clip_min_x = self.create_percent_slider(vbox, "Min X", 0, self.on_clip_changed)
        self.slider_clip_max_x = self.create_percent_slider(vbox, "Max X", 100, self.on_clip_changed)
        self.slider_clip_min_y = self.create_percent_slider(vbox, "Min Y", 0, self.on_clip_changed)
        self.slider_clip_max_y = self.create_percent_slider(vbox, "Max Y", 100, self.on_clip_changed)
        self.slider_clip_min_z = self.create_percent_slider(vbox, "Min Z", 0, self.on_clip_changed)
        self.slider_clip_max_z = self.create_percent_slider(vbox, "Max Z", 100, self.on_clip_changed)
        
        btn_reset_clip = QPushButton("Reset Clipping")
        btn_reset_clip.clicked.connect(self.on_reset_clipping)
        vbox.addWidget(btn_reset_clip)
        
        layout.addWidget(container)

    def create_percent_slider(self, layout, name, default_val, callback):
        layout.addWidget(QLabel(name))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(default_val)
        slider.valueChanged.connect(callback)
        layout.addWidget(slider)
        return slider

    def create_command_panel(self, layout):
        container = QFrame()
        container.setObjectName("SidePanel")
        vbox = QVBoxLayout(container)
        
        title = QLabel("AI COMMAND")
        title.setObjectName("PanelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(title)
        
        # Chat log display
        self.cmd_log = QTextEdit()
        self.cmd_log.setReadOnly(True)
        self.cmd_log.setFixedHeight(150)
        self.cmd_log.setStyleSheet("background-color: #222; color: #CCC; font-size: 11px; border: 1px solid #444;")
        vbox.addWidget(self.cmd_log)
        
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Type 'zoom in', 'rotate 90'...")
        self.cmd_input.returnPressed.connect(self.on_command_submit)
        self.cmd_input.setStyleSheet("padding: 5px; color: white; background-color: #333; border: 1px solid #555;")
        vbox.addWidget(self.cmd_input)
        
        row = QHBoxLayout()
        self.btn_send = QPushButton("Send")
        self.btn_send.clicked.connect(self.on_command_submit)
        row.addWidget(self.btn_send)
        vbox.addLayout(row)
        
        layout.addWidget(container)

    def on_command_submit(self):
        text = self.cmd_input.text()
        if not text:
            return
            
        self.cmd_log.append(f"<b style='color:#3498DB'>You:</b> {text}")
        
        # Disable input while processing
        self.cmd_input.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.cmd_log.append("<i style='color:#888'>AI is thinking...</i>")
        
        # Start worker thread
        self.worker = AIWorker(self.core.command_interpreter, text)
        self.worker.finished.connect(self.on_ai_finished)
        self.worker.start()

    def on_ai_finished(self, action_dict, response_msg):
        # Remove "thinking" message (last line)
        cursor = self.cmd_log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.select(cursor.SelectionType.LineUnderCursor)
        cursor.removeSelectedText()
        cursor.deletePreviousChar() # remove the newline
        
        # Re-enable input
        self.cmd_input.setEnabled(True)
        self.btn_send.setEnabled(True)
        self.cmd_input.setFocus()
        
        # Execute action (if any) and show response
        success = False
        if action_dict:
            # We bypass execute_command_text because we already have the action_dict
            success = self.apply_ai_action(action_dict)
        
        color = "#2ECC71" if (success or not action_dict and response_msg) else "#E74C3C"
        final_msg = response_msg or "Execution failed."
        self.cmd_log.append(f"<b style='color:{color}'>AI:</b> {final_msg}")
        
        # Auto-scroll
        self.cmd_log.verticalScrollBar().setValue(self.cmd_log.verticalScrollBar().maximum())
        
        if success or (not action_dict and response_msg):
            self.cmd_input.clear()
            self.update_views()

    def apply_ai_action(self, action_dict):
        """Executes the action on the main thread and syncs UI."""
        if not isinstance(action_dict, dict):
            return False
        try:
            import glm
            action = action_dict.get('action')
            params = action_dict.get('params', {})
            
            if action == 'zoom':
                val = float(params.get('value', 0))
                self.core.camera.process_scroll(val * 5.0)
                return True
            elif action == 'rotate':
                axis = params.get('axis')
                val = float(params.get('value', 0))
                # Scale degrees to NDC drag amount (90 deg ≈ 0.5 NDC units)
                if axis == 'y':
                    drag_amount = (val / 180.0)
                    self.core.camera.rotate(0, 0, -drag_amount, 0)
                elif axis == 'x':
                    drag_amount = (val / 180.0)
                    self.core.camera.rotate(0, 0, 0, -drag_amount)
                return True
            elif action == 'reset':
                self.core.camera.radius = 3.0
                self.core.camera.target = self.core.get_box_size() * 0.5
                self.core.camera.orientation = glm.quat()
                self.core.camera.update_camera_vectors()
                return True
            elif action == 'set_mode':
                mode_map = {'mip': 0, 'volume': 1, 'cinematic': 2, 'mida': 3}
                mode_name = params.get('mode', '').lower()
                if mode_name in mode_map:
                    self.core.set_rendering_mode(mode_map[mode_name])
                    self.combo_render_mode.setCurrentIndex(mode_map[mode_name])
                    return True
            elif action == 'set_tf':
                tf_name = params.get('tf', '').lower()
                if tf_name in self.core.tf_names:
                    self.core.current_tf_name = tf_name
                    self.combo_tf.setCurrentText(tf_name)
                    return True
            elif action == 'set_slice':
                axis = params.get('axis', '').lower()
                axis_map = {'x': 0, 'y': 1, 'z': 2}
                if axis in axis_map:
                    axis_idx = axis_map[axis]
                    vol_dims = self.core.volume_renderer.volume_dim
                    
                    if 'percent' in params:
                        percent = float(params['percent'])
                        value = int((percent / 100.0) * (vol_dims[axis_idx] - 1))
                    else:
                        value = int(params.get('value', 0))
                    
                    value = max(0, min(value, vol_dims[axis_idx] - 1))
                    self.core.slice_indices[axis_idx] = value
                    
                    # Update UI slider
                    sliders = [self.slider_x, self.slider_y, self.slider_z]
                    sliders[axis_idx].setValue(value)
                    return True
            elif action == 'set_lighting':
                mode_name = params.get('mode', '').lower()
                mode_map = {'fixed': 0, 'headlamp': 1}
                if mode_name in mode_map:
                    self.core.lighting_mode = mode_map[mode_name]
                    self.combo_lighting.setCurrentIndex(mode_map[mode_name])
                    return True
            elif action == 'adjust_quality':
                value = float(params.get('value', 1.0))
                self.core.sampling_rate = max(0.1, min(value, 5.0))
                self.slider_quality.setValue(int(value * 10))
                return True
            elif action == 'crop':
                axis = params.get('axis', 'x').lower()
                c_min = float(params.get('min', 0.0))
                c_max = float(params.get('max', 1.0))
                
                if axis == 'x':
                    self.slider_clip_min_x.setValue(int(c_min * 100))
                    self.slider_clip_max_x.setValue(int(c_max * 100))
                elif axis == 'y':
                    self.slider_clip_min_y.setValue(int(c_min * 100))
                    self.slider_clip_max_y.setValue(int(c_max * 100))
                elif axis == 'z':
                    self.slider_clip_min_z.setValue(int(c_min * 100))
                    self.slider_clip_max_z.setValue(int(c_max * 100))
                return True
        except Exception as e:
            print(f"Error applying AI action: {e}")
        return False

    def create_named_slider(self, layout, name, axis_idx, callback):
        layout.addWidget(QLabel(name))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setEnabled(False) # Enable only after load
        slider.valueChanged.connect(callback)
        # Add a value label
        val_label = QLabel("0")
        slider.valueChanged.connect(lambda v: val_label.setText(str(v)))
        layout.addWidget(slider)
        layout.addWidget(val_label)
        return slider

    def create_tf_panel(self, layout):
        container = QFrame()
        container.setObjectName("SidePanel")
        vbox = QVBoxLayout(container)
        
        title = QLabel("TRANSFER FUNCTIONS")
        title.setObjectName("PanelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(title)
        
        self.combo_tf = QComboBox()
        self.combo_tf.addItems(self.core.tf_names)
        self.combo_tf.currentTextChanged.connect(self.on_tf_changed)
        vbox.addWidget(self.combo_tf)
        
        vbox.addWidget(QLabel("Opacity Curve"))
        self.tf_editor = TFEditorWidget(self.core)
        self.tf_editor.pointsChanged.connect(self.on_tf_points_changed)
        vbox.addWidget(self.tf_editor)
        
        hint = QLabel("L-Click: Select/Drag\nR-Click: Add/Remove")
        hint.setStyleSheet("font-size: 10px; color: #888888;")
        vbox.addWidget(hint)
        
        layout.addWidget(container)

    def on_browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Volume Data Folder")
        if folder:
            self.folder_label.setText(folder)
            self.current_folder = folder

    def on_load(self):
        if hasattr(self, 'current_folder'):
            if self.core.load_dataset(self.current_folder):
                # Update slider ranges
                vol_w, vol_h, vol_d = self.core.volume_renderer.volume_dim
                for s, m in [(self.slider_x, vol_w), (self.slider_y, vol_h), (self.slider_z, vol_d)]:
                    s.setRange(0, m - 1)
                    s.setEnabled(True)
                
                self.slider_x.setValue(self.core.slice_indices[0])
                self.slider_y.setValue(self.core.slice_indices[1])
                self.slider_z.setValue(self.core.slice_indices[2])
                
                # Initialize TF
                self.core.set_transfer_function(self.core.current_tf_name)
                self.update_views()

    def on_density_changed(self, val):
        self.core.slice_density = val / 10.0
        self.update_views()

    def on_threshold_changed(self, val):
        self.core.slice_threshold = val / 100.0
        self.update_views()

    def on_slice_x_changed(self, val):
        self.core.slice_indices[0] = val
        self.update_views()

    def on_slice_y_changed(self, val):
        self.core.slice_indices[1] = val
        self.update_views()

    def on_slice_z_changed(self, val):
        self.core.slice_indices[2] = val
        self.update_views()

    def on_clip_changed(self, _):
        self.core.clip_min.x = self.slider_clip_min_x.value() / 100.0
        self.core.clip_max.x = self.slider_clip_max_x.value() / 100.0
        self.core.clip_min.y = self.slider_clip_min_y.value() / 100.0
        self.core.clip_max.y = self.slider_clip_max_y.value() / 100.0
        self.core.clip_min.z = self.slider_clip_min_z.value() / 100.0
        self.core.clip_max.z = self.slider_clip_max_z.value() / 100.0
        self.update_views()


    def on_reset_clipping(self):
        self.slider_clip_min_x.setValue(0)
        self.slider_clip_max_x.setValue(100)
        self.slider_clip_min_y.setValue(0)
        self.slider_clip_max_y.setValue(100)
        self.slider_clip_min_z.setValue(0)
        self.slider_clip_max_z.setValue(100)
        # This will trigger on_clip_changed multiple times but it's fine
        self.update_views()

    def on_tf_changed(self, name):
        self.core.set_transfer_function(name)
        self.tf_editor.update() # Refresh background colormap
        self.update_views()

    def on_tf_points_changed(self, points):
        self.core.update_alpha_points(points)
        self.update_views()

    def update_views(self):
        self.view_axial.update()
        self.view_coronal.update()
        self.view_sagittal.update()
        self.view_3d.update()

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121212;
            }
            QLabel {
                color: #E0E0E0;
                font-family: 'Segoe UI', sans-serif;
            }
            #PanelTitle {
                font-weight: bold;
                font-size: 14px;
                color: #FFFFFF;
                background-color: #2C3E50;
                padding: 5px;
                border-radius: 3px;
                margin-bottom: 5px;
            }
            #SidePanel {
                background-color: #1E1E1E;
                border: 1px solid #333333;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton {
                background-color: #3D3D3D;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4D4D4D;
            }
            #PrimaryButton {
                background-color: #E74C3C; /* Match Red in drawing */
                font-weight: bold;
            }
            #PrimaryButton:hover {
                background-color: #C0392B;
            }
            QSlider::handle:horizontal {
                background: #3498DB;
                width: 14px;
                border-radius: 7px;
            }
            QComboBox {
                background-color: #2C3E50;
                color: white;
                border: 1px solid #3498DB;
                padding: 5px;
                border-radius: 3px;
            }
        """)

if __name__ == "__main__":
    print("Starting PyQt Application...")
    try:
        # Enable context sharing for all QOpenGLWidgets
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        
        app = QApplication(sys.argv)
        
        window = MainWindow()
        window.show()
        print("Application window shown.")
        
        print("Starting app.exec()...")
        res = app.exec()
        print(f"app.exec() returned with code {res}")
        sys.exit(res)
    except Exception as e:
        print(f"Crash during startup: {e}")
        traceback.print_exc()
        sys.exit(1)
