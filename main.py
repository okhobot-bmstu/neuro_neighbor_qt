import sys
import json
import warnings
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from widgets.mainwindow import MainWindow

warnings.filterwarnings("ignore", category=RuntimeWarning, module="noisereduce")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="numpy")

PROJECT_ROOT = Path(__file__).resolve().parent

# Инициализация AI-движка: загрузка конфига, проверка методов, обработка ошибок импорта
def init_ai_engine():
    try:
        from ai_nn import Ai_NN

        config_path = PROJECT_ROOT / "config" / "config.json"
        print(f"📦 Инициализация AI (конфиг: {config_path})...")

        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)

        engine = Ai_NN(json_config=config_dict)

        if not (hasattr(engine, 'start_recognition') and hasattr(engine, 'stop_recognition')):
            print("⚠️ Методы управления микрофоном не найдены")
            return None
        return engine
    except json.JSONDecodeError as e:
        print(f"⚠️ Ошибка парсинга config.json: {e}")
        return None
    except ImportError as e:
        print(f"️ Пакет ai_nn не найден. Установите в editable-режиме:\n   pip install -e ai_nn --no-deps\n   Ошибка: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Ошибка инициализации AI: {e}")
        return None

# Точка входа приложения: настройка Qt, загрузка стилей, инициализация AI и запуск UI
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Neuro_neighbor")

    style_path = PROJECT_ROOT / "styles" / "style.qss"

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

    window = MainWindow(ai_engine=ai_engine, project_root=PROJECT_ROOT)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
