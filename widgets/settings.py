import sys
import os
import json
import sounddevice as sd
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGroupBox, QLineEdit, QComboBox,
                             QPushButton, QCheckBox, QFormLayout, QFileDialog,
                             QScrollArea)

Options = {
    "cache_dir": ("dir", "Кэш"),
    "hf_token": ("text", "HF Token"),
    "offline": ("check", "Офлайн режим"),

    "model.repo_id": ("text", "Repo ID"),
    "model.filename": ("text", "Filename"),
    "model.init_prompt_path": ("dir", "Init Prompt Path"),  
    "model.chat_history_path": ("dir", "Chat History Path"), 
    "model.init_prompt_role": ("combo", "Init Prompt Role", ["user", "system", "assistant"]),
    "model.max_console_op_depth": ("text", "Max Depth"),
    "model.load_embeddings_count": ("text", "Embeddings"),
    "model.chat_size": ("text", "Chat Size"),
    "model.use_gpu": ("check", "Use GPU"),

    "tts.pitch_shift": ("text", "Pitch Shift"),
    "tts.speaker_name": ("text", "Speaker"),
    "tts.model_name": ("text", "Model Name"),

    "stt.model": ("combo", "Model", ["tiny", "base", "small", "medium", "large"]),
    "stt.device": ("combo", "Device", ["cpu", "cuda"]),
    "stt.use_nr": ("check", "Use NR"),
    "stt.micro_index": ("mic", "Microphone"),
    "stt.silence_duration": ("text", "Silence Duration"),
}

Headers = [
    ("Основные", ["cache_dir", "hf_token", "offline"]),
    ("Модель", [
        "model.repo_id", "model.filename", "model.init_prompt_path",
        "model.chat_history_path", "model.init_prompt_role",
        "model.max_console_op_depth", "model.load_embeddings_count",
        "model.chat_size", "model.use_gpu",
    ]),
    ("TTS", ["tts.pitch_shift", "tts.speaker_name", "tts.model_name"]),
    ("STT", ["stt.model", "stt.device", "stt.use_nr", "stt.silence_duration", "stt.micro_index"]),
]
CONFIG_PATH = "config/config.json"
TEMPLATE_PATH = "config/config_template.json"


with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
    test_config = json.load(f)


class ConfigEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_path = CONFIG_PATH
        self.widgets = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config_data = json.load(f)
            except Exception as e:
                print(f"Ошибка чтения config.json: {e}. Загружен шаблон.")
                self.config_data = test_config
        else:
            self.config_data = test_config

        self.setWindowTitle("Конфигуратор модели")
        self.resize(650, 720)

        root = QWidget(self)
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        reset_btn = QPushButton("Перезапустить")
        reset_btn.clicked.connect(self.reset_model)
        scroll_layout.addWidget(reset_btn)

        for title, keys in Headers:
            box = QGroupBox(title)
            form = QFormLayout(box)
            for key in keys:
                if key == "tts.pitch_shift":
                    reset_chat_btn = QPushButton("Очистить чат")
                    reset_chat_btn.clicked.connect(self.reset_chat)
                    scroll_layout.addWidget(reset_chat_btn)
                form.addRow(Options[key][1], self._make_widget(key))
            scroll_layout.addWidget(box)

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        row = QHBoxLayout()
        for text, slot in (("Сохранить", self.save), ("Загрузить", self.load), ("Сброс", self.reset)):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        main_layout.addLayout(row)

        self._apply(self.config_data)

    def reset_chat(self):
        print("очистить чат")

    def reset_model(self):
        print("перезапуск")

    def _make_widget(self, key):
        kind = Options[key][0]

        if kind == "text":
            w = QLineEdit()
            if "token" in key:
                w.setEchoMode(QLineEdit.EchoMode.Password)

        elif kind == "check":
            w = QCheckBox()

        elif kind == "combo":
            _, _, items = Options[key]
            w = QComboBox()
            w.addItems(items)

        elif kind == "mic":
            w = QComboBox()
            w.addItem("Нету", -1)
            for idx, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    w.addItem(dev["name"], idx)

        elif kind == "dir":
            edit = QLineEdit()
            btn = QPushButton("Обзор...")
            additional = Options[key][1]
            if additional == "Кэш":
                btn.clicked.connect(lambda: self._browse_dir(0))
            elif additional == "Init Prompt Path":
                btn.clicked.connect(lambda: self._browse_dir(1))
            else:
                btn.clicked.connect(lambda: self._browse_dir(2))

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
        except Exception as e:
            print(f"Ошибка сохранения: {e}")

    def load(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self.config_data = json.load(f)
            self._apply(self.config_data)
        except Exception as e:
            print(f"Ошибка загрузки: {e}")

    def _browse_dir(self, ind):
        vars = ["cache_dir", "model.init_prompt_path", "model.chat_history_path"]
        path = QFileDialog.getExistingDirectory(self, "Выберите директорию")
        if path:
            self.widgets[vars[ind]].setText(path)

    def _get(self, cfg, path):
        for part in path.split("."):
            if not isinstance(cfg, dict) or part not in cfg:
                return None
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
        self.config_data = test_config
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