import sys
import os
import json

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
)

CONFIG_PATH = "config/config.json"


class Settings(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Config Test")
        self.resize(600, 450)

        # self.config_data

        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)

        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.save)

        load_btn = QPushButton("Загрузить")
        load_btn.clicked.connect(self.load)

        layout.addWidget(save_btn)
        layout.addWidget(load_btn)

        self.setLayout(layout)

    def save(self):
        try:
            self.config_data = "new"

            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, ensure_ascii=False)

            print("Сохранено")

        except Exception as e:
            print(f"Ошибка сохранения: {e}")

    def load(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self.config_data = json.load(f)

            print("Загружено")
            print(self.config_data)

        except Exception as e:
            print(f"Ошибка загрузки: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = Settings()
    window.show()

    sys.exit(app.exec())