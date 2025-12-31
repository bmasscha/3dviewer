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
        self.slider_vol_density, self.label_vol_density = self.create_labeled_slider(
            vbox, "3D Density Multiplier", 1, 2000, int(self.core.volume_density * 10), 
            self.on_vol_density_changed, transform=lambda v: f"{v/10.0:.1f}"
        )
        
        # Light Intensity
        self.slider_light, self.label_light = self.create_labeled_slider(
            vbox, "Light Intensity", 1, 1000, int(self.core.light_intensity * 100), 
            self.on_light_intensity_changed, transform=lambda v: f"{v/100.0:.2f}"
        )
        
        # Ambient Light
        self.slider_ambient, self.label_ambient = self.create_labeled_slider(
            vbox, "Ambient Light", 0, 100, int(self.core.ambient_light * 100), 
            self.on_ambient_changed, transform=lambda v: f"{v/100.0:.2f}"
        )
        
        # Diffuse Light
        self.slider_diffuse, self.label_diffuse = self.create_labeled_slider(
            vbox, "Diffuse Light", 0, 200, int(self.core.diffuse_light * 100), 
            self.on_diffuse_changed, transform=lambda v: f"{v/100.0:.2f}"
        )
        
        # Sampling Quality
        self.slider_quality, self.label_quality = self.create_labeled_slider(
            vbox, "Sampling Quality", 5, 40, int(self.core.sampling_rate * 10), 
            self.on_quality_changed, transform=lambda v: f"{v/10.0:.1f}"
        )
        
        # Lighting Mode
        vbox.addWidget(QLabel("Lighting Mode"))
        self.combo_light_mode = QComboBox()
        self.combo_light_mode.addItems(self.core.lighting_modes)
        self.combo_light_mode.setCurrentIndex(self.core.lighting_mode)
        self.combo_light_mode.currentIndexChanged.connect(self.on_lighting_mode_changed)
        vbox.addWidget(self.combo_light_mode)
        
        # TF Slope
        self.slider_tf_slope, self.label_tf_slope = self.create_labeled_slider(
            vbox, "TF Slope", 1, 100, int(self.core.tf_slope * 10), 
            self.on_tf_slope_changed, transform=lambda v: f"{v/10.0:.1f}"
        )
        
        # TF Offset
        self.slider_tf_offset, self.label_tf_offset = self.create_labeled_slider(
            vbox, "TF Offset", -200, 200, int(self.core.tf_offset * 100), 
            self.on_tf_offset_changed, transform=lambda v: f"{v/100.0:.2f}"
        )
        
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
        self.slider_density, self.label_density = self.create_labeled_slider(
            vbox, "Slice Density", 1, 50, int(self.core.slice_density * 10), 
            self.on_density_changed, transform=lambda v: f"{v/10.0:.1f}"
        )

        
        # Threshold
        self.slider_threshold, self.label_threshold = self.create_labeled_slider(
            vbox, "Slice Threshold", 0, 100, int(self.core.slice_threshold * 100), 
            self.on_threshold_changed, transform=lambda v: f"{v/100.0:.2f}"
        )
        
        # Slices
        self.slider_x, self.label_x = self.create_named_slider(vbox, "Slice X", 0, self.on_slice_x_changed)
        self.slider_y, self.label_y = self.create_named_slider(vbox, "Slice Y", 1, self.on_slice_y_changed)
        self.slider_z, self.label_z = self.create_named_slider(vbox, "Slice Z", 2, self.on_slice_z_changed)
        
        layout.addWidget(container)


    def create_clipping_panel(self, layout):
        container = QFrame()
        container.setObjectName("SidePanel")
        vbox = QVBoxLayout(container)
        
        title = QLabel("VOLUME CROPPING")
        title.setObjectName("PanelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(title)
        
        self.slider_clip_min_x, self.label_clip_min_x = self.create_percent_slider(vbox, "Min X", 0, self.on_clip_changed)
        self.slider_clip_max_x, self.label_clip_max_x = self.create_percent_slider(vbox, "Max X", 100, self.on_clip_changed)
        self.slider_clip_min_y, self.label_clip_min_y = self.create_percent_slider(vbox, "Min Y", 0, self.on_clip_changed)
        self.slider_clip_max_y, self.label_clip_max_y = self.create_percent_slider(vbox, "Max Y", 100, self.on_clip_changed)
        self.slider_clip_min_z, self.label_clip_min_z = self.create_percent_slider(vbox, "Min Z", 0, self.on_clip_changed)
        self.slider_clip_max_z, self.label_clip_max_z = self.create_percent_slider(vbox, "Max Z", 100, self.on_clip_changed)
        
        btn_reset_clip = QPushButton("Reset Clipping")
        btn_reset_clip.clicked.connect(self.on_reset_clipping)
        vbox.addWidget(btn_reset_clip)
        
        layout.addWidget(container)


    def create_percent_slider(self, layout, name, default_val, callback):
        return self.create_labeled_slider(layout, name, 0, 100, default_val, callback, transform=lambda v: f"{v}%")

    def create_labeled_slider(self, layout, name, min_val, max_val, initial_val, callback, transform=None):
        header = QHBoxLayout()
        header.addWidget(QLabel(name))
        header.addStretch()
        
        val_str = str(initial_val)
        if transform:
            val_str = transform(initial_val)
            
        val_label = QLabel(val_str)
        val_label.setStyleSheet("color: #3498DB; font-weight: bold;")
        header.addWidget(val_label)
        layout.addLayout(header)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(initial_val)
        
        def on_val_changed(v):
            if transform:
                val_label.setText(transform(v))
            else:
                val_label.setText(str(v))
            callback(v)
            
        slider.valueChanged.connect(on_val_changed)
        layout.addWidget(slider)
        return slider, val_label


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
            self.sync_ui_to_core() # New sync method
            self.update_views()

    def sync_ui_to_core(self):
        """Syncs all UI elements to match current core state."""
        # Update render mode
        self.combo_render_mode.setCurrentIndex(self.core.rendering_mode)
        
        # Update sliders
        self.slider_vol_density.setValue(int(self.core.volume_density * 10))
        self.slider_quality.setValue(int(self.core.sampling_rate * 10))
        self.slider_light.setValue(int(self.core.light_intensity * 100))
        self.slider_ambient.setValue(int(self.core.ambient_light * 100))
        self.slider_diffuse.setValue(int(self.core.diffuse_light * 100))
        self.slider_tf_slope.setValue(int(self.core.tf_slope * 10))
        self.slider_tf_offset.setValue(int(self.core.tf_offset * 100))
        
        # Labels are updated via valueChanged signals, but if value hasn't changed
        # we might want to force update just in case of float precision differences in display
        self.label_vol_density.setText(f"{self.core.volume_density:.1f}")
        self.label_quality.setText(f"{self.core.sampling_rate:.1f}")
        self.label_light.setText(f"{self.core.light_intensity:.2f}")
        self.label_ambient.setText(f"{self.core.ambient_light:.2f}")
        self.label_diffuse.setText(f"{self.core.diffuse_light:.2f}")
        self.label_tf_slope.setText(f"{self.core.tf_slope:.1f}")
        self.label_tf_offset.setText(f"{self.core.tf_offset:.2f}")

        
        # Update slice ranges/values
        vol_w, vol_h, vol_d = self.core.volume_renderer.volume_dims[0]
        if vol_w > 0:
            for s, m, v in [(self.slider_x, vol_w, self.core.slice_indices[0]), 
                           (self.slider_y, vol_h, self.core.slice_indices[1]), 
                           (self.slider_z, vol_d, self.core.slice_indices[2])]:
                s.setRange(0, m - 1)
                s.setEnabled(True)
                s.setValue(v)
            self.folder_label.setText(getattr(self, 'current_folder', "Loaded via Command"))

        # Sync TF selection
        self.combo_tf.setCurrentText(self.core.current_tf_name)
        
        # Note: We don't have separate sliders for overlay in the side panel yet,
        # but the core state IS updated.

    def apply_ai_action(self, action_dict):
        """Executes the action via AppCore to ensure consistency, then updates UI."""
        if not action_dict:
            return False
            
        # Instead of manual parsing, use the unified logic in AppCore
        # We need the original text for 'overlay' detection if we rely on it there,
        # but since we have the action_dict, we can also pass it to a new core method if needed.
        # For now, AppCore.execute_command_text(text) is the safest way to keep logic in one place.
        success, message = self.core.execute_command_text(self.worker.text)
        return success

    def create_named_slider(self, layout, name, axis_idx, callback):
        slider, label = self.create_labeled_slider(layout, name, 0, 100, 0, callback)
        slider.setEnabled(False)
        return slider, label



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
                vol_w, vol_h, vol_d = self.core.volume_renderer.volume_dims[0]
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
