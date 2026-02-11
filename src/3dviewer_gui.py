import sys
import os
import traceback
import logging
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QLabel, QSlider,
                             QPushButton, QComboBox, QFileDialog, QFrame,
                             QScrollArea, QLineEdit, QTextEdit, QProgressDialog,
                             QStackedLayout, QDoubleSpinBox, QSpinBox, QMessageBox,
                             QCheckBox)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPainter
from datetime import datetime
from app_core import AppCore
from widgets.gl_view import GLViewWidget
from widgets.tf_editor import TFEditorWidget
from zmq_client import ViewerZMQClient
from widgets.import_dialog import ImportDialog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class LoadVolumeThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)
    
    def __init__(self, loader, folder_path, **kwargs):
        super().__init__()
        self.loader = loader
        self.folder_path = folder_path
        self.kwargs = kwargs
        
    def run(self):
        def progress_cb(msg):
            self.progress.emit(msg)
            
        try:
            if os.path.isfile(self.folder_path):
                data = self.loader.load_from_h5(self.folder_path, progress_callback=progress_cb, **self.kwargs)
            else:
                data = self.loader.load_from_folder(self.folder_path, progress_callback=progress_cb, **self.kwargs)
            self.finished.emit(data)
        except Exception as e:
            logging.error(f"LoadVolumeThread error: {e}")
            self.finished.emit(None) # Signal failure

class FilterWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, core, filter_name, params):
        super().__init__()
        self.core = core
        self.filter_name = filter_name
        self.params = params
        self.is_cancelled = False
        
    def run(self):
        def check_cancel():
            return self.is_cancelled
            
        def on_progress(val):
            self.progress.emit(val)
            
        try:
            success, msg = self.core.apply_filter(
                self.filter_name, 
                progress_callback=on_progress, 
                check_cancel=check_cancel, 
                **self.params
            )
            self.finished.emit(success, msg)
        except Exception as e:
            self.finished.emit(False, str(e))
        
    def cancel(self):
        self.is_cancelled = True

class AIWorker(QThread):
    finished = pyqtSignal(object, str) # returns (action_dict, response_msg)
    
    def __init__(self, interpreter, text, state=None):
        super().__init__()
        self.interpreter = interpreter
        self.text = text
        self.state = state
        
    def run(self):
        try:
            action_dict, response_msg = self.interpreter.interpret(self.text, state=self.state)
            self.finished.emit(action_dict, response_msg)
        except Exception as e:
            self.finished.emit(None, f"Internal Error: {str(e)}")

