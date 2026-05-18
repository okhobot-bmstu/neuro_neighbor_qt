import sys
import os
import json
import sounddevice as sd
from config.UI_class import Options, Headers

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLineEdit, QComboBox, QPushButton, QCheckBox, QFormLayout, QFileDialog
base_directory = os.getcwd()
CONFIG_PATH = "config/config.json"
TEMPLATE_PATH = "config/config_template.json"

with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
    test_config = json.load(f)

with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
    t1 = json.load(f)




class ConfigEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_path = CONFIG_PATH
        self.widgets = {}
        self.config_data = test_config

        self.setWindowTitle("Конфигуратор модели")
        self.resize(650, 720)

        root = QWidget(self)
        self.setCentralWidget(root)
        main = QVBoxLayout(root)

        for title, keys in Headers:
            box = QGroupBox(title)
            form = QFormLayout(box)
            for key in keys:
                form.addRow(Options[key][1], self._make_widget(key))
            main.addWidget(box)

        row = QHBoxLayout()
        for text, slot in (("Сохранить", self.save), ("Загрузить", self.load), ("Сброс", self.reset)):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            row.addWidget(btn)

        main.addLayout(row)
        self._apply(self.config_data)


    def _make_widget(self, key):
        kind = Options[key][0]

        if kind == "text":
            w = QLineEdit()
            if "token" in key:
                w.setEchoMode(QLineEdit.Password)

        elif kind == "check":
            w = QCheckBox()

        elif kind == "combo":
            _, _, items = Options[key]
            w = QComboBox()
            w.addItems(items)

        elif kind == "mic":
            pass
            w = QComboBox()
            w.addItem("Нету", -1)  
            for idx, dev in enumerate(sd.query_devices()):
                    if dev.get("max_input_channels", 0) > 0:
                        w.addItem(dev["name"], idx)

        elif kind == "dir":
            edit = QLineEdit()
            btn = QPushButton("Обзор...")
            btn.clicked.connect(self._browse_dir)

            wrap = QWidget()
            row = QHBoxLayout(wrap)
            row.addWidget(edit)
            row.addWidget(btn)

            self.widgets[key] = edit
            return wrap

        self.widgets[key] = w
        return w
    

    def save(self):
        try:
            self.config_data = self._collect()

            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, ensure_ascii=False)

            # print("Сохранено")

        except Exception as e:
            print(f"Ошибка сохранения: {e}")


    def load(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self.config_data = json.load(f)

            # print("Загружено")
            self._apply(self.config_data)

        except Exception as e:
            print(f"Ошибка загрузки: {e}")


    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Выберите директорию")
        if path:
            self.widgets["cache_dir"].setText(path) 
    

    def _get(self, cfg, path):
        for part in path.split("."):
            if not isinstance(cfg, dict) or part not in cfg:
                pass
            cfg = cfg[part]
        return cfg
    

    def _apply(self, cfg):
        for key, w in self.widgets.items():
            val = self._get(cfg, key)
            if val is None:
                continue

            if isinstance(w, QCheckBox):
                w.setChecked(bool(val))
            elif isinstance(w, QComboBox):
                if key == "stt.micro_index":
                    idx = w.findData(int(val))
                    w.setCurrentIndex(idx if idx >= 0 else 0)
                else:
                    idx = w.findText(str(val))
                    w.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                w.setText(str(val))


    def reset(self):
        self.config_data = t1 
        self._apply(self.config_data)


    def _set(self, cfg, path, value):
        parts = path.split(".")
        for part in parts[:-1]:
            cfg = cfg.setdefault(part, {})
        cfg[parts[-1]] = value


    def _collect(self):
        cfg = self.config_data
        for key, w in self.widgets.items():
            if isinstance(w, QCheckBox):
                val = w.isChecked()
            elif isinstance(w, QComboBox):
                val = w.currentData() if key == "stt.micro_index" else w.currentText()
            else:
                val = w.text()

            if key in {
                "model.max_console_op_depth",
                "model.load_embeddings_count",
                "model.chat_size",
                "tts.pitch_shift",
                "stt.micro_index",
                "stt.silence_duration",
            }:
                val = self._to_int(val, self._get(self.config_data, key) or 0)

            self._set(cfg, key, val)
        return cfg

    def _to_int(self, text, silly=0):
        try:
            return int(str(text).strip())
        except Exception:
            return silly

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ConfigEditor()
    win.show()
    sys.exit(app.exec())