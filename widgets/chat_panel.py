import json
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QTextBlockFormat
from .chat_worker import ChatWorker

class ChatPanel(QWidget):
    """Панель чата: управление UI, историей и фоновой генерацией ответов."""
    history_cleared = pyqtSignal()

    def __init__(self, project_root: Path, ai_engine, parent=None):
        super().__init__(parent)
        self.project_root = project_root
        self.ai_engine = ai_engine
        self.chat_history = []
        self.chat_worker = None
        self._load_chat_history()
        self._init_ui()

    def _init_ui(self):
        """Сборка интерфейса: область сообщений, поле ввода и кнопка отправки."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setObjectName("chatDisplay")
        layout.addWidget(self.chat_display, stretch=1)

        # Восстановление сообщений при запуске
        # Берем последние 100 сообщений
        for msg in self.chat_history[-100:]:
            self._append_chat_message(msg["content"], msg["role"] == "user")

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
        layout.addLayout(input_row)

    def _append_chat_message(self, text: str, is_user: bool):
        """Добавление сообщения с выравниванием и стилями через Qt-курсор."""
        if not self.chat_display:
            return

        safe = text.replace(" & ", " &amp; ").replace(" < ", " &lt; ").replace(" > ", " &gt; ").replace("\n", " <br > ")

        bg = "#374658" if is_user else "#333333"
        border = "border: 2px solid #003366;" if is_user else ""
        html = f'<span style="display: inline-block; background: {bg}; {border} color: white; padding: 12px 18px; border-radius: 16px; max-width: 75%; font-size: 18px; line-height: 1.6; box-shadow: 0 3px 8px rgba(0,0,0,0.3);">{safe}</span>'

        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        block_fmt = QTextBlockFormat()
        block_fmt.setAlignment(Qt.AlignmentFlag.AlignRight if is_user else Qt.AlignmentFlag.AlignLeft)
        block_fmt.setTopMargin(6)
        block_fmt.setBottomMargin(16)
        cursor.insertBlock(block_fmt)
        cursor.insertHtml(html)

        # Автопрокрутка после отрисовки
        QTimer.singleShot(0, lambda: self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum()))

    def _send_chat_message(self):
        """Обработка отправки: валидация, блокировка ввода, запуск воркера."""
        if not self.chat_input or not self.ai_engine or (self.chat_worker and self.chat_worker.isRunning()):
            return
        text = self.chat_input.text().strip()
        if not text: 
            return

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
        """Приём ответа от AI: удаление индикатора, запись сообщения."""
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
        """Обработка ошибки генерации."""
        if self.chat_display:
            self.chat_display.append(f'<div style="color:#ff6b6b;margin:4px 0;">Ошибка: {error}</div>')
        self._cleanup_chat_worker()

    def _cleanup_chat_worker(self):
        """Ожидание завершения потока и разблокировка поля ввода."""
        if self.chat_worker:
            self.chat_worker.wait(2000)
            self.chat_worker.deleteLater()
            self.chat_worker = None
        if self.chat_input:
            self.chat_input.setEnabled(True)
            self.chat_input.setFocus()

    def _load_chat_history(self):
        """Загрузка истории из config/chat_history.json."""
        # ИЗМЕНЕНИЕ 2: Переименование файла
        path = self.project_root / "config" / "chat_history.json"
        if path.exists():
            try:
                self.chat_history = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self.chat_history = []

    def _save_chat_history(self):
        """Сохранение истории в config/chat_history.json."""
        # ИЗМЕНЕНИЕ 2: Переименование файла
        path = self.project_root / "config" / "chat_history.json"
        try:
            path.write_text(json.dumps(self.chat_history, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def clear_history(self):
        """Полный сброс: UI, локальный JSON и эммит сигнала."""
        self.chat_history.clear()
        self._save_chat_history()
        if self.chat_display:
            self.chat_display.clear()
        self.history_cleared.emit()
