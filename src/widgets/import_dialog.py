import os
import numpy as np
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFileDialog, QSlider, QFrame, QSizePolicy,
                             QComboBox, QCheckBox, QSpinBox, QGridLayout, QProgressDialog,
                             QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPoint, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QImage, QPixmap
import psutil

class HistogramWidget(QFrame):
    """
    Displays a histogram and allows selecting a range with two draggable vertical bars.
    """
    rangeChanged = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setMinimumWidth(400)
        self.setStyleSheet("background-color: #111; border: 1px solid #444;")
        
        self.hist_data = None
        self.lower_val = 0
        self.upper_val = 65535
        self.max_val = 65535
        
        self.dragging = None # 'lower' or 'upper'
        self.setMouseTracking(True)

    def set_data(self, hist, bin_edges):
        self.hist_data = hist
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        padding = 10
        
        draw_w = w - 2 * padding
        draw_h = h - 2 * padding
        
        # Draw Histogram
        if self.hist_data is not None and len(self.hist_data) > 0:
            max_h = np.max(self.hist_data)
            if max_h == 0: max_h = 1
            
            bar_w = draw_w / len(self.hist_data)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(52, 152, 219, 150))) # Blue-ish semi-transparent
            
            for i, val in enumerate(self.hist_data):
                bar_h = (val / max_h) * draw_h
                x = padding + i * bar_w
                y = h - padding - bar_h
                painter.drawRect(QRect(int(x), int(y), int(bar_w) + 1, int(bar_h)))

        # Draw Range Overlay
        # Mask out-of-range areas
        painter.setBrush(QBrush(QColor(0, 0, 0, 100)))
        x_low = padding + (self.lower_val / self.max_val) * draw_w
        x_high = padding + (self.upper_val / self.max_val) * draw_w
        
        painter.drawRect(QRect(padding, padding, int(x_low - padding), draw_h))
        painter.drawRect(QRect(int(x_high), padding, int(w - padding - x_high), draw_h))

        # Draw handles
        pen_handle = QPen(QColor(231, 76, 60), 2) # Redish
        painter.setPen(pen_handle)
        painter.drawLine(int(x_low), padding, int(x_low), h - padding)
        painter.drawLine(int(x_high), padding, int(x_high), h - padding)
        
        # Draw handle labels
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(int(x_low) - 10, h - 2, f"{self.lower_val}")
        painter.drawText(int(x_high) - 10, h - 2, f"{self.upper_val}")

    def mousePressEvent(self, event):
        pos = event.position().x()
        padding = 10
        draw_w = self.width() - 2 * padding
        
        x_low = padding + (self.lower_val / self.max_val) * draw_w
        x_high = padding + (self.upper_val / self.max_val) * draw_w
        
        if abs(pos - x_low) < 10:
            self.dragging = 'lower'
        elif abs(pos - x_high) < 10:
            self.dragging = 'upper'
        else:
            self.dragging = None

    def mouseMoveEvent(self, event):
        if self.dragging:
            pos = event.position().x()
            padding = 10
            draw_w = self.width() - 2 * padding
            
            val = int(((pos - padding) / draw_w) * self.max_val)
            val = max(0, min(val, self.max_val))
            
            if self.dragging == 'lower':
                self.lower_val = min(val, self.upper_val - 1)
            else:
                self.upper_val = max(val, self.lower_val + 1)
            
            self.rangeChanged.emit(self.lower_val, self.upper_val)
            self.update()
        else:
            # Change cursor if hovering over handles
            pos = event.position().x()
            padding = 10
            draw_w = self.width() - 2 * padding
            x_low = padding + (self.lower_val / self.max_val) * draw_w
            x_high = padding + (self.upper_val / self.max_val) * draw_w
            
            if abs(pos - x_low) < 10 or abs(pos - x_high) < 10:
                self.setCursor(Qt.CursorShape.SplitHCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self.dragging = None

class ImportDialog(QDialog):
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle("Import 3D Volume with Rescaling")
        self.resize(1000, 600)
        
        self.folder_path = None
        self.is_hdf5 = False
        self.stats = None
        self.rescale_range = (0, 65535)
        self.z_range = (0, 0)
        self.binning_factor = 1
        self.use_8bit = False
        self.channel_index = 0
        
        self.setup_ui()
        self.apply_style()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. Folder Selection
        top_row = QHBoxLayout()
        self.path_label = QLabel("No folder/file selected")
        btn_browse_folder = QPushButton("Select Folder...")
        btn_browse_folder.clicked.connect(self.on_browse_folder)
        btn_browse_file = QPushButton("Select H5 File...")
        btn_browse_file.clicked.connect(self.on_browse_file)
        top_row.addWidget(self.path_label, 1)
        top_row.addWidget(btn_browse_folder)
        top_row.addWidget(btn_browse_file)
        layout.addWidget(self.create_group_frame(top_row, "Source Data"))
        
        # 2. Main Area (Preview + Histogram)
        center_row = QHBoxLayout()
        
        # Preview Column
        preview_vbox = QVBoxLayout()
        title_preview = QLabel("SLICE PREVIEW")
        title_preview.setStyleSheet("font-weight: bold; color: #FFF;")
        preview_vbox.addWidget(title_preview)
        
        self.preview_label = QLabel("Select a folder to see preview")
        self.preview_label.setFixedSize(400, 400)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #000; border: 1px solid #555;")
        preview_vbox.addWidget(self.preview_label)
        
        self.slice_slider = QSlider(Qt.Orientation.Horizontal)
        self.slice_slider.setEnabled(False)
        self.slice_slider.valueChanged.connect(self.update_preview)
        preview_vbox.addWidget(self.slice_slider)
        center_row.addLayout(preview_vbox)
        
        # Histogram and Configuration Column
        config_vbox = QVBoxLayout()
        
        # Intensity Range
        config_vbox.addWidget(QLabel("Intensity Distribution (Rescaling Range)"))
        self.hist_widget = HistogramWidget()
        self.hist_widget.rangeChanged.connect(self.on_range_changed)
        config_vbox.addWidget(self.hist_widget)
        
        self.range_info = QLabel("Selected Range: [0, 65535] -> [0, 65535]")
        self.range_info.setStyleSheet("font-weight: bold; color: #3498DB;")
        config_vbox.addWidget(self.range_info)
        
        # Data Reduction Options
        reduction_group = QFrame()
        reduction_group.setStyleSheet("background-color: #222; border-radius: 4px; padding: 5px;")
        reduction_layout = QGridLayout(reduction_group)
        reduction_layout.addWidget(QLabel("DATA REDUCTION OPTIONS"), 0, 0, 1, 3)
        
        # Z-Range
        reduction_layout.addWidget(QLabel("Slice Range (Z):"), 1, 0)
        self.spin_z_start = QSpinBox()
        self.spin_z_end = QSpinBox()
        self.spin_z_start.valueChanged.connect(self.on_reduction_changed)
        self.spin_z_end.valueChanged.connect(self.on_reduction_changed)
        reduction_layout.addWidget(self.spin_z_start, 1, 1)
        reduction_layout.addWidget(self.spin_z_end, 1, 2)
        
        # Binning
        reduction_layout.addWidget(QLabel("Spatial Binning:"), 2, 0)
        self.combo_binning = QComboBox()
        self.combo_binning.addItems(["None (1x1x1)", "2x2x2", "4x4x4"])
        self.combo_binning.currentIndexChanged.connect(self.on_reduction_changed)
        reduction_layout.addWidget(self.combo_binning, 2, 1, 1, 2)
        
        # Channel Selection (for HDF5)
        self.label_channel = QLabel("Energy Channel:")
        self.combo_channel = QComboBox()
        self.label_channel.hide()
        self.combo_channel.hide()
        self.combo_channel.currentIndexChanged.connect(self.on_channel_changed)
        reduction_layout.addWidget(self.label_channel, 3, 0)
        reduction_layout.addWidget(self.combo_channel, 3, 1, 1, 2)
        
        # 8-bit mode
        self.chk_8bit = QCheckBox("Import as 8-bit (halves memory usage)")
        self.chk_8bit.toggled.connect(self.on_reduction_changed)
        reduction_layout.addWidget(self.chk_8bit, 4, 0, 1, 3)
        
        config_vbox.addWidget(reduction_group)
        
        # Memory Information
        mem_group = QFrame()
        mem_group.setStyleSheet("background-color: #1a2a33; border: 1px solid #34495e; border-radius: 4px; padding: 10px;")
        mem_layout = QVBoxLayout(mem_group)
        self.mem_info_label = QLabel("Memory: Ready to estimate...")
        self.mem_info_label.setStyleSheet("font-size: 13px; color: #ecf0f1; font-family: 'Consolas', 'Monaco', monospace;")
        mem_layout.addWidget(self.mem_info_label)
        self.mem_status_label = QLabel("Status: Waiting for input")
        self.mem_status_label.setStyleSheet("font-weight: bold; color: #95a5a6;")
        mem_layout.addWidget(self.mem_status_label)
        
        config_vbox.addWidget(mem_group)
        config_vbox.addStretch()
        
        center_row.addLayout(config_vbox, 1)
        layout.addLayout(center_row)
        
        # 3. Actions
        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        
        self.btn_import = QPushButton("Import & Rescale")
        self.btn_import.setObjectName("PrimaryButton")
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self.accept)
        
        btns.addWidget(btn_cancel)
        btns.addWidget(self.btn_import)
        layout.addLayout(btns)

    def create_group_frame(self, inner_layout, title):
        frame = QFrame()
        vbox = QVBoxLayout(frame)
        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet("font-size: 10px; color: #888; margin-bottom: 2px;")
        vbox.addWidget(title_lbl)
        vbox.addLayout(inner_layout)
        return frame

    def on_browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Volume Folder")
        if path:
            self.folder_path = path
            self.is_hdf5 = False
            self.path_label.setText(path)
            self.load_metadata()

    def on_browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select HDF5 Volume", "", "HDF5 Files (*.h5 *.hdf5);;All Files (*)")
        if path:
            self.folder_path = path
            self.is_hdf5 = True
            self.path_label.setText(path)
            self.load_metadata()

    def load_metadata(self):
        if self.is_hdf5:
            self.stats = self.core.volume_loader.get_h5_quick_stats(self.folder_path, self.channel_index)
        else:
            self.stats = self.core.volume_loader.get_quick_stats(self.folder_path)

        if self.stats:
            self.hist_widget.set_data(self.stats['histogram'], self.stats['bin_edges'])
            
            # Setup channel selection for HDF5
            if self.is_hdf5 and self.stats.get('num_channels', 1) > 1:
                self.label_channel.show()
                self.combo_channel.show()
                if self.combo_channel.count() == 0:
                    for i in range(self.stats['num_channels']):
                        self.combo_channel.addItem(f"Channel {i}")
            else:
                self.label_channel.hide()
                self.combo_channel.hide()
            
            # Setup reduction controls
            self.spin_z_start.setRange(0, self.stats['depth'] - 1)
            self.spin_z_end.setRange(0, self.stats['depth'])
            self.spin_z_start.setValue(0)
            self.spin_z_end.setValue(self.stats['depth'])
            
            self.slice_slider.setRange(0, self.stats['depth'] - 1)
            self.slice_slider.setValue(self.stats['depth'] // 2)
            self.slice_slider.setEnabled(True)
            
            # Suggest a range if possible
            self.hist_widget.lower_val = int(self.stats['min'])
            self.hist_widget.upper_val = int(self.stats['max'])
            self.on_range_changed(self.hist_widget.lower_val, self.hist_widget.upper_val)
            
            self.update_memory_info()
            self.update_preview()
        else:
            if self.is_hdf5:
                self.path_label.setText("Error: Failed to read HDF5 metadata.")
            else:
                self.path_label.setText("Error: No TIFF files found in folder.")
            self.btn_import.setEnabled(False)

    def on_range_changed(self, lower, upper):
        self.rescale_range = (lower, upper)
        self.range_info.setText(f"Selected Range: [{lower}, {upper}] -> [0, 65535]")
        self.update_preview()

    def on_reduction_changed(self, _=None):
        self.update_memory_info()
        self.update_preview()

    def on_channel_changed(self, index):
        self.channel_index = index
        self.load_metadata() # Refresh stats and histogram for new channel
        self.update_preview()

    def update_memory_info(self):
        if not self.stats: return
        
        # Get current settings
        z0 = self.spin_z_start.value()
        z1 = self.spin_z_end.value()
        self.z_range = (z0, z1)
        
        bin_idx = self.combo_binning.currentIndex()
        self.binning_factor = [1, 2, 4][bin_idx]
        self.use_8bit = self.chk_8bit.isChecked()
        
        # Calculate reduced dimensions
        orig_w = self.stats['width']
        orig_h = self.stats['height']
        orig_d = self.stats['depth']
        
        cur_d = max(0, z1 - z0)
        cur_w = orig_w // self.binning_factor
        cur_h = orig_h // self.binning_factor
        cur_d = cur_d // self.binning_factor
        
        # Estimate memory
        is_safe, estimated, available = self.core.volume_loader.check_memory_available(
            cur_w, cur_h, cur_d, self.use_8bit
        )
        
        # Update labels
        info_text = (
            f"Original: {orig_w}x{orig_h}x{orig_d} ({orig_w*orig_h*orig_d/1e9:.1f}B voxels)\n"
            f"Reduced:  {cur_w}x{cur_h}x{cur_d} ({cur_w*cur_h*cur_d/1e6:.1f}M voxels)\n"
            f"Estimated Load: {estimated/1e9:.2f} GB\n"
            f"Free System RAM: {available/1e9:.2f} GB"
        )
        self.mem_info_label.setText(info_text)
        
        # Check Hardware Limits
        max_limit = self.core.volume_renderer.max_texture_size
        hw_warning = ""
        if cur_w > max_limit or cur_h > max_limit or cur_d > max_limit:
            hw_warning = f"\n⚠️ OVER GPU LIMIT ({max_limit})"
            is_safe = False
            
        if is_safe:
            self.mem_status_label.setText(f"Status: ✅ Safe to load{hw_warning}")
            self.mem_status_label.setStyleSheet("color: #2ecc71; font-weight: bold;")
            self.btn_import.setEnabled(True)
        else:
            if hw_warning:
                 self.mem_status_label.setText(f"Status: ❌ Hardware Limit{hw_warning}")
            else:
                 self.mem_status_label.setText(f"Status: ❌ Critical: Memory Insufficient")
            self.mem_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.btn_import.setEnabled(False)

    def update_preview(self):
        if not self.stats: return

        if self.is_hdf5:
            import h5py
            try:
                with h5py.File(self.folder_path, 'r') as f:
                    ds = f['reconstruction']
                    idx = self.slice_slider.value()
                    if len(ds.shape) == 4:
                        img_data = ds[idx, :, :, self.channel_index]
                    else:
                        img_data = ds[idx, :, :]
                    
                    # Apply rescaling for the preview
                    lower, upper = self.rescale_range
                    img_f = img_data.astype(np.float32)
                    img_f = (img_f - lower) * 255.0 / (upper - lower)
                    img_f = np.clip(img_f, 0, 255).astype(np.uint8)
                    
                    h, w = img_f.shape
                    bytes_per_line = w
                    q_img = QImage(img_f.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
                    pixmap = QPixmap.fromImage(q_img)
                    self.preview_label.setPixmap(pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio))
            except Exception as e:
                print(f"H5 Preview error: {e}")
        else:
            # Original TIFF preview logic
            import tifffile
            files = sorted([f for f in os.listdir(self.folder_path) if f.lower().endswith(('.tif', '.tiff'))])
            idx = self.slice_slider.value()
            try:
                img_data = tifffile.imread(os.path.join(self.folder_path, files[idx]))
                
                # Apply rescaling for the preview too!
                lower, upper = self.rescale_range
                img_f = img_data.astype(np.float32)
                img_f = (img_f - lower) * 255.0 / (upper - lower)
                img_f = np.clip(img_f, 0, 255).astype(np.uint8)
                
                h, w = img_f.shape
                bytes_per_line = w
                q_img = QImage(img_f.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
                pixmap = QPixmap.fromImage(q_img)
                self.preview_label.setPixmap(pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio))
            except Exception as e:
                print(f"Preview error: {e}")

    def apply_style(self):
        self.setStyleSheet("""
            QDialog { background-color: #1A1A1A; color: white; }
            QLabel { color: #DDD; }
            QPushButton { background-color: #333; color: white; border-radius: 4px; padding: 8px 15px; border: 1px solid #444; }
            QPushButton:hover { background-color: #444; }
            QPushButton:disabled { color: #666; background-color: #222; }
            #PrimaryButton { background-color: #E74C3C; font-weight: bold; border-color: #C0392B; }
            #PrimaryButton:hover { background-color: #C0392B; }
            QComboBox { background-color: #2C3E50; color: white; border: 1px solid #3498DB; padding: 5px; border-radius: 3px; }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 6px solid white; width: 0; height: 0; margin-right: 6px; }
            QComboBox QAbstractItemView { background-color: #2C3E50; color: white; selection-background-color: #3498DB; selection-color: white; border: 1px solid #3498DB; }
            QSpinBox { background-color: #2C3E50; color: white; border: 1px solid #3498DB; padding: 3px; border-radius: 3px; }
            QCheckBox { color: white; spacing: 5px; }
            QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #555; border-radius: 3px; background-color: #2C3E50; }
            QCheckBox::indicator:checked { background-color: #3498DB; border-color: #3498DB; }
        """)
