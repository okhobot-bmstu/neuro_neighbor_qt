import sys
import os
import threading
import json
import re
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QPushButton, QWidget, QVBoxLayout, QHBoxLayout,
    QGraphicsDropShadowEffect, QApplication, QMessageBox,
    QTextEdit, QLineEdit, QToolButton, QLabel
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QProcess, QThread
from PyQt6.QtGui import QIcon, QPainter, QPixmap, QColor, QPen, QImage


class ChatWorker(QThread):
    """Фоновый воркер с перехватом ответа через патч нейро-чата."""
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, ai_engine, text: str):
        super().__init__()
        self.ai_engine = ai_engine
        self.text = text
        self._captured_response = None

    def _capture_chat(self, original_chat):
        def wrapper(*args, **kwargs):
            result = original_chat(*args, **kwargs)
            self._captured_response = result
            return result
        return wrapper

    def run(self):
        try:
            if not (hasattr(self.ai_engine, 'neuro') and hasattr(self.ai_engine.neuro, 'chat')):
                self.response_ready.emit("")
                return

            original_chat = self.ai_engine.neuro.chat
            self.ai_engine.neuro.chat = self._capture_chat(original_chat)

            try:
                self.ai_engine.chat(self.text)
            finally:
                self.ai_engine.neuro.chat = original_chat

            response = ""
            if self._captured_response is not None:
                raw = str(self._captured_response).strip()
                clean = re.sub(r'```.*?```', '', raw, flags=re.DOTALL).strip()
                for line in clean.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('<<') and not line.startswith('>>'):
                        response = line
                        break
                if not response:
                    response = raw[:500]
            self.response_ready.emit(response)
        except Exception as e:
            print(f"❌ [ChatWorker] Ошибка: {e}")
            self.error_occurred.emit(str(e))


