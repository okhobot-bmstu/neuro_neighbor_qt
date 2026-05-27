import sys
import os
import threading
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QProcess
from PyQt6.QtGui import QIcon, QPainter, QPixmap, QColor, QPen, QImage

from .chat_panel import ChatPanel
from .mic_control import MicControl


class MainWindow(QMainWindow):
    """Координатор UI: маршрутизация сигналов, управление AI/STT, жизненный цикл."""
    phrase_finished = pyqtSignal()

    def __init__(self, ai_engine=None, project_root=None):
        super().__init__()
        self.setWindowTitle("Neuro_neighbor")
        self.resize(1920, 1080)
        self.setMinimumSize(500, 700)

        self.project_root = Path(project_root) or Path(__file__).resolve().parent.parent
        self.ai_engine = ai_engine
        self.assets = {}
        self.settings_dialog = None

        self.is_mic_active = False
        self._is_calibrating = False
        self._waiting_for_last_phrase = False

        self.stop_timeout_timer = QTimer(self)
        self.stop_timeout_timer.setSingleShot(True)
        self.stop_timeout_timer.timeout.connect(self._force_stop_if_idle)
        self.phrase_finished.connect(self._on_phrase_finished)

        # Патчим STT-коллбэк для эмитации сигнала без изменения src/
        if self.ai_engine and hasattr(self.ai_engine, 'stt'):
            original_cb = self.ai_engine.stt.call_func
            def patched_cb(text, depth=0):
                if self._is_calibrating: return
                original_cb(text, depth)
                self.phrase_finished.emit()
            self.ai_engine.stt.call_func = patched_cb

        self._init_ui()

    def _init_ui(self):
        self.load_asset('settings', 'settings.png')
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 16)
        main_layout.setSpacing(10)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.setFixedSize(44, 44)
        self.settings_btn.setToolTip("Настройки")
        self.settings_btn.clicked.connect(self.open_settings)
        self.settings_btn.setIcon(self._make_settings_icon("#999999"))
        self.settings_btn.setIconSize(self.settings_btn.size() * 0.65)
        top_bar.addWidget(self.settings_btn)

        self.calibrate_btn = QPushButton("Калибровка")
        self.calibrate_btn.setObjectName("calibrateButton")
        self.calibrate_btn.setFixedHeight(44)
        self.calibrate_btn.setToolTip("Записать фоновый шум (3 сек)")
        self.calibrate_btn.clicked.connect(self.start_calibration)
        top_bar.addWidget(self.calibrate_btn)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        self.chat_panel = ChatPanel(self.project_root, self.ai_engine)
        main_layout.addWidget(self.chat_panel, stretch=1)

        self.mic_btn = MicControl(self.project_root)
        self.mic_btn.toggled.connect(self._on_mic_toggled)
        main_layout.addWidget(self.mic_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def load_asset(self, name: str, filename: str):
        """Загрузка PNG с конвертацией белого фона в прозрачность."""
        path = self.project_root / "assets" / filename
        if not path.exists(): return

        img = QPixmap(str(path)).toImage().convertToFormat(QImage.Format.Format_ARGB32)
        for y in range(img.height()):
            for x in range(img.width()):
                if img.pixelColor(x, y).lightness() > 240:
                    img.setPixelColor(x, y, QColor(0, 0, 0, 0))
        self.assets[name] = QPixmap.fromImage(img)

    def _make_settings_icon(self, color: str) -> QIcon:
        """Перекраска PNG-ассета с сохранением альфа-канала."""
        asset = self.assets.get('settings')
        if not asset or asset.isNull(): return self._fallback_settings_icon(color)

        p = QPixmap(asset.size())
        p.fill(Qt.GlobalColor.transparent)
        qp = QPainter(p)
        qp.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.Antialiasing)
        qp.drawPixmap(0, 0, asset)
        qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        qp.fillRect(p.rect(), QColor(color))
        qp.end()
        return QIcon(p)

    def _fallback_settings_icon(self, color: str) -> QIcon:
        """Векторная заглушка при отсутствии ассета."""
        size = 44
        p = QPixmap(size, size)
        p.fill(Qt.GlobalColor.transparent)
        qp = QPainter(p)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.setPen(Qt.PenStyle.NoPen)
        c = size / 2.0
        qp.setBrush(QColor(color))
        qp.drawEllipse(int(c - 10), int(c - 10), 20, 20)
        qp.setBrush(QColor("#2b2b2b"))
        qp.drawEllipse(int(c - 5), int(c - 5), 10, 10)
        qp.setBrush(QColor(color))
        for i in range(8):
            qp.save(); qp.translate(c, c); qp.rotate(i * 45); qp.drawEllipse(-4, -22, 8, 8); qp.restore()
        qp.end()
        return QIcon(p)

    def _on_mic_toggled(self, is_active: bool):
        self.is_mic_active = is_active
        if is_active:
            self._waiting_for_last_phrase = False
            self._call_ai('start_recognition')
        else:
            self._waiting_for_last_phrase = True
            self.stop_timeout_timer.start(1000)

    def _call_ai(self, method_name):
        """Безопасный вызов методов внешнего AI-движка."""
        if not self.ai_engine: return
        if hasattr(self.ai_engine, method_name):
            try: getattr(self.ai_engine, method_name)()
            except Exception as e: print(f"⚠️ Ошибка AI.{method_name}: {e}")

    def _on_phrase_finished(self):
        if self._waiting_for_last_phrase:
            self.stop_timeout_timer.stop()
            self._waiting_for_last_phrase = False
            self._call_ai('stop_recognition')

    def _force_stop_if_idle(self):
        if self._waiting_for_last_phrase:
            self._waiting_for_last_phrase = False
            self._call_ai('stop_recognition')

    def start_calibration(self):
        if not self.ai_engine or not hasattr(self.ai_engine, 'calibrate'): return
        self._is_calibrating = True
        self.calibrate_btn.setEnabled(False)
        self.calibrate_btn.setText("⏳ Слушаю шум...")
        if self.is_mic_active: self._call_ai('stop_recognition')
        threading.Thread(target=self._run_calibration, daemon=True).start()

    def _run_calibration(self):
        try: self.ai_engine.calibrate(duration=3)
        except Exception as e: print(f"❌ Ошибка калибровки: {e}")
        finally: QTimer.singleShot(0, self._finish_calibration)  # Безопасный возврат в UI-поток

    def _finish_calibration(self):
        self._is_calibrating = False
        self.stop_timeout_timer.stop()
        self.calibrate_btn.setEnabled(True)
        self.calibrate_btn.setText("Калибровка")
        QTimer.singleShot(100, lambda: QMessageBox.information(self, "Калибровка", "Калибровка микрофона успешно завершена."))

    def open_settings(self):
        """Открытие окна настроек. WA_DeleteOnClose требует защиты от обращений к удалённому C++ объекту."""
        if self.settings_dialog is not None:
            try:
                if self.settings_dialog.isVisible():
                    self.settings_dialog.raise_()
                    self.settings_dialog.activateWindow()
                    return
            except RuntimeError:
                self.settings_dialog = None

        try:
            from widgets.settings import ConfigEditor
        except ImportError as e:
            QMessageBox.critical(self, "Ошибка модуля", f"Не удалось загрузить окно настроек:\n{e}")
            return

        self.settings_dialog = ConfigEditor(project_root=self.project_root, parent=self)
        self.settings_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        if hasattr(self.settings_dialog, 'reset_signal'):
            self.settings_dialog.reset_signal.connect(self._handle_restart)

        self.settings_dialog.show()
        # Задержка 10ms гарантирует, что дерево виджетов полностью построено до поиска кнопок
        QTimer.singleShot(10, self._patch_settings_buttons)

    def _patch_settings_buttons(self):
        """Перенаправление кликов через monkey-patch (обход проблем с Z-order и фокусом)."""
        if not self.settings_dialog: return
        for btn in self.settings_dialog.findChildren(QPushButton):
            text = btn.text().replace("&", "").lower()
            if "сохранить" in text:
                try: btn.clicked.disconnect()
                except Exception: pass
                btn.clicked.connect(self._on_save_clicked)
            elif "очистить историю" in text:
                original_clear = self.settings_dialog.reset_chat
                def wrapped_clear():
                    original_clear()  # Удаляет файл на диске
                    self.chat_panel.clear_history()  # Очищает UI
                    if self.ai_engine and hasattr(self.ai_engine, 'neuro'):
                        if hasattr(self.ai_engine.neuro, 'chat_history'):
                            self.ai_engine.neuro.chat_history.clear()
                        self._call_ai('load_history')  # Перезагружает пустую историю в память AI
                btn.clicked.connect(wrapped_clear)

    def _on_save_clicked(self):
        """Сохранение настроек и показ диалога перезапуска."""
        try:
            if hasattr(self.settings_dialog, 'save'):
                self.settings_dialog.save()
        except Exception as e:
            print(f"⚠️ Ошибка сохранения настроек: {e}")
            return

        QApplication.processEvents()
        msg = QMessageBox()
        msg.setWindowTitle("Настройки сохранены")
        msg.setText("Изменения вступят в силу после перезапуска.\nПерезапустить сейчас?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        msg.setWindowModality(Qt.WindowModality.ApplicationModal)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self._handle_restart()

    def _handle_restart(self):
        """Грейсфул-перезапуск: остановка аудио, запуск нового процесса, выход."""
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

    def closeEvent(self, event):
        """Безопасная очистка потоков и дочерних окон при закрытии."""
        if hasattr(self, 'chat_panel') and self.chat_panel.chat_worker and self.chat_panel.chat_worker.isRunning():
            self.chat_panel.chat_worker.wait(2000)
        if self.settings_dialog is not None:
            try: self.settings_dialog.close()
            except RuntimeError: pass
            self.settings_dialog = None
        super().closeEvent(event)