class CommandInput(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.history_index = -1
        self.temporary_command = ""

    def add_to_history(self, text):
        if not text or not text.strip():
            return
        # Don't add if same as last
        if not self.history or self.history[-1] != text:
            self.history.append(text)
        self.history_index = -1
        self.temporary_command = ""

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Up:
            if not self.history:
                return
            if self.history_index == -1:
                # Save current unfinished input
                self.temporary_command = self.text()
                self.history_index = len(self.history) - 1
            elif self.history_index > 0:
                self.history_index -= 1
            self.setText(self.history[self.history_index])
        elif event.key() == Qt.Key.Key_Down:
            if self.history_index == -1:
                return
            if self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.setText(self.history[self.history_index])
            else:
                self.history_index = -1
                self.setText(self.temporary_command)
        else:
            super().keyPressEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Viewer Bert v0.0.7")
        self.resize(1600, 900)
        
        self.core = AppCore()
        # Delay shader loading until GL context is ready
        self.setup_ui()
        self.apply_stylesheet()
        
        # UPDATED PORTS: Inbound=50001 (Server's Out), Outbound=50000 (Server's In)
        self.zmq_client = ViewerZMQClient(self.core, server_ip="127.0.0.1", inbound_port=50001, outbound_port=50000)
        
        # Connect new signals for thread-safe execution
        self.zmq_client.sig_load_data.connect(self.handle_zmq_load_data)
        self.zmq_client.sig_set_tf.connect(self.handle_zmq_set_tf)
        self.zmq_client.sig_exec_command.connect(self.handle_zmq_exec_command)
        self.zmq_client.sig_command_processed.connect(self._update_gui_after_zmq_command)
        
        # Legacy callback (optional now, but kept for logging)
        self.zmq_client.set_command_callback(self.on_zmq_command_received)
        
        self.zmq_client.start(component_name="3dviewer", physical_name="3dviewer")
        logging.info("ZMQ client started - ready to receive commands")
        
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

        # View Layout Selection (NEW)
        self.create_layout_panel(left_sidebar)
        
        # Virtual Phase Contrast (Post-Processing)
        self.create_vpc_panel(left_sidebar)
        
        # Slice Controls
        self.create_slice_panel(left_sidebar)

        # Clipping Controls
        self.create_clipping_panel(left_sidebar)

        # Noise Filter
        self.create_filter_panel(left_sidebar)

        # Command Control
        self.create_command_panel(left_sidebar)
        
        left_sidebar.addStretch()
        left_scroll.setWidget(left_widget)
        main_layout.addWidget(left_scroll, 1)

        # --- Center Grid (Viewports) ---
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(5)
        
        self.view_axial = GLViewWidget(self.core, "Axial")
        self.view_coronal = GLViewWidget(self.core, "Coronal")
        self.view_sagittal = GLViewWidget(self.core, "Sagittal")
        self.view_3d = GLViewWidget(self.core, "3D")
        
        self.grid_layout.addWidget(self.view_axial, 0, 0)
        self.grid_layout.addWidget(self.view_sagittal, 0, 1) # Match drawing: Axial, Sagittal
        self.grid_layout.addWidget(self.view_coronal, 1, 0)
        self.grid_layout.addWidget(self.view_3d, 1, 1)
        
        # Connect save signals
        for view in [self.view_axial, self.view_coronal, self.view_sagittal, self.view_3d]:
            view.sig_save_request.connect(lambda mode, v=view: self.on_request_save_view(v, mode))
            # Connect export slices signal (only for orthogonal views)
            if view.mode != "3D":
                view.sig_export_slices.connect(lambda mode, v=view: self.on_request_export_slices(v, mode))
                view.sig_slice_changed.connect(self.sync_ui_to_core)
            else:
                view.sig_record_movie.connect(self.on_request_record_movie)

        # Set titles for views
        self.add_viewport_overlay(self.grid_layout, "Axial", 0, 0)
        self.add_viewport_overlay(self.grid_layout, "Sagittal", 0, 1)
        self.add_viewport_overlay(self.grid_layout, "Coronal", 1, 0)
        self.add_viewport_overlay(self.grid_layout, "Rendering (3D)", 1, 1)

        main_layout.addLayout(self.grid_layout, 4)

        # --- Right Sidebar ---
        right_widget = QWidget()
        right_sidebar = QVBoxLayout(right_widget)
        right_sidebar.setSpacing(15)
        right_sidebar.setContentsMargins(10, 0, 0, 0)

        # Rendering Methods (Moved from left)
        self.create_rendering_panel(right_sidebar)

        self.create_tf_panel(right_sidebar)
        right_sidebar.addStretch()
        
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setWidget(right_widget)
        
        main_layout.addWidget(right_scroll, 1)

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
        
        # Field of View
        self.slider_fov, self.label_fov = self.create_labeled_slider(
            vbox, "Field of View (FOV)", 10, 120, int(self.core.camera.fov), 
            self.on_fov_changed, transform=lambda v: f"{v} deg"
        )
        
        # 3D Density
        self.slider_vol_density, self.label_vol_density = self.create_labeled_slider(
            vbox, "3D Density Multiplier", 1, 2000, int(self.core.volume_density * 10), 
            self.on_vol_density_changed, transform=lambda v: f"{v/10.0:.1f}"
        )
        
        # 3D Threshold
        self.slider_vol_threshold, self.label_vol_threshold = self.create_labeled_slider(
            vbox, "3D Volume Threshold", 0, 100, int(self.core.volume_threshold * 100), 
            self.on_vol_threshold_changed, transform=lambda v: f"{v/100.0:.2f}"
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

        # Specular Intensity
        self.slider_specular, self.label_specular = self.create_labeled_slider(
            vbox, "Specular Intensity", 0, 200, int(self.core.specular_intensity * 100), 
            self.on_specular_changed, transform=lambda v: f"{v/100.0:.2f}"
        )

        # Shininess
        self.slider_shininess, self.label_shininess = self.create_labeled_slider(
            vbox, "Shininess (Phong)", 1, 128, int(self.core.shininess), 
            self.on_shininess_changed
        )
        
        # Edge Magnitude (Gradient Weight)
        self.slider_grad_weight, self.label_grad_weight = self.create_labeled_slider(
            vbox, "Edge Enhancement", 0, 50, int(self.core.gradient_weight), 
            self.on_grad_weight_changed
        )
        
        # Sampling Quality
        self.slider_quality, self.label_quality = self.create_labeled_slider(
            vbox, "Sampling Quality", 10, 100, int(self.core.sampling_rate * 10), 
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


    def create_vpc_panel(self, layout):
        container = QFrame()
        container.setObjectName("SidePanel")
        vbox = QVBoxLayout(container)
        
        title = QLabel("VIRTUAL PHASE CONTRAST")
        title.setObjectName("PanelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(title)
        
        # Enable Toggle
        self.chk_vpc = QCheckBox("Enable VPC Filter")
        self.chk_vpc.setChecked(self.core.vpc_enabled)
        self.chk_vpc.toggled.connect(self.on_vpc_toggled)
        self.chk_vpc.setStyleSheet("color: white; margin-bottom: 5px;")
        vbox.addWidget(self.chk_vpc)
        
        # Distance Slider
        self.slider_vpc_dist, self.label_vpc_dist = self.create_labeled_slider(
            vbox, "Propagation Distance", 0, 200, int(self.core.vpc_distance), 
            self.on_vpc_distance_changed, transform=lambda v: f"{v}"
        )
        
        # Wavelength Slider
        self.slider_vpc_wave, self.label_vpc_wave = self.create_labeled_slider(
            vbox, "Wavelength Factor", 1, 100, int(self.core.vpc_wavelength * 10), 
            self.on_vpc_wavelength_changed, transform=lambda v: f"{v/10.0:.1f}"
        )

        layout.addWidget(container)

    def on_vpc_toggled(self, checked):
        self.core.vpc_enabled = checked
        self.update_views()

    def on_scale_bar_toggled(self, checked):
        self.core.show_scale_bar = checked
        self.update_views()

    def on_vpc_distance_changed(self, val):
        self.core.vpc_distance = float(val)
        self.update_views()

    def on_vpc_wavelength_changed(self, val):
        self.core.vpc_wavelength = val / 10.0
        self.update_views()

    def on_render_mode_changed(self, index):
        self.core.set_rendering_mode(index)
        self.update_views()

    def on_vol_density_changed(self, val):
        self.core.volume_density = val / 10.0
        self.update_views()

    def on_vol_threshold_changed(self, val):
        self.core.volume_threshold = val / 100.0
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

    def on_specular_changed(self, val):
        self.core.specular_intensity = val / 100.0
        self.update_views()

    def on_shininess_changed(self, val):
        self.core.shininess = float(val)
        self.update_views()

    def on_grad_weight_changed(self, val):
        self.core.gradient_weight = float(val)
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

    def on_fov_changed(self, val):
        self.core.camera.fov = float(val)
        self.update_views()

    def on_request_save_view(self, source_view, mode):
        """Handles saving one or all views to an image file."""
        # 1. Determine base path
        base_path = self.core.current_dataset_path
        if not base_path or not os.path.isdir(base_path):
            # Fallback to current working directory if no dataset loaded
            base_path = os.getcwd()
            
        # 2. Ensure "images" folder exists
        img_dir = os.path.join(base_path, "images")
        try:
            os.makedirs(img_dir, exist_ok=True)
        except Exception as e:
            logging.error(f"Failed to create images directory: {e}")
            img_dir = base_path # Fallback
            
        # 3. Generate default filename
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"{now}.png"
        full_suggested_path = os.path.join(img_dir, default_name)
        
        # 4. Ask user for path and name
        save_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save View as Image", full_suggested_path, 
            "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg)"
        )
        
        if not save_path:
            return
            
        try:
            if mode == "single":
                # Grab just this viewport
                pixmap = source_view.grabFramebuffer()
                pixmap.save(save_path)
            else:
                # Grab all 4 viewports and compose
                img_axial = self.view_axial.grabFramebuffer()
                img_sag = self.view_sagittal.grabFramebuffer()
                img_cor = self.view_coronal.grabFramebuffer()
                img_3d = self.view_3d.grabFramebuffer()
                
                # Composition (2x2)
                w, h = img_axial.width(), img_axial.height()
                combined = QImage(w * 2, h * 2, QImage.Format.Format_ARGB32)
                painter = QPainter(combined)
                painter.drawImage(0, 0, img_axial)
                painter.drawImage(w, 0, img_sag)
                painter.drawImage(0, h, img_cor)
                painter.drawImage(w, h, img_3d)
                painter.end()
                
                combined.save(save_path)
                
            logging.info(f"Image saved to: {save_path}")
            # Show a brief status message if possible, but logging is fine for now
        except Exception as e:
            logging.error(f"Failed to save image: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Save Error", f"Could not save image: {str(e)}")

    def on_request_export_slices(self, source_view, mode):
        """Exports all slices along the specified orthogonal axis as individual PNG files."""
        from PyQt6.QtWidgets import QMessageBox, QFileDialog, QProgressDialog, QApplication

        # 1. Determine axis and slice range
        vol_w, vol_h, vol_d = self.core.volume_renderer.volume_dims[0]

        if mode == "Axial":
            axis_idx = 2
            num_slices = vol_d
        elif mode == "Coronal":
            axis_idx = 1
            num_slices = vol_h
        elif mode == "Sagittal":
            axis_idx = 0
            num_slices = vol_w
        else:
            logging.error(f"Invalid mode for slice export: {mode}")
            return

        if num_slices == 0:
            QMessageBox.warning(self, "Export Error", "No volume data loaded.")
            return

        # 2. Ask user for output folder
        base_path = self.core.current_dataset_path
        if not base_path or not os.path.isdir(base_path):
            base_path = os.getcwd()

        # Suggest "slices_[mode]" folder
        suggested_folder = os.path.join(base_path, f"slices_{mode.lower()}")

        output_folder = QFileDialog.getExistingDirectory(
            self,
            f"Select Output Folder for {mode} Slices ({num_slices} images)",
            suggested_folder
        )

        if not output_folder:
            return

        # 3. Create output folder if it doesn't exist
        try:
            os.makedirs(output_folder, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Folder Error", f"Could not create output folder: {str(e)}")
            return

        # 4. Store original slice index
        original_slice_idx = self.core.slice_indices[axis_idx]

        # 5. Setup progress dialog
        progress = QProgressDialog(f"Exporting {mode} slices...", "Cancel", 0, num_slices, self)
        progress.setWindowTitle("Export Progress")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        # 6. Iterate through all slices
        exported_count = 0
        try:
            for slice_idx in range(num_slices):
                # Check for cancellation
                if progress.wasCanceled():
                    logging.info(f"Slice export cancelled at {slice_idx}/{num_slices}")
                    break

                # Update progress
                progress.setValue(slice_idx)
                progress.setLabelText(f"Exporting {mode} slice {slice_idx + 1}/{num_slices}...")

                # Update slice index
                self.core.slice_indices[axis_idx] = slice_idx

                # Trigger render
                source_view.update()

                # Process events to ensure rendering completes
                QApplication.processEvents()

                # Capture framebuffer
                pixmap = source_view.grabFramebuffer()

                # Generate filename with zero-padded index
                filename = f"{mode.lower()}_{slice_idx:03d}.png"
                filepath = os.path.join(output_folder, filename)

                # Save PNG
                if pixmap.save(filepath):
                    exported_count += 1
                else:
                    logging.warning(f"Failed to save slice {slice_idx} to {filepath}")

            # Final progress update
            progress.setValue(num_slices)

        except Exception as e:
            logging.error(f"Error during slice export: {e}")
            QMessageBox.critical(self, "Export Error", f"Export failed: {str(e)}")

        finally:
            # 7. Restore original slice index
            self.core.slice_indices[axis_idx] = original_slice_idx
            source_view.update()
            progress.close()

        # 8. Show completion message
        if exported_count > 0:
            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported {exported_count} slices to:\n{output_folder}"
            )
            logging.info(f"Exported {exported_count} {mode} slices to {output_folder}")
        else:
            QMessageBox.warning(self, "Export Cancelled", "No slices were exported.")

    def create_layout_panel(self, layout):
        container = QFrame()
        container.setObjectName("SidePanel")
        vbox = QVBoxLayout(container)
        
        title = QLabel("VIEW LAYOUT")
        title.setObjectName("PanelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(title)
        
        layout_grid = QGridLayout()
        
        presets = [
            ("Grid (2x2)", "Grid"),
            ("Axial Only", "Axial"),
            ("Coronal Only", "Coronal"),
            ("Sagittal Only", "Sagittal"),
            ("3D View Only", "3D"),
            ("Axial + 3D", "Dual_A3")
        ]
        
        for i, (label, mode) in enumerate(presets):
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, m=mode: self.set_view_layout(m))
            layout_grid.addWidget(btn, i // 2, i % 2)
            
        vbox.addLayout(layout_grid)
        layout.addWidget(container)

    def set_view_layout(self, mode):
        """Changes the viewport arrangement."""
        # Hide all first
        self.view_axial.hide()
        self.view_coronal.hide()
        self.view_sagittal.hide()
        self.view_3d.hide()
        
        # We also need to hide/show viewport labels if we decide to implement them properly.
        # Currently, add_viewport_overlay is just a placeholder.
        
        # Clear existing widgets from the grid layout
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None) # Remove from layout but don't delete widget
        
        if mode == "Grid":
            self.grid_layout.addWidget(self.view_axial, 0, 0)
            self.grid_layout.addWidget(self.view_sagittal, 0, 1)
            self.grid_layout.addWidget(self.view_coronal, 1, 0)
            self.grid_layout.addWidget(self.view_3d, 1, 1)
            self.view_axial.show()
            self.view_coronal.show()
            self.view_sagittal.show()
            self.view_3d.show()
        elif mode == "Axial":
            self.grid_layout.addWidget(self.view_axial, 0, 0, 2, 2)
            self.view_axial.show()
        elif mode == "Coronal":
            self.grid_layout.addWidget(self.view_coronal, 0, 0, 2, 2)
            self.view_coronal.show()
        elif mode == "Sagittal":
            self.grid_layout.addWidget(self.view_sagittal, 0, 0, 2, 2)
            self.view_sagittal.show()
        elif mode == "3D":
            self.grid_layout.addWidget(self.view_3d, 0, 0, 2, 2)
            self.view_3d.show()
        elif mode == "Dual_A3":
            self.grid_layout.addWidget(self.view_axial, 0, 0, 2, 1)
            self.grid_layout.addWidget(self.view_3d, 0, 1, 2, 1)
            self.view_axial.show()
            self.view_3d.show()
            
        logging.info(f"Layout changed to: {mode}")

    def create_dataset_panel(self, layout):
        container = QFrame()
        container.setObjectName("SidePanel")
        vbox = QVBoxLayout(container)
        
        title = QLabel("DATASET SELECTION")
        title.setObjectName("PanelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(title)
        
        btn_import_adv = QPushButton("Import Advanced...")
        btn_import_adv.clicked.connect(self.on_import_advanced)
        vbox.addWidget(btn_import_adv)
        
        # Label to show current dataset folder
        self.folder_label = QLabel("No dataset loaded")
        self.folder_label.setWordWrap(True)
        self.folder_label.setStyleSheet("font-size: 10px; color: #888888; padding: 5px;")
        vbox.addWidget(self.folder_label)
        
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
            vbox, "Slice Density", 1, 10, int(self.core.slice_density * 10), 
            self.on_density_changed, transform=lambda v: f"{v/10.0:.2f}"
        )

        
        # Threshold
        self.slider_threshold, self.label_threshold = self.create_labeled_slider(
            vbox, "Slice Threshold", 0, 100, int(self.core.slice_threshold * 100), 
            self.on_threshold_changed, transform=lambda v: f"{v/100.0:.2f}"
        )
        
        # Slices (Medical equivalents: Sagittal=X, Coronal=Y, Axial=Z)
        self.slider_x, self.label_x = self.create_named_slider(vbox, "Sagittal (X)", 0, self.on_slice_x_changed)
        self.slider_y, self.label_y = self.create_named_slider(vbox, "Coronal (Y)", 1, self.on_slice_y_changed)
        self.slider_z, self.label_z = self.create_named_slider(vbox, "Axial (Z)", 2, self.on_slice_z_changed)

        # Scale Bar Toggle
        self.chk_scale_bar = QCheckBox("Show Scale Bar")
        self.chk_scale_bar.setChecked(self.core.show_scale_bar)
        self.chk_scale_bar.toggled.connect(self.on_scale_bar_toggled)
        self.chk_scale_bar.setStyleSheet("color: white; margin-top: 10px;")
        vbox.addWidget(self.chk_scale_bar)

        # Geometry Info Label
        self.geometry_label = QLabel("Voxel size: N/A")
        self.geometry_label.setStyleSheet("font-size: 10px; color: #888888; padding: 2px;")
        vbox.addWidget(self.geometry_label)

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


        layout.addWidget(container)

    def create_filter_panel(self, layout):
        container = QFrame()
        container.setObjectName("SidePanel")
        vbox = QVBoxLayout(container)
        
        title = QLabel("NOISE FILTER")
        title.setObjectName("PanelTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(title)
        
        self.combo_filter_type = QComboBox()
        self.combo_filter_type.addItems(["Gaussian", "Median", "Bilateral", "NLM", "Total Variation"])
        self.combo_filter_type.currentIndexChanged.connect(self.on_filter_type_changed)
        vbox.addWidget(self.combo_filter_type)
        
        # Stacked Widget for Parameters
        self.stack_filter_params = QStackedLayout()
        
        # 1. Gaussian Params
        page_gaussian = QWidget()
        layout_gaussian = QVBoxLayout(page_gaussian)
        layout_gaussian.setContentsMargins(0, 5, 0, 5)
        
        row_sigma = QHBoxLayout()
        row_sigma.addWidget(QLabel("Sigma:"))
        self.spin_sigma = QDoubleSpinBox()
        self.spin_sigma.setRange(0.1, 5.0)
        self.spin_sigma.setSingleStep(0.1)
        self.spin_sigma.setValue(1.0)
        row_sigma.addWidget(self.spin_sigma)
        layout_gaussian.addLayout(row_sigma)
        
        # 2. Median Params
        page_median = QWidget()
        layout_median = QVBoxLayout(page_median)
        layout_median.setContentsMargins(0, 5, 0, 5)
        
        row_size = QHBoxLayout()
        row_size.addWidget(QLabel("Size:"))
        self.spin_median_size = QSpinBox()
        self.spin_median_size.setRange(2, 10)
        self.spin_median_size.setSingleStep(1)
        self.spin_median_size.setValue(3)
        row_size.addWidget(self.spin_median_size)
        layout_median.addLayout(row_size)
        
        # Create a placeholder widget to hold the stacked layout because QStackedLayout cannot be added directly to QVBoxLayout
        # Wait, QStackedLayout is a layout, not a widget. We need a container widget.
        # Actually simplest is just to add the pages to a QStackedWidget
        from PyQt6.QtWidgets import QStackedWidget
        # Filter Settings Stack
        self.stack_widget = QStackedWidget()
        self.stack_widget.setStyleSheet("""
            QDoubleSpinBox, QSpinBox {
                color: #FFFFFF;
                background-color: #333333;
                border: 1px solid #555555;
                padding: 2px;
                border-radius: 3px;
            }
            QLabel {
                color: #DDDDDD;
            }
        """)
        self.stack_widget.addWidget(page_gaussian)
        self.stack_widget.addWidget(page_median)
        
        # 3. Bilateral Params
        page_bilateral = QWidget()
        layout_bilateral = QVBoxLayout(page_bilateral)
        layout_bilateral.setContentsMargins(0, 5, 0, 5)
        
        row_bi_spatial = QHBoxLayout()
        row_bi_spatial.addWidget(QLabel("Sigma Spatial:"))
        self.spin_bi_spatial = QDoubleSpinBox()
        self.spin_bi_spatial.setRange(0.1, 10.0)
        self.spin_bi_spatial.setValue(1.0)
        self.spin_bi_spatial.setSingleStep(0.1)
        row_bi_spatial.addWidget(self.spin_bi_spatial)
        layout_bilateral.addLayout(row_bi_spatial)
        
        row_bi_color = QHBoxLayout()
        row_bi_color.addWidget(QLabel("Sigma Color:"))
        self.spin_bi_color = QDoubleSpinBox()
        self.spin_bi_color.setRange(0.01, 1.0)
        self.spin_bi_color.setValue(0.05)
        self.spin_bi_color.setSingleStep(0.01)
        row_bi_color.addWidget(self.spin_bi_color)
        layout_bilateral.addLayout(row_bi_color)
        self.stack_widget.addWidget(page_bilateral)

        # 4. NLM Params
        page_nlm = QWidget()
        layout_nlm = QVBoxLayout(page_nlm)
        layout_nlm.setContentsMargins(0, 5, 0, 5)
        
        row_nlm_h = QHBoxLayout()
        row_nlm_h.addWidget(QLabel("h (Smooth):"))
        self.spin_nlm_h = QDoubleSpinBox()
        self.spin_nlm_h.setRange(0.1, 5.0)
        self.spin_nlm_h.setValue(1.15)
        self.spin_nlm_h.setSingleStep(0.05)
        row_nlm_h.addWidget(self.spin_nlm_h)
        layout_nlm.addLayout(row_nlm_h)
        self.stack_widget.addWidget(page_nlm)

        # 5. TV Params
        page_tv = QWidget()
        layout_tv = QVBoxLayout(page_tv)
        layout_tv.setContentsMargins(0, 5, 0, 5)
        
        row_tv_w = QHBoxLayout()
        row_tv_w.addWidget(QLabel("Weight:"))
        self.spin_tv_weight = QDoubleSpinBox()
        self.spin_tv_weight.setRange(0.01, 1.0)
        self.spin_tv_weight.setValue(0.1)
        self.spin_tv_weight.setSingleStep(0.01)
        row_tv_w.addWidget(self.spin_tv_weight)
        layout_tv.addLayout(row_tv_w)
        self.stack_widget.addWidget(page_tv)
        
        self.stack_widget.setFixedHeight(80) # Increased height for more params
        
        vbox.addWidget(self.stack_widget)
        
        # Apply Button
        self.btn_apply_filter = QPushButton("Apply Filter (CPU)")
        self.btn_apply_filter.clicked.connect(self.on_apply_filter)
        self.btn_apply_filter.setStyleSheet("background-color: #E67E22; color: white; font-weight: bold;")
        vbox.addWidget(self.btn_apply_filter)
        
        layout.addWidget(container)

    def on_filter_type_changed(self, index):
        self.stack_widget.setCurrentIndex(index)

    def on_apply_filter(self):
        filter_name = self.combo_filter_type.currentText()
        params = {}
        
        if filter_name == "Gaussian":
            params['sigma'] = self.spin_sigma.value()
        elif filter_name == "Median":
            # Ensure odd size for median usually, but scipy handles it. 
            # Scipy median_filter footprint is size^ndim. 
            # If user picks even, it still works but behavior at center might be shifted. 
            # We'll just pass it.
            params['size'] = self.spin_median_size.value()
        elif filter_name == "Bilateral":
            params['sigma_spatial'] = self.spin_bi_spatial.value()
            params['sigma_color'] = self.spin_bi_color.value()
        elif filter_name == "NLM":
            params['h'] = self.spin_nlm_h.value()
            # Hardcoded mostly for simplicity in UI, but could expose
            params['patch_size'] = 5 
            params['patch_distance'] = 6
        elif filter_name == "Total Variation":
            params['weight'] = self.spin_tv_weight.value()
            
        # Confirm with user
        ret = QMessageBox.question(self, "Apply Filter", 
                                   f"This will apply {filter_name} filter on CPU.\n"
                                   "It may take a few seconds/minutes depending on volume size.\n"
                                   "Current data will be modified.\n\nContinue?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if ret != QMessageBox.StandardButton.Yes:
            return

        # Show Progress Dialog
        self.progress_dialog = QProgressDialog("Applying Filter...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setAutoClose(False) # We will close it manually
        self.progress_dialog.setAutoReset(False)
        
        # Setup Worker
        self.worker = FilterWorker(self.core, filter_name, params)
        self.worker.progress.connect(self.progress_dialog.setValue)
        self.worker.finished.connect(self.on_filter_finished)
        
        # Connect Cancel
        # When user clicks Cancel button on dialog, it emits canceled()
        self.progress_dialog.canceled.connect(self.worker.cancel)
        
        self.worker.start()
        
    def on_filter_finished(self, success, msg):
        self.progress_dialog.close()
        
        if success:
            # Update the OpenGL texture on the main thread
            self.core.update_render_texture()
            self.update_views()
            QMessageBox.information(self, "Filter Result", msg)
            logging.info(msg)
        else:
            if "cancelled" in msg:
                QMessageBox.information(self, "Cancelled", msg)
            else:
                QMessageBox.warning(self, "Failed", msg)
            logging.warning(msg)

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
        
        self.cmd_input = CommandInput()
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
        self.cmd_input.add_to_history(text)
        
        # Disable input while processing
        self.cmd_input.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.cmd_log.append("<i style='color:#888'>AI is thinking...</i>")
        
        # Start worker thread
        self.worker = AIWorker(self.core.command_interpreter, text, state=self.core.get_state())
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
        
        # Sync VPC Controls
        self.chk_vpc.setChecked(self.core.vpc_enabled)
        self.slider_vpc_dist.setValue(int(self.core.vpc_distance))
        self.slider_vpc_wave.setValue(int(self.core.vpc_wavelength * 10))
        self.label_vpc_dist.setText(f"{int(self.core.vpc_distance)}")
        self.label_vpc_wave.setText(f"{self.core.vpc_wavelength:.1f}")

        # Labels are updated via valueChanged signals, but if value hasn't changed
        # we might want to force update just in case of float precision differences in display
        self.label_vol_density.setText(f"{self.core.volume_density:.1f}")
        self.label_quality.setText(f"{self.core.sampling_rate:.1f}")
        self.label_light.setText(f"{self.core.light_intensity:.2f}")
        self.label_ambient.setText(f"{self.core.ambient_light:.2f}")
        self.label_diffuse.setText(f"{self.core.diffuse_light:.2f}")
        self.label_tf_slope.setText(f"{self.core.tf_slope:.1f}")
        self.label_tf_offset.setText(f"{self.core.tf_offset:.2f}")

        self.slider_specular.setValue(int(self.core.specular_intensity * 100))
        self.slider_shininess.setValue(int(self.core.shininess))
        self.slider_grad_weight.setValue(int(self.core.gradient_weight))
        
        self.label_specular.setText(f"{self.core.specular_intensity:.2f}")
        self.label_shininess.setText(f"{self.core.shininess:.1f}")
        self.label_grad_weight.setText(f"{self.core.gradient_weight:.1f}")



        # Sync FOV
        self.slider_fov.setValue(int(self.core.camera.fov))
        self.label_fov.setText(f"{self.core.camera.fov} deg")
        vol_w, vol_h, vol_d = self.core.volume_renderer.volume_dims[0]
        if vol_w > 0:
            for s, m, v in [(self.slider_x, vol_w, self.core.slice_indices[0]), 
                           (self.slider_y, vol_h, self.core.slice_indices[1]), 
                           (self.slider_z, vol_d, self.core.slice_indices[2])]:
                s.setRange(0, m - 1)
                s.setEnabled(True)
                s.setValue(v)
            self.folder_label.setText(getattr(self, 'current_folder', "Loaded via Command"))
            self.update_geometry_label()

        # Sync TF selection
        self.combo_tf.setCurrentText(self.core.current_tf_name)
        
        # Note: We don't have separate sliders for overlay in the side panel yet,
        # but the core state IS updated.

    def handle_zmq_load_data(self, metadata: dict):
        """
        Slot to handle load_data request from ZMQ thread on the Main Thread.
        """
        path = metadata.get("path", "")
        uuid = metadata.get("UUID", "")
            
        logging.info(f"ZMQ requested load_data: {path}")
        
        # Helper to send standardized feedback echoing all metadata
        def send_zmq_feedback(msg, reply_type):
            if self.zmq_client:
                self.zmq_client.send_message({
                    "component": metadata.get("component", "3dviewer"),
                    "comp_phys": metadata.get("comp_phys", "3dviewer"),
                    "command": metadata.get("raw_command", "load_data"),
                    "arg1": metadata.get("arg1", ""),
                    "arg2": metadata.get("arg2", ""),
                    "reply": msg,
                    "reply type": reply_type,
                    "comp_type": metadata.get("comp_type", "other"),
                    "tick count": metadata.get("tick_count", 0),
                    "UUID": uuid,
                    "sender": "3dviewer"
                })

        # Progress callback to send FDB messages via ZMQ
        def zmq_progress_cb(msg):
            send_zmq_feedback(msg, "FDB")
        
        success = self.core.load_dataset(path, progress_callback=zmq_progress_cb)
        
        message = f"Successfully loaded from {path}" if success else f"Failed to load from {path}"
        
        # Send FINAL ACK
        send_zmq_feedback(message, "ACK" if success else "ERROR")
            
        self.on_zmq_command_received("load_data", success, message)

    def handle_zmq_set_tf(self, metadata: dict):
        """
        Slot to handle set_transfer_function on Main Thread.
        """
        name = metadata.get("name", "")
        slot = metadata.get("slot", 0)
        uuid = metadata.get("UUID", "")
            
        logging.info(f"ZMQ requested set_transfer_function: {name} (slot {slot})")
        
        def send_zmq_feedback(msg, reply_type):
            if self.zmq_client:
                self.zmq_client.send_message({
                    "component": metadata.get("component", "3dviewer"),
                    "comp_phys": metadata.get("comp_phys", "3dviewer"),
                    "command": metadata.get("raw_command", "set_transfer_function"),
                    "arg1": metadata.get("arg1", ""),
                    "arg2": metadata.get("arg2", ""),
                    "reply": msg,
                    "reply type": reply_type,
                    "comp_type": metadata.get("comp_type", "other"),
                    "tick count": metadata.get("tick_count", 0),
                    "UUID": uuid,
                    "sender": "3dviewer"
                })

        # Execute on Main Thread (GL context is valid here)
        success = False
        message = ""
        try:
            if name in self.core.tf_names:
                self.core.set_transfer_function(name, slot=slot)
                success = True
                target = "Overlay" if slot == 1 else "Primary"
                message = f"{target} transfer function set to {name}"
            else:
                success = False
                message = f"Unknown transfer function: {name}"
        except Exception as e:
            success = False
            message = f"Error setting TF: {str(e)}"
            
        # Send FINAL ACK
        send_zmq_feedback(message, "ACK" if success else "ERROR")
            
        self.on_zmq_command_received("set_transfer_function", success, message)

    def handle_zmq_exec_command(self, metadata: dict):
        """
        Slot to handle AI command execution from ZMQ thread on the Main Thread.
        """
        command_text = metadata.get("text", "")
        uuid = metadata.get("UUID", "")
            
        logging.info(f"ZMQ requested command: {command_text}")
        
        def send_zmq_feedback(msg, reply_type):
            if self.zmq_client:
                self.zmq_client.send_message({
                    "component": metadata.get("component", "3dviewer"),
                    "comp_phys": metadata.get("comp_phys", "3dviewer"),
                    "command": metadata.get("raw_command", command_text),
                    "arg1": metadata.get("arg1", ""),
                    "arg2": metadata.get("arg2", ""),
                    "reply": msg,
                    "reply type": reply_type,
                    "comp_type": metadata.get("comp_type", "other"),
                    "tick count": metadata.get("tick_count", 0),
                    "UUID": uuid,
                    "sender": "3dviewer"
                })

        # Immediate feedback that processing has started on main thread
        send_zmq_feedback("Executing AI command on main thread...", "FDB")

        success, message = self.core.execute_command_text(command_text)
        
        # Send FINAL ACK
        send_zmq_feedback(message, "ACK" if success else "ERROR")
            
        self.on_zmq_command_received(command_text, success, message)

    def on_zmq_command_received(self, command: str, success: bool, message: str):
        """
        Callback invoked when a ZMQ command is received and processed.
        (This is now primarily used for immediate logging).
        """
        # Log the command result
        logging.info(f"ZMQ Command '{command}': {'SUCCESS' if success else 'FAILED'} - {message}")
        
        # Trigger UI update (if called from main thread, this is direct; if not, we should've used signals)
        self._update_gui_after_zmq_command(command, success, message)
    
    def _update_gui_after_zmq_command(self, command: str, success: bool, message: str):
        """
        Update GUI elements after a ZMQ command (runs on main thread).
        
        Args:
            command: The command that was executed
            success: Whether the command succeeded
            message: Result message
        """
        # Update the command log to show ZMQ activity
        color = "#2ECC71" if success else "#E74C3C"
        self.cmd_log.append(f"<b style='color:#9B59B6'>ZMQ:</b> {command}")
        self.cmd_log.append(f"<b style='color:{color}'>Result:</b> {message}")
        
        # Auto-scroll the log
        self.cmd_log.verticalScrollBar().setValue(self.cmd_log.verticalScrollBar().maximum())
        
        # If it was a load_data command or any command that changes state, sync UI
        if success:
            if command == "load_data":
                # Update slider ranges for the newly loaded data
                vol_w, vol_h, vol_d = self.core.volume_renderer.volume_dims[0]
                if vol_w > 0:
                    for s, m in [(self.slider_x, vol_w), (self.slider_y, vol_h), (self.slider_z, vol_d)]:
                        s.setRange(0, m - 1)
                        s.setEnabled(True)
                    
                    self.slider_x.setValue(self.core.slice_indices[0])
                    self.slider_y.setValue(self.core.slice_indices[1])
                    self.slider_z.setValue(self.core.slice_indices[2])
                    
                    self.folder_label.setText("Loaded via ZMQ")
                    self.update_geometry_label()

                    # Initialize TF
                    self.core.set_transfer_function(self.core.current_tf_name)
            
            # For any successful command, sync UI and update views
            self.sync_ui_to_core()
            self.update_views()


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

    def on_import_advanced(self):
        diag = ImportDialog(self.core, self)
        if diag.exec():
            folder = diag.folder_path
            rescale_range = diag.rescale_range
            z_range = diag.z_range
            binning_factor = diag.binning_factor
            use_8bit = diag.use_8bit
            channel_index = diag.channel_index
            
            # Show progress dialog for potentially long operation
            progress = QProgressDialog("Initializing...", "Cancel", 0, 100, self)
            progress.setWindowTitle("Import Progress")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setAutoClose(True)
            progress.show()
            
            # Start loading thread
            self.load_thread = LoadVolumeThread(
                self.core.volume_loader, 
                folder, 
                rescale_range=rescale_range,
                z_range=z_range,
                binning_factor=binning_factor,
                use_8bit=use_8bit,
                channel_index=channel_index
            )
            self.load_thread.progress.connect(progress.setLabelText)
            self.load_thread.finished.connect(lambda data: self.on_volume_loaded_callback(data, folder, progress))
            self.load_thread.start()

    def on_volume_loaded_callback(self, data, folder_path, progress_dialog):
        progress_dialog.close()
        if data is not None:
            # Use AppCore to finalize initialization (GPU upload, state, camera)
            success = self.core.finalize_volume_load(data, folder_path)
            
            if success:
                # Update UI slider ranges based on new volume
                vol_w, vol_h, vol_d = self.core.volume_renderer.volume_dims[0]
                for s, m in [(self.slider_x, vol_w), (self.slider_y, vol_h), (self.slider_z, vol_d)]:
                    s.setRange(0, m - 1)
                    s.setEnabled(True)
                
                self.slider_x.setValue(self.core.slice_indices[0])
                self.slider_y.setValue(self.core.slice_indices[1])
                self.slider_z.setValue(self.core.slice_indices[2])
                
                self.folder_label.setText(f"Loaded: {os.path.basename(folder_path)}")
                self.update_geometry_label()
                self.update_views()
                logging.info(f"Volume loaded and initialized: {folder_path}")
            else:
                QMessageBox.critical(self, "Init Error", "Failed to initialize volume on GPU.")
        else:
            QMessageBox.critical(self, "Load Error", "Failed to load volume data.")

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

    def on_request_record_movie(self):
        """Records a 360-degree rotation movie of the 3D rendering."""
        if not self.core.volume_renderer.texture_ids:
            QMessageBox.warning(self, "Recording Error", "No volume data loaded.")
            return

        # 1. Ask for save path
        base_path = self.core.current_dataset_path or os.getcwd()
        movies_dir = os.path.join(base_path, "movies")
        try:
            os.makedirs(movies_dir, exist_ok=True)
        except:
            movies_dir = base_path
            
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested_path = os.path.join(movies_dir, f"rotation_360_{now}.mp4")
        
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save 360 Movie", suggested_path, "MP4 Video (*.mp4)"
        )
        
        if not save_path:
            return

        # 2. Setup Recording
        import imageio
        import numpy as np
        import glm

        num_frames = 120 # 4 seconds at 30 fps
        fps = 30
        
        progress = QProgressDialog("Recording 360° Movie...", "Cancel", 0, num_frames, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        # Save original orientation
        original_orientation = self.core.camera.orientation

        try:
            writer = imageio.get_writer(save_path, fps=fps, codec='libx264', quality=8)
            
            for i in range(num_frames):
                if progress.wasCanceled():
                    break
                
                progress.setValue(i)
                progress.setLabelText(f"Rendering frame {i+1}/{num_frames}...")
                
                # Calculate rotation angle (360 degrees over num_frames)
                angle_deg = (i / num_frames) * 360.0
                angle_rad = glm.radians(angle_deg)
                
                # Apply rotation around screen-vertical axis
                q_rot = glm.angleAxis(angle_rad, glm.vec3(0, 1, 0))
                self.core.camera.orientation = original_orientation * q_rot
                self.core.camera.update_camera_vectors()
                # Force High Quality Render (Disable interaction scaling)
                self.view_3d.is_interacting = False
                
                # Capture frame from the widget
                # grabFramebuffer() triggers a render internally.
                frame = self.view_3d.grabFramebuffer()
                
                # Create a black background image to blend onto.
                # This ensures semi-transparent "haze" is correctly darkened (as seen in the viewer)
                # and handles all color format conversions via Qt's QPainter.
                # We use Format_RGBA8888 because it has a predictable memory layout: R, G, B, A.
                blended = QImage(frame.size(), QImage.Format.Format_RGBA8888)
                blended.fill(Qt.GlobalColor.black)
                
                painter = QPainter(blended)
                painter.drawImage(0, 0, frame)
                painter.end()
                
                # Convert final blended image to numpy for imageio
                width = blended.width()
                height = blended.height()
                ptr = blended.bits()
                ptr.setsize(height * width * 4)
                arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
                
                # Extract RGB from the RGBA (R=0, G=1, B=2)
                actual_rgb = arr[:, :, :3]
                
                writer.append_data(actual_rgb)
                
            writer.close()
            progress.setValue(num_frames)
            
            if not progress.wasCanceled():
                QMessageBox.information(self, "Recording Complete", f"Movie saved to:\n{save_path}")
                logging.info(f"360 movie saved to {save_path}")
                
        except Exception as e:
            logging.error(f"Failed to record movie: {e}")
            QMessageBox.critical(self, "Recording Error", f"Could not record movie: {str(e)}")
        finally:
            # Restore original orientation
            self.core.camera.orientation = original_orientation
            self.core.camera.update_camera_vectors()
            self.view_3d.update()
            progress.close()

    def update_views(self):
        self.view_axial.update()
        self.view_coronal.update()
        self.view_sagittal.update()
        self.view_3d.update()

    def update_geometry_label(self):
        """Update the geometry info label with voxel size from loaded dataset."""
        voxel_size = self.core.geometry.get('voxel_size')
        if voxel_size:
            if voxel_size >= 1:
                text = f"Voxel: {voxel_size:.3f} mm"
            else:
                text = f"Voxel: {voxel_size * 1000:.1f} µm"

            # Add scanner info if available
            scanner = self.core.geometry.get('scanner_type')
            if scanner:
                text += f" | {scanner}"

            self.geometry_label.setText(text)
        else:
            self.geometry_label.setText("Voxel size: N/A (no settings file)")

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0D0D0D;
            }
            QWidget {
                background-color: #0D0D0D;
            }
            QScrollArea {
                background-color: #0D0D0D;
                border: none;
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
                background-color: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 5px;
                padding: 10px;
                margin-bottom: 5px;
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
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #2C3E50;
                color: white;
                selection-background-color: #3498DB;
                selection-color: white;
                border: 1px solid #3498DB;
            }
            QMenu {
                background-color: #2C3E50;
                color: white;
                border: 1px solid #3498DB;
            }
            QMenu::item {
                background-color: transparent;
                padding: 5px 25px 5px 20px;
            }
            QMenu::item:selected {
                background-color: #3498DB;
            }
            QMenu::separator {
                height: 1px;
                background: #555;
                margin: 5px 0px 5px 0px;
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
