import sys
import os
from PyQt6.QtWidgets import QApplication
from widgets.mainwindow import MainWindow

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
ai_path = os.path.join(PROJECT_ROOT, "ai_nn")
if ai_path not in sys.path:
        sys.path.insert(0, ai_path)

def init_ai_engine():
    try:
        # Импортируем класс после исправления импортов в ai_nn.py
        from ai_nn import Ai_NN

        config_path = os.path.join(PROJECT_ROOT, "config", "config.json")
        print(f"📦 Инициализация AI (конфиг: {config_path})...")

        engine = Ai_NN(path_to_config=config_path)

        if not (hasattr(engine, 'start_recognition') and hasattr(engine, 'stop_recognition')):
            print("⚠️ Методы управления микрофоном не найдены")
            return None
        return engine
    except Exception as e:
        print(f"⚠️ Ошибка инициализации AI: {e}")
        return None

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Neuro_neighbor")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    style_path = os.path.join(base_dir, "styles", "style.qss")

    try:
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print(f"⚠️ Стили не найдены: {style_path}")

    ai_engine = init_ai_engine()
    if ai_engine:
        print("✅ AI-модуль готов к работе")
    else:
        print("⚠️ Запуск в UI-режиме (без AI)")

    window = MainWindow(ai_engine=ai_engine)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
