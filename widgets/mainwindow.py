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
    calibration_done = pyqtSignal(bool)

    def __init__(self, ai_engine=None, project_root=None):
        super().__init__()
        self.setWindowTitle("Neuro_neighbor")
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
        self.calibration_done.connect(self._finish_calibration)

        # Патчим STT-коллбэк для эмитации сигнала без изменения src/
        if self.ai_engine and hasattr(self.ai_engine, 'stt'):
            original_cb = self.ai_engine.stt.call_func
            def patched_cb(text, depth=0):
                if self._is_calibrating: return
                original_cb(text, depth)
                self.phrase_finished.emit()
            self.ai_engine.stt.call_func = patched_cb

        self._init_ui()
        self.showMaximized()

    def _init_ui(self):
        """Сборка интерфейса: загрузка ассетов, кнопок и панели чата."""
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
        """Обработка переключения микрофона: запуск/остановка распознавания."""
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
        """Обработка сигнала окончания фразы: остановка таймера и AI."""
        if self._waiting_for_last_phrase:
            self.stop_timeout_timer.stop()
            self._waiting_for_last_phrase = False
            self._call_ai('stop_recognition')

    def _force_stop_if_idle(self):
        """Принудительная остановка, если фраза не была распознана."""
        if self._waiting_for_last_phrase:
            self._waiting_for_last_phrase = False
            self._call_ai('stop_recognition')

    def start_calibration(self):
        """Запуск процесса калибровки микрофона в отдельном потоке."""
        if not self.ai_engine or not hasattr(self.ai_engine, 'calibrate'): return
        self._is_calibrating = True
        self.calibrate_btn.setEnabled(False)
        self.calibrate_btn.setText("⏳ Слушаю шум...")
        if self.is_mic_active: self._call_ai('stop_recognition')
        threading.Thread(target=self._run_calibration, daemon=True).start()

    def _run_calibration(self):
        """Фоновая задача: вызов калибровки и обработка ошибок."""
        success = True
        try:
            self.ai_engine.calibrate(duration=3)
        except Exception as e:
            print(f"❌ Ошибка калибровки: {e}")
            success = False
        finally:
            self.calibration_done.emit(success)

    def _finish_calibration(self, success: bool):
        """Завершение калибровки в UI-потоке (вызывается через сигнал)."""
        self._is_calibrating = False
        self.stop_timeout_timer.stop()
        self.calibrate_btn.setEnabled(True)
        self.calibrate_btn.setText("Калибровка")
        self._show_calibration_result(success)

    def _show_calibration_result(self, success: bool):
        """Показ результата калибровки пользователю."""
        if success:
            QMessageBox.information(self, "Калибровка", "Калибровка микрофона успешно завершена.")
        else:
            QMessageBox.warning(self, "Ошибка калибровки",
                                "Не удалось настроить микрофон.\n"
                                "Возможно, устройство не поддерживает частоту дискретизации или занято.")

    def open_settings(self):
        """Открытие окна настроек с проверкой на уже открытое окно."""
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
        QTimer.singleShot(10, self._patch_settings_buttons)

    def _patch_settings_buttons(self):
        """Перенаправление кликов кнопок в настройках на методы MainWindow."""
        if not self.settings_dialog: return
        for btn in self.settings_dialog.findChildren(QPushButton):
            text = btn.text().replace(" & ", " ").lower()
            if "сохранить" in text:
                try: btn.clicked.disconnect()
                except Exception: pass
                btn.clicked.connect(self._on_save_clicked)
            elif "очистить историю" in text:
                original_clear = self.settings_dialog.reset_chat
                def wrapped_clear():
                    original_clear()
                    self.chat_panel.clear_history()
                    if self.ai_engine and hasattr(self.ai_engine, 'neuro'):
                        if hasattr(self.ai_engine.neuro, 'chat_history'):
                            self.ai_engine.neuro.chat_history.clear()
                        self._call_ai('load_history')
                btn.clicked.connect(wrapped_clear)

    def _on_save_clicked(self):
        """Сохранение настроек и показ диалога перезапуска с фокусом на Yes."""
        if not self.settings_dialog:
            return

        try:
            if hasattr(self.settings_dialog, 'save'):
                self.settings_dialog.save()
        except Exception as e:
            print(f"⚠️ Ошибка сохранения настроек: {e}")
            return

        QApplication.processEvents()

        msg = QMessageBox(self.settings_dialog)
        msg.setWindowTitle("Сохранение")
        msg.setText("Изменения вступят в силу после перезапуска.\nПерезапустить сейчас?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        msg.setWindowModality(Qt.WindowModality.ApplicationModal)

        result = msg.exec()

        if result == QMessageBox.StandardButton.Yes:
            self._handle_restart()
            return

    def _handle_restart(self):
        """Грейсфул-перезапуск приложения."""
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
