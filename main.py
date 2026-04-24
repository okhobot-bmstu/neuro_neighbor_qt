import sys
import os
from PyQt6.QtWidgets import QApplication
from widgets.mainwindow import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Neuro_neighbor")

    # Безопасное определение пути к файлу стилей
    base_dir = os.path.dirname(os.path.abspath(__file__))
    style_path = os.path.join(base_dir, "styles", "style.qss")

    try:
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print(f"⚠️ Файл стилей не найден по пути: {style_path}")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
