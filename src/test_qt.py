from PyQt6.QtWidgets import QApplication, QLabel
import sys

try:
    app = QApplication(sys.argv)
    label = QLabel("Hello PyQt6")
    label.show()
    print("PyQt6 initialized successfully")
    # QTimer.singleShot(1000, app.quit) # Optional: Quit after 1 sec
except Exception as e:
    print(f"Error: {e}")
