import sys
import os
import json
from pathlib import Path
import sounddevice as sd
from config.UI_class import Options, Headers

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLineEdit, QComboBox, QPushButton, QCheckBox, QFormLayout, QFileDialog, QMessageBox
)


class ConfigEditor(QMainWindow):
    def __init__(self, project_root: Path = None, parent = None):
        super().__init__(parent)
        self.project_root = project_root or Path(__file__).resolve().parent.parent
        self.config_path = self.project_root / "config" / "config.json"
        self.template_path = self.project_root / "config" / "config_template.json"
        self.widgets = {}

        # Загрузка шаблона по умолчанию
        try:
            with open(self.template_path, "r", encoding="utf-8") as f:
                self.default_config = json.load(f)
        except Exception as e:
            print(f"⚠️ Не удалось загрузить шаблон: {e}")
            self.default_config = {}

        # Загрузка пользовательского конфига или фоллбэк на шаблон
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config_data = json.load(f)

                def deep_merge(base, update):
                    for k, v in update.items():
                        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                            deep_merge(base[k], v)
                        elif k not in base:
                            base[k] = v
                    return base

                self.config_data = deep_merge(self.config_data, self.default_config)
            except Exception as e:
                print(f"⚠️ Не удалось загрузить config.json: {e}")
                self.config_data = self.default_config.copy()
        else:
            self.config_data = self.default_config.copy()

        self.setWindowTitle("Конфигуратор модели")
        self.resize(650, 720)

        root = QWidget(self)
        self.setCentralWidget(root)
        main = QVBoxLayout(root)

        reset_btn = QPushButton("Перезапустить")
        reset_btn.clicked.connect(self.reset_model)
        main.addWidget(reset_btn)

        for title, keys in Headers:
            box = QGroupBox(title)
            form = QFormLayout(box)
            for key in keys:
                if key == "tts.pitch_shift":
                    reset_chat_btn = QPushButton("Очистить чат")
                    reset_chat_btn.clicked.connect(self.reset_chat)
                    main.addWidget(reset_chat_btn)  
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
        """Создание UI-элемента по типу из конфига."""
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
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(edit)
            row.addWidget(btn)
            self.widgets[key] = edit
            return wrap
        
        else:
            w = QLineEdit()
        self.widgets[key] = w
        return w
    
    def reset_chat(self):
        print("очистить чат")

    def reset_model(self):
        print("перезапуск")

    def save(self):
        """Сохранение конфига и предложение перезапуска."""
        try:
            self.config_data = self._collect()
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=2)

            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setWindowTitle("Настройки сохранены")
            msg_box.setText("Изменения вступят в силу после перезапуска.\nПерезапустить сейчас?")

            btn_restart = msg_box.addButton("Перезапустить", QMessageBox.ButtonRole.AcceptRole)
            msg_box.addButton("Позже", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()

            if msg_box.clickedButton() == btn_restart:
                print("🔄 Перезапуск приложения...")
                os.execl(sys.executable, sys.executable, *sys.argv)
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")

    def load(self):
        """Загрузка конфига из файла и обновление UI."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config_data = json.load(f)
            self._apply(self.config_data)
            print("✅ Конфигурация загружена")
        except Exception as e:
            print(f"❌ Ошибка загрузки: {e}")


    def _browse_dir(self, ind):
        """Выбор директории через системный диалог."""
        vars = ["cache_dir", "model.init_prompt_path", "model.chat_history_path"]
        path = QFileDialog.getExistingDirectory(self, "Выберите директорию")
        if path:
            self.widgets[vars[ind]].setText(path)
    
    def _get(self, cfg, path):
        """Безопасное получение вложенного значения по точечному пути."""
        for part in path.split("."):
            if not isinstance(cfg, dict) or part not in cfg:
                return None
            cfg = cfg[part]
        return cfg

    def _apply(self, cfg):
        """Применение значений конфига к UI-элементам."""
        for key, w in self.widgets.items():
            val = self._get(cfg, key)
            if val is None:
                continue
            if isinstance(w, QCheckBox):
                w.setChecked(bool(val))
            elif isinstance(w, QComboBox):
                idx = w.findData(int(val)) if key == "stt.micro_index" else w.findText(str(val))
                w.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                w.setText(str(val))

    def reset(self):
        """Сброс настроек к значениям из шаблона."""
        self.config_data = self.default_config.copy()
        self._apply(self.config_data)
        print(" Конфигурация сброшена к шаблону")

    def _set(self, cfg, path, value):
        """Установка значения в вложенную структуру по точечному пути."""
        parts = path.split(".")
        for part in parts[:-1]:
            cfg = cfg.setdefault(part, {})
        cfg[parts[-1]] = value

    def _collect(self):
        """Сбор текущих значений UI в структуру конфига."""
        cfg = {}
        for key, w in self.widgets.items():
            if isinstance(w, QCheckBox):
                val = w.isChecked()
            elif isinstance(w, QComboBox):
                val = w.currentData() if key == "stt.micro_index" else w.currentText()
            else:
                val = w.text()

            if key in {
                "model.max_console_op_depth", "model.load_embeddings_count",
                "model.chat_size", "tts.pitch_shift", "stt.micro_index",
                "stt.silence_duration",
            }:
                val = self._to_int(val, self._get(self.config_data, key) or 0)

            self._set(cfg, key, val)
        return cfg

    def _to_int(self, text, silly=0):
        """Безопасное преобразование строки в int."""
        try:
            return int(str(text).strip())
        except Exception:
            return silly


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ConfigEditor()
    win.show()
    sys.exit(app.exec())