class MainWindow(QMainWindow):
    phrase_finished = pyqtSignal()

    def __init__(self, ai_engine=None, project_root=None):
        super().__init__()
        self.setWindowTitle("Neuro_neighbor")
        self.resize(1920, 1080)
        self.setMinimumSize(450, 800)

        self.project_root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent

        self.is_mic_active = False
        self.assets = {}
        self.ai_engine = ai_engine
        self._is_calibrating = False
        self._waiting_for_last_phrase = False
        self.settings_dialog = None

        # Чат
        self.chat_history = []
        self.chat_worker = None
        self.chat_display = None
        self.chat_input = None
        self.mic_btn = None
        self.calibrate_btn = None
        self.settings_btn = None

        self._load_chat_history()

        # Таймер
        self.stop_timeout_timer = QTimer(self)
        self.stop_timeout_timer.setSingleShot(True)
        self.stop_timeout_timer.timeout.connect(self._force_stop_if_idle)
        self.phrase_finished.connect(self._on_phrase_finished)

        # Патч STT
        if self.ai_engine and hasattr(self.ai_engine, 'stt'):
            original_cb = self.ai_engine.stt.call_func
            def patched_cb(text, depth=0):
                if self._is_calibrating:
                    return
                original_cb(text, depth)
                self.phrase_finished.emit()
            self.ai_engine.stt.call_func = patched_cb

        self.init_ui()

    def init_ui(self):
        """Централизованная раскладка: чат по центру, микрофон снизу."""
        self.load_asset('mic', 'microphone.png')
        self.load_asset('settings', 'settings.png')

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 16)
        main_layout.setSpacing(10)

        # Верхняя панель
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.setFixedSize(44, 44)
        self.settings_btn.setToolTip("Настройки")
        self.settings_btn.clicked.connect(self.open_settings)
        self.settings_btn.setIcon(self.make_icon('settings', "#999999"))
        self.settings_btn.setIconSize(self.settings_btn.size() * 0.65)
        top_bar.addWidget(self.settings_btn)

        self.calibrate_btn = QPushButton("🔇 Калибровка")
        self.calibrate_btn.setObjectName("calibrateButton")
        self.calibrate_btn.setFixedHeight(36)
        self.calibrate_btn.setToolTip("Записать фоновый шум (3 сек)")
        self.calibrate_btn.clicked.connect(self.start_calibration)
        top_bar.addWidget(self.calibrate_btn)

        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # Область чата (стили вынесены во внешний QSS)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setObjectName("chatDisplay")
        main_layout.addWidget(self.chat_display, stretch=1)

        # Загрузка истории в чат
        for msg in self.chat_history[-100:]:
            self._append_chat_message(msg["content"], msg["role"] == "user")

        # Поле ввода + кнопка отправки
        input_row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Введите сообщение...")
        self.chat_input.returnPressed.connect(self._send_chat_message)
        self.chat_input.setObjectName("chatInput")

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(42, 42)
        send_btn.setObjectName("sendButton")
        send_btn.clicked.connect(self._send_chat_message)

        input_row.addWidget(self.chat_input, stretch=1)
        input_row.addWidget(send_btn)
        main_layout.addLayout(input_row)

        # Кнопка микрофона (по центру под вводом, гарантированно круглая)
        mic_wrap = QWidget()
        mic_layout = QVBoxLayout(mic_wrap)
        mic_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.mic_btn = QPushButton()
        self.mic_btn.setObjectName("micButton")
        self.mic_btn.setFixedSize(140, 140)
        self.mic_btn.clicked.connect(self.toggle_microphone)

        self.mic_icon_off = self.make_mic_icon("#FFFFFF", crossed=True)
        self.mic_icon_on = self.make_mic_icon("#FFFFFF", crossed=False)
        self.update_mic_icon()

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(22)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.mic_btn.setGraphicsEffect(shadow)

        mic_layout.addWidget(self.mic_btn)
        main_layout.addWidget(mic_wrap)

    def load_asset(self, name, filename):
        path = self.project_root / "assets" / filename
        if not path.exists():
            print(f"⚠️ {filename} не найден: {path}")
            return
        img = QPixmap(str(path)).toImage().convertToFormat(QImage.Format.Format_ARGB32)
        for y in range(img.height()):
            for x in range(img.width()):
                if img.pixelColor(x, y).lightness() > 240:
                    img.setPixelColor(x, y, QColor(0, 0, 0, 0))
        self.assets[name] = QPixmap.fromImage(img)

    def make_icon(self, name, color):
        if name not in self.assets or self.assets[name].isNull():
            return self.fallback(name, color)
        p = QPixmap(self.assets[name].size())
        p.fill(Qt.GlobalColor.transparent)
        qp = QPainter(p)
        qp.fillRect(p.rect(), QColor(color))
        qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        qp.drawPixmap(0, 0, self.assets[name])
        qp.end()
        return QIcon(p)

    def make_mic_icon(self, color, crossed=False):
        icon = self.make_icon('mic', color)
        if crossed:
            p = icon.pixmap(140, 140)
            qp = QPainter(p)
            qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            qp.setPen(QPen(QColor(color), 7, cap=Qt.PenCapStyle.RoundCap))
            qp.drawLine(25, 25, 115, 115)
            qp.end()
            return QIcon(p)
        return icon

    def fallback(self, name, color):
        if name == 'settings':
            p = QPixmap(44, 44)
            p.fill(Qt.GlobalColor.transparent)
            qp = QPainter(p)
            qp.setRenderHint(QPainter.RenderHint.Antialiasing)
            qp.setBrush(QColor(color))
            qp.setPen(Qt.PenStyle.NoPen)
            qp.drawEllipse(12, 12, 20, 20)
            qp.setBrush(QColor("#2b2b2b"))
            qp.drawEllipse(16, 16, 12, 12)
            for i in range(8):
                qp.save()
                qp.translate(22, 22)
                qp.rotate(i * 45)
                qp.drawEllipse(-3, -18, 6, 6)
                qp.restore()
            qp.end()
            return QIcon(p)
        return QIcon()

    def update_mic_icon(self):
        self.mic_btn.setIcon(self.mic_icon_on if self.is_mic_active else self.mic_icon_off)
        self.mic_btn.setIconSize(self.mic_btn.size() * 0.7)
        self.mic_btn.setObjectName("micButtonActive" if self.is_mic_active else "micButton")
        self.mic_btn.style().unpolish(self.mic_btn)
        self.mic_btn.style().polish(self.mic_btn)

    def toggle_microphone(self):
        if not self.is_mic_active:
            print("🎤 Микрофон ВКЛЮЧЁН")
            self._waiting_for_last_phrase = False
            self.is_mic_active = True
            self._call_ai('start_recognition')
        else:
            print("🔇 Микрофон выключен. Дожидаюсь конца фразы...")
            self.is_mic_active = False
            self._waiting_for_last_phrase = True
            self.stop_timeout_timer.start(1000)
        self.update_mic_icon()

    def _call_ai(self, method_name):
        if not self.ai_engine:
            print("⚠️ AI-движок не инициализирован")
            return
        if hasattr(self.ai_engine, method_name):
            try: getattr(self.ai_engine, method_name)()
            except Exception as e: print(f"⚠️ Ошибка AI.{method_name}: {e}")
        else: print(f"⚠️ Метод {method_name} не найден")

    def _on_phrase_finished(self):
        if self._waiting_for_last_phrase:
            self.stop_timeout_timer.stop()
            self._waiting_for_last_phrase = False
            print("✅ Фраза обработана, останавливаю запись...")
            self._call_ai('stop_recognition')

    def _force_stop_if_idle(self):
        if self._waiting_for_last_phrase:
            self._waiting_for_last_phrase = False
            self._call_ai('stop_recognition')

    def start_calibration(self):
        if not self.ai_engine or not hasattr(self.ai_engine, 'calibrate'):
            print("⚠️ Калибровка недоступна")
            return
        self._is_calibrating = True
        self.calibrate_btn.setEnabled(False)
        self.calibrate_btn.setText("⏳ Слушаю шум...")
        if self.is_mic_active: self._call_ai('stop_recognition')
        threading.Thread(target=self._run_calibration, daemon=True).start()

    def _run_calibration(self):
        try: self.ai_engine.calibrate(duration=3)
        except Exception as e: print(f"❌ Ошибка калибровки: {e}")
        finally: QTimer.singleShot(0, self._finish_calibration)

    def _finish_calibration(self):
        self._is_calibrating = False
        self.stop_timeout_timer.stop()
        self.calibrate_btn.setEnabled(True)
        self.calibrate_btn.setText("🔇 Калибровка")
        QTimer.singleShot(100, lambda: QMessageBox.information(self, "Калибровка", "Калибровка микрофона успешно завершена."))

    def open_settings(self):
        """Открытие окна настроек с безопасной проверкой на удалённый C++ объект."""
        # 1. Безопасная проверка: если C++ объект уже удалён, сбрасываем ссылку
        if self.settings_dialog is not None:
            try:
                if self.settings_dialog.isVisible():
                    self.settings_dialog.raise_()
                    self.settings_dialog.activateWindow()
                    return
            except RuntimeError:
                self.settings_dialog = None  # Очистка ссылки на удалённый объект

        try:
            from widgets.settings import ConfigEditor
        except ImportError as e:
            QMessageBox.critical(self, "Ошибка модуля", f"Не удалось загрузить окно настроек:\n{e}")
            return

        self.settings_dialog = ConfigEditor(project_root=self.project_root, parent=self)
        self.settings_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # 2. Сигнал перезапуска
        if hasattr(self.settings_dialog, 'reset_signal'):
            self.settings_dialog.reset_signal.connect(self._on_restart_clicked)

        # 3. Перехват кнопки "Сохранить"
        for btn in self.settings_dialog.findChildren(QPushButton):
            if "сохранить" in btn.text().replace("&", "").lower():
                try: btn.clicked.disconnect()
                except Exception: pass
                btn.clicked.connect(self._on_save_clicked)
                break

        # 4. Перехват кнопки "Очистить историю"
        for btn in self.settings_dialog.findChildren(QPushButton):
            if "очистить историю" in btn.text().lower():
                original_clear = self.settings_dialog.reset_chat
                def wrapped_clear():
                    original_clear()
                    self._clear_chat_everywhere()
                btn.clicked.connect(wrapped_clear)
                break

        self.settings_dialog.show()

    def _on_restart_clicked(self):
        print("🔄 Получен запрос на перезапуск приложения")
        self._handle_restart()

    def _handle_restart(self):
        if self.settings_dialog:
            self.settings_dialog.close()
            self.settings_dialog = None
        if self.is_mic_active:
            self.is_mic_active = False
            self._call_ai('stop_recognition')
        executable = sys.executable
        args = sys.argv
        work_dir = os.getcwd()
        if getattr(sys, 'frozen', False):
            QProcess.startDetached(executable, args, work_dir)
        else:
            script_path = os.path.abspath(sys.argv[0])
            QProcess.startDetached(executable, [script_path] + args[1:], work_dir)
        QApplication.instance().quit()

    def _on_save_clicked(self):
        if self.settings_dialog and hasattr(self.settings_dialog, 'save'):
            self.settings_dialog.save()
        reply = QMessageBox.question(
            self, "Настройки сохранены",
            "Изменения вступят в силу после перезапуска.\nПерезапустить сейчас?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._handle_restart()

    def _append_chat_message(self, text: str, is_user: bool):
        if not self.chat_display: return
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        align = "right" if is_user else "left"
        bg = "#0066cc" if is_user else "#333333"
        # Увеличен шрифт до 16px, добавлены отступы для читаемости
        html = f'''
        <div style="text-align: {align}; margin: 8px 0;">
            <span style="display: inline-block; background: {bg}; color: white; padding: 12px 16px; border-radius: 16px; max-width: 75%; font-size: 16px; line-height: 1.5; box-shadow: 0 2px 6px rgba(0,0,0,0.3);">
                {safe}
            </span>
        </div>
        '''
        self.chat_display.append(html)
        QTimer.singleShot(0, lambda: self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum()))

    def _send_chat_message(self):
        if not self.chat_input or not self.ai_engine or (self.chat_worker and self.chat_worker.isRunning()):
            return
        text = self.chat_input.text().strip()
        if not text: return
        self._append_chat_message(text, is_user=True)
        self.chat_history.append({"role": "user", "content": text})
        self._save_chat_history()
        self.chat_input.clear()
        self.chat_input.setEnabled(False)
        self.chat_display.append('<div style="color:#888;font-style:italic;margin:4px 0;">⋮ генерация...</div>')
        self.chat_worker = ChatWorker(self.ai_engine, text)
        self.chat_worker.response_ready.connect(self._on_chat_response)
        self.chat_worker.error_occurred.connect(self._on_chat_error)
        self.chat_worker.start()

    def _on_chat_response(self, response: str):
        if self.chat_display:
            cursor = self.chat_display.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
        if response:
            self._append_chat_message(response, is_user=False)
            self.chat_history.append({"role": "assistant", "content": response})
            self._save_chat_history()
        self._cleanup_chat_worker()

    def _on_chat_error(self, error: str):
        if self.chat_display:
            self.chat_display.append(f'<div style="color:#ff6b6b;margin:4px 0;">❌ Ошибка: {error}</div>')
        self._cleanup_chat_worker()

    def _cleanup_chat_worker(self):
        if self.chat_worker:
            self.chat_worker.wait(2000)
            self.chat_worker.deleteLater()
            self.chat_worker = None
        if self.chat_input:
            self.chat_input.setEnabled(True)
            self.chat_input.setFocus()

    def _load_chat_history(self):
        path = self.project_root / "config" / "chat_session.json"
        if path.exists():
            try: self.chat_history = json.loads(path.read_text(encoding="utf-8"))
            except Exception: self.chat_history = []

    def _save_chat_history(self):
        path = self.project_root / "config" / "chat_session.json"
        try: path.write_text(json.dumps(self.chat_history, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception: pass

    def _clear_chat_everywhere(self):
        """Полная очистка истории: AI, UI и локального кэша."""
        # 1. Сбрасываем память AI-движка
        if self.ai_engine and hasattr(self.ai_engine, 'neuro'):
            if hasattr(self.ai_engine.neuro, 'chat_history'):
                self.ai_engine.neuro.chat_history.clear()
            # Безопасно перезагружаем историю (файл уже удалён оригинальным методом)
            self._call_ai('load_history')

        # 2. Очищаем интерфейс и локальную сессию
        self.chat_history.clear()
        self._save_chat_history()  # Перезаписывает config/chat_session.json пустым списком []
        if self.chat_display:
            self.chat_display.clear()

    def closeEvent(self, event):
        """Очистка ресурсов при закрытии приложения."""
        # 1. Ждём завершения воркера чата
        if self.chat_worker and self.chat_worker.isRunning():
            self.chat_worker.wait(2000)

        # 2. Безопасное закрытие настроек (ловит обращение к удалённому C++ объекту)
        if self.settings_dialog is not None:
            try:
                self.settings_dialog.close()
            except RuntimeError:
                pass  # Окно уже удалено Qt через WA_DeleteOnClose
            self.settings_dialog = None

        super().closeEvent(event)
