import re
from PyQt6.QtCore import QThread, pyqtSignal

class ChatWorker(QThread):
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    # Инициализация воркера: сохранение ссылки на AI-движок и текст запроса
    def __init__(self, ai_engine, text: str):
        super().__init__()
        self.ai_engine = ai_engine
        self.text = text
        self._captured_response = None

    # Обёртка для перехвата возвращаемого значения метода chat
    def _capture_chat(self, original_func):
        def wrapper(*args, **kwargs):
            result = original_func(*args, **kwargs)
            self._captured_response = result
            return result
        return wrapper

    # Выполнение запроса к AI в фоновом потоке и обработка ответа
    def run(self):
        try:
            if not hasattr(self.ai_engine, 'neuro') or not hasattr(self.ai_engine.neuro, 'chat'):
                self.response_ready.emit(" ")
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

                lines = []
                for line in clean.split('\n'):
                    line = line.strip()
                    if line and not line.startswith(('<<', '>>')):
                        lines.append(line)

                response = '\n'.join(lines) if lines else raw[:500]

            self.response_ready.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))
