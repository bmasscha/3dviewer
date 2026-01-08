import os
import numpy as np
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFileDialog, QSlider, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPoint, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QImage, QPixmap

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
        self.stats = None
        self.rescale_range = (0, 65535)
        
        self.setup_ui()
        self.apply_style()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Top: Folder Selection
        top_row = QHBoxLayout()
        self.path_label = QLabel("No folder selected")
        btn_browse = QPushButton("Select Folder...")
        btn_browse.clicked.connect(self.on_browse)
        top_row.addWidget(self.path_label, 1)
        top_row.addWidget(btn_browse)
        layout.addLayout(top_row)
        
        # Center: Preview and Histogram
        center_row = QHBoxLayout()
        
        # Left: Preview
        preview_vbox = QVBoxLayout()
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
        
        # Right: Histogram
        hist_vbox = QVBoxLayout()
        hist_vbox.addWidget(QLabel("Intensity Distribution (Rescaling Range)"))
        self.hist_widget = HistogramWidget()
        self.hist_widget.rangeChanged.connect(self.on_range_changed)
        hist_vbox.addWidget(self.hist_widget)
        
        self.range_info = QLabel("Selected Range: [0, 65535] -> [0, 65535]")
        self.range_info.setStyleSheet("font-weight: bold; color: #3498DB;")
        hist_vbox.addWidget(self.range_info)
        
        center_row.addLayout(hist_vbox, 1)
        layout.addLayout(center_row)
        
        # Bottom: Actions
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

    def on_browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select Volume Folder")
        if path:
            self.folder_path = path
            self.path_label.setText(path)
            self.load_metadata()

    def load_metadata(self):
        # Quick scan to get histogram and dimensions
        self.stats = self.core.volume_loader.get_quick_stats(self.folder_path)
        if self.stats:
            self.hist_widget.set_data(self.stats['histogram'], self.stats['bin_edges'])
            self.slice_slider.setRange(0, self.stats['depth'] - 1)
            self.slice_slider.setValue(self.stats['depth'] // 2)
            self.slice_slider.setEnabled(True)
            self.btn_import.setEnabled(True)
            
            # Suggest a range if possible (e.g. min/max of samples)
            self.hist_widget.lower_val = int(self.stats['min'])
            self.hist_widget.upper_val = int(self.stats['max'])
            self.on_range_changed(self.hist_widget.lower_val, self.hist_widget.upper_val)
            self.update_preview()
        else:
            self.path_label.setText("Error: No TIFF files found in folder.")
            self.btn_import.setEnabled(False)

    def on_range_changed(self, lower, upper):
        self.rescale_range = (lower, upper)
        self.range_info.setText(f"Selected Range: [{lower}, {upper}] -> [0, 65535]")
        self.update_preview()

    def update_preview(self):
        if not self.stats: return
        
        # We could load the specific slice for preview, but let's stick to the middle one if many slices
        # to keep it snappy. Actually, let's just let the user scroll through the sample slices or 
        # load specific ones if they change the slider.
        # For now, let's just use the middle slice or first/last.
        
        # Actually, let's implement a simple slice loader for preview
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
        """)
