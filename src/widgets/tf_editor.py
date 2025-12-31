import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient

class TFEditorWidget(QWidget):
    """
    A widget for editing the transparency (alpha) ramp of a transfer function.
    Displays a colormap background and a draggable opacity curve.
    """
    pointsChanged = pyqtSignal(list) # Emits list of (pos, alpha) tuples

    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.setMinimumHeight(200)
        self.setMinimumWidth(250)
        
        # Initial points from core
        self.points = [list(p) for p in self.core.alpha_points]
        self.selected_point_idx = None
        self.point_radius = 6
        
        self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()

        # 1. Draw Background Colormap
        # We'll use a gradient that approximates the current colormap
        gradient = QLinearGradient(0, 0, w, 0)
        
        # Sample the colormap at a few points
        from transfer_functions import get_colormap
        tf_data = get_colormap(self.core.current_tf_name, size=10) # low res for gradient is fine
        for i in range(len(tf_data)):
            pos = i / (len(tf_data) - 1)
            r, g, b, _ = tf_data[i]
            gradient.setColorAt(pos, QColor(int(r*255), int(g*255), int(b*255)))
        
        painter.fillRect(self.rect(), gradient)
        
        # 2. Draw opacity curve
        pen = QPen(QColor(255, 255, 255), 2)
        painter.setPen(pen)
        
        path_points = []
        for p in self.points:
            px = p[0] * w
            py = (1.0 - p[1]) * h # Invert Y for UI
            path_points.append(QPointF(px, py))
            
        for i in range(len(path_points) - 1):
            painter.drawLine(path_points[i], path_points[i+1])
            
        # 3. Draw points
        for i, pt in enumerate(path_points):
            if i == self.selected_point_idx:
                painter.setBrush(QBrush(QColor(255, 0, 0)))
            else:
                painter.setBrush(QBrush(QColor(255, 255, 255)))
            
            painter.drawEllipse(pt, self.point_radius, self.point_radius)

    def mousePressEvent(self, event):
        pos = event.position()
        w, h = self.width(), self.height()
        
        # Check if clicking near a point
        self.selected_point_idx = None
        for i, p in enumerate(self.points):
            px = p[0] * w
            py = (1.0 - p[1]) * h
            if (pos.x() - px)**2 + (pos.y() - py)**2 < (self.point_radius * 2)**2:
                self.selected_point_idx = i
                break
        
        # If right click, delete point (if not endpoints)
        if event.button() == Qt.MouseButton.RightButton:
            if self.selected_point_idx is not None and 0 < self.selected_point_idx < len(self.points) - 1:
                self.points.pop(self.selected_point_idx)
                self.selected_point_idx = None
                self.update_and_emit()
            elif self.selected_point_idx is None:
                # Add a new point
                new_p = [pos.x() / w, 1.0 - pos.y() / h]
                self.points.append(new_p)
                self.points.sort(key=lambda x: x[0])
                self.update_and_emit()
        
        self.update()

    def mouseMoveEvent(self, event):
        if self.selected_point_idx is not None and event.buttons() & Qt.MouseButton.LeftButton:
            pos = event.position()
            w, h = self.width(), self.height()
            
            # Clamp values
            nx = np.clip(pos.x() / w, 0.0, 1.0)
            ny = np.clip(1.0 - pos.y() / h, 0.0, 1.0)
            
            # Don't allow X-overlap or moving endpoints past boundaries
            if self.selected_point_idx == 0:
                nx = 0.0
            elif self.selected_point_idx == len(self.points) - 1:
                nx = 1.0
            else:
                # Keep order
                prev_x = self.points[self.selected_point_idx - 1][0]
                next_x = self.points[self.selected_point_idx + 1][0]
                nx = np.clip(nx, prev_x + 0.01, next_x - 0.01)
            
            self.points[self.selected_point_idx] = [nx, ny]
            self.update_and_emit()
            self.update()

    def update_and_emit(self):
        # Convert to tuples for the signal
        pts = [tuple(p) for p in self.points]
        self.pointsChanged.emit(pts)

    def set_points(self, points):
        self.points = [list(p) for p in points]
        self.update()
