import threading
import os
from PyQt6.QtWidgets import QMainWindow, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QPainter, QPixmap, QColor, QPen, QImage


class MainWindow(QMainWindow):
    phrase_finished = pyqtSignal()

    def __init__(self, ai_engine=None):
        super().__init__()
        self.setWindowTitle("Neuro_neighbor")
        self.resize(480, 560)
        self.setMinimumSize(420, 500)

        self.is_mic_active = False
        self.assets = {}
        self.ai_engine = ai_engine
        self._is_calibrating = False
        self._waiting_for_last_phrase = False
        self.stop_timeout_timer = QTimer(self)  # ← Явный таймер вместо singleShot
        self.stop_timeout_timer.setSingleShot(True)
        self.stop_timeout_timer.timeout.connect(self._force_stop_if_idle)

        self.phrase_finished.connect(self._on_phrase_finished)

        # Патчим колбэк STT в рантайме
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
        self.load_asset('mic', 'microphone.png')
        self.load_asset('settings', 'settings.png')

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        top = QHBoxLayout()
        top.setAlignment(Qt.AlignmentFlag.AlignLeft)
        top.setSpacing(12)

        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.setFixedSize(50, 50)
        self.settings_btn.setToolTip("Настройки")
        self.settings_btn.clicked.connect(self.open_settings)
        self.settings_btn.setIcon(self.make_icon('settings', "#999999"))
        self.settings_btn.setIconSize(self.settings_btn.size() * 0.6)
        top.addWidget(self.settings_btn)

        self.calibrate_btn = QPushButton("🔇 Калибровка")
        self.calibrate_btn.setObjectName("calibrateButton")
        self.calibrate_btn.setFixedHeight(40)
        self.calibrate_btn.setToolTip("Записать фоновый шум (3 сек молчания)")
        self.calibrate_btn.clicked.connect(self.start_calibration)
        top.addWidget(self.calibrate_btn)

        top.addStretch()
        layout.addLayout(top)

        layout.addStretch()
        self.mic_btn = QPushButton()
        self.mic_btn.setObjectName("micButton")
        self.mic_btn.setFixedSize(160, 160)
        self.mic_btn.clicked.connect(self.toggle_microphone)

        self.mic_icon_off = self.make_mic_icon("#FFFFFF", crossed=True)
        self.mic_icon_on = self.make_mic_icon("#FFFFFF", crossed=False)
        self.update_mic_icon()

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.mic_btn.setGraphicsEffect(shadow)

        layout.addWidget(self.mic_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

    def load_asset(self, name, filename):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, '..', 'assets', filename)
        if not os.path.exists(path):
            print(f"⚠️ {filename} не найден")
            return
        img = QPixmap(path).toImage().convertToFormat(QImage.Format.Format_ARGB32)
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
            p = icon.pixmap(160, 160)
            qp = QPainter(p)
            qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            qp.setPen(QPen(QColor(color), 8, cap=Qt.PenCapStyle.RoundCap))
            qp.drawLine(30, 30, 130, 130)
            qp.end()
            return QIcon(p)
        return icon

    def fallback(self, name, color):
        if name == 'settings':
            p = QPixmap(50, 50)
            p.fill(Qt.GlobalColor.transparent)
            qp = QPainter(p)
            qp.setRenderHint(QPainter.RenderHint.Antialiasing)
            qp.setBrush(QColor(color))
            qp.setPen(Qt.PenStyle.NoPen)
            qp.drawEllipse(15, 15, 20, 20)
            qp.setBrush(QColor("#2b2b2b"))
            qp.drawEllipse(20, 20, 10, 10)
            for i in range(8):
                qp.save()
                qp.translate(25, 25)
                qp.rotate(i * 45)
                qp.drawEllipse(-4, -22, 8, 8)
                qp.restore()
            qp.end()
            return QIcon(p)
        return QIcon()

    def update_mic_icon(self):
        self.mic_btn.setIcon(self.mic_icon_on if self.is_mic_active else self.mic_icon_off)
        self.mic_btn.setIconSize(self.mic_btn.size() * 0.65)

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
            self.stop_timeout_timer.start(6000)  # 6 сек на дослушивание + транскрибацию

        self.mic_btn.setObjectName("micButtonActive" if self.is_mic_active else "micButton")
        self.mic_btn.style().unpolish(self.mic_btn)
        self.mic_btn.style().polish(self.mic_btn)
        self.update_mic_icon()

    def _call_ai(self, method_name):
        if not self.ai_engine:
            print("⚠️ AI-движок не инициализирован")
            return
        if hasattr(self.ai_engine, method_name):
            try:
                getattr(self.ai_engine, method_name)()
            except Exception as e:
                print(f"⚠️ Ошибка AI.{method_name}: {e}")
        else:
            print(f"⚠️ Метод {method_name} не найден в AI-модуле")

    def _on_phrase_finished(self):
        if self._waiting_for_last_phrase:
            self.stop_timeout_timer.stop()  # Отменяем таймаут, фраза пришла
            self._waiting_for_last_phrase = False
            print("✅ Фраза обработана, останавливаю запись...")
            self._call_ai('stop_recognition')

    def _force_stop_if_idle(self):
        if self._waiting_for_last_phrase:
            self._waiting_for_last_phrase = False
            # Тихий сброс без лога: таймер просто гарантирует, что микрофон не зависнет
            self._call_ai('stop_recognition')

    def start_calibration(self):
        if not self.ai_engine:
            print("⚠️ AI-движок не инициализирован")
            return
        if not hasattr(self.ai_engine, 'calibrate'):
            print("⚠️ Метод калибровки недоступен в данной версии AI")
            return

        self._is_calibrating = True
        self.calibrate_btn.setEnabled(False)
        self.calibrate_btn.setText("⏳ Слушаю шум...")
        print("🎙️ Калибровка: пожалуйста, молчите 3 секунды...")

        if self.is_mic_active:
            self._call_ai('stop_recognition')

        threading.Thread(target=self._run_calibration, daemon=True).start()

    def _run_calibration(self):
        try:
            self.ai_engine.calibrate(duration=3)
            print("✅ Калибровка завершена успешно")
        except Exception as e:
            print(f"❌ Ошибка калибровки: {e}")
        finally:
            QTimer.singleShot(0, self._finish_calibration)

    def _finish_calibration(self):
        self._is_calibrating = False
        self.stop_timeout_timer.stop()  # ← Добавьте эту строку
        self.calibrate_btn.setEnabled(True)
        self.calibrate_btn.setText("🔇 Калибровка")
        # ... остальной код без изменений

    def open_settings(self):
        print("⚙️ Настройки")
