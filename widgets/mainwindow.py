import sys
import os
import threading
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QPushButton, QWidget, QVBoxLayout, QHBoxLayout,
    QGraphicsDropShadowEffect, QApplication, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QProcess
from PyQt6.QtGui import QIcon, QPainter, QPixmap, QColor, QPen, QImage


class MainWindow(QMainWindow):
    phrase_finished = pyqtSignal()

    def __init__(self, ai_engine=None, project_root=None):
        super().__init__()
        self.setWindowTitle("Neuro_neighbor")
        self.resize(480, 560)
        self.setMinimumSize(420, 500)

        # Определяем корневую папку проекта для относительных путей к ассетам
        self.project_root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent

        self.is_mic_active = False
        self.assets = {}
        self.ai_engine = ai_engine
        self._is_calibrating = False
        self._waiting_for_last_phrase = False
        self.settings_dialog = None

        # Таймер для принудительной остановки, если фраза не завершилась за 1 сек
        self.stop_timeout_timer = QTimer(self)
        self.stop_timeout_timer.setSingleShot(True)
        self.stop_timeout_timer.timeout.connect(self._force_stop_if_idle)
        self.phrase_finished.connect(self._on_phrase_finished)

        # Патчим коллбэк STT: эмитируем сигнал после обработки каждой фразы
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
        """Создание основной раскладки и кнопок управления."""
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
        """Загрузка PNG с конвертацией белых пикселей в прозрачные."""
        path = self.project_root / "assets" / filename
        if not path.exists():
            print(f"⚠️ {filename} не найден: {path}")
            return
        # Поэлементная обработка подходит только для маленьких иконок (<256x256)
        img = QPixmap(str(path)).toImage().convertToFormat(QImage.Format.Format_ARGB32)
        for y in range(img.height()):
            for x in range(img.width()):
                if img.pixelColor(x, y).lightness() > 240:
                    img.setPixelColor(x, y, QColor(0, 0, 0, 0))
        self.assets[name] = QPixmap.fromImage(img)

    def make_icon(self, name, color):
        """Генерация QIcon с заливкой цвета по альфа-каналу ассета."""
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
        """Создание иконки микрофона с опциональным перечеркиванием."""
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
        """Векторная отрисовка шестерёнки при отсутствии файла ассета."""
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
        """Переключение иконки и обновление стилей кнопки микрофона."""
        self.mic_btn.setIcon(self.mic_icon_on if self.is_mic_active else self.mic_icon_off)
        self.mic_btn.setIconSize(self.mic_btn.size() * 0.65)
        # Обновляем objectName для работы с QSS
        self.mic_btn.setObjectName("micButtonActive" if self.is_mic_active else "micButton")
        self.mic_btn.style().unpolish(self.mic_btn)
        self.mic_btn.style().polish(self.mic_btn)

    def toggle_microphone(self):
        """Включение/выключение микрофона и управление потоком распознавания."""
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

        self.update_mic_icon()  # Содержит всю логику обновления UI

    def _call_ai(self, method_name):
        """Безопасный вызов методов внешнего AI-движка."""
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
        """Обработка завершения распознавания фразы."""
        if self._waiting_for_last_phrase:
            self.stop_timeout_timer.stop()
            self._waiting_for_last_phrase = False
            print("✅ Фраза обработана, останавливаю запись...")
            self._call_ai('stop_recognition')

    def _force_stop_if_idle(self):
        """Принудительная остановка при превышении таймаута молчания."""
        if self._waiting_for_last_phrase:
            self._waiting_for_last_phrase = False
            self._call_ai('stop_recognition')

    def start_calibration(self):
        """Запуск калибровки шума в фоновом потоке."""
        if not self.ai_engine or not hasattr(self.ai_engine, 'calibrate'):
            print("⚠️ Калибровка недоступна")
            return

        self._is_calibrating = True
        self.calibrate_btn.setEnabled(False)
        self.calibrate_btn.setText("⏳ Слушаю шум...")
        print("⏱️ Калибровка: пожалуйста, молчите 3 секунды...")

        if self.is_mic_active:
            self._call_ai('stop_recognition')

        # Демон-поток не блокирует UI, результат возвращается в главный поток
        threading.Thread(target=self._run_calibration, daemon=True).start()

    def _run_calibration(self):
        """Вызов калибровки и безопасный возврат управления в UI."""
        try:
            self.ai_engine.calibrate(duration=3)
            print("✅ Калибровка завершена успешно")
        except Exception as e:
            print(f"❌ Ошибка калибровки: {e}")
        finally:
            # 0ms задержка гарантирует выполнение в основном потоке Qt после обновления UI
            QTimer.singleShot(0, self._finish_calibration)

    def _finish_calibration(self):
        """Возврат кнопки в исходное состояние и показ уведомления."""
        self._is_calibrating = False
        self.stop_timeout_timer.stop()
        self.calibrate_btn.setEnabled(True)
        self.calibrate_btn.setText("🔇 Калибровка")

        # Небольшая задержка предотвращает наложение диалога на перерисовку кнопки
        QTimer.singleShot(100, lambda: QMessageBox.information(
            self, "Калибровка", "Калибровка микрофона успешно завершена."
        ))

    def open_settings(self):
        """Открытие окна настроек с автоподключением к кнопкам Сохранить и Перезапустить."""
        if self.settings_dialog and self.settings_dialog.isVisible():
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return

        try:
            from widgets.settings import ConfigEditor
        except ImportError as e:
            QMessageBox.critical(self, "Ошибка модуля", f"Не удалось загрузить окно настроек:\n{e}")
            return

        self.settings_dialog = ConfigEditor(project_root=self.project_root, parent=self)
        # Удаляем окно из памяти при закрытии, чтобы не копить экземпляры
        self.settings_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # 1. Подключаем явный сигнал перезапуска
        if hasattr(self.settings_dialog, 'reset_signal'):
            self.settings_dialog.reset_signal.connect(self._on_restart_clicked)

        # 2. Находим кнопку "Сохранить" и перенаправляем её сигнал
        # Qt кеширует методы при connect(), поэтому простая замена self.save не сработает.
        # Нужно найти кнопку и переподключить её сигнал напрямую.
        for btn in self.settings_dialog.findChildren(QPushButton):
            if "сохранить" in btn.text().replace("&", "").lower():
                try:
                    btn.clicked.disconnect()
                except Exception:
                    pass
                btn.clicked.connect(self._on_save_clicked)
                break

        self.settings_dialog.show()

    def _on_restart_clicked(self):
        """Слот-обработчик сигнала перезапуска из окна настроек."""
        print("🔄 Получен запрос на перезапуск приложения")
        self._handle_restart()

    def _handle_restart(self):
        """Грейсфул-перезапуск приложения с очисткой ресурсов."""
        if self.settings_dialog:
            self.settings_dialog.close()
            self.settings_dialog = None

        if self.is_mic_active:
            self.is_mic_active = False
            self._call_ai('stop_recognition')

        # Запуск независимого процесса с текущими аргументами
        executable = sys.executable
        args = sys.argv
        work_dir = os.getcwd()

        if getattr(sys, 'frozen', False):  # PyInstaller / Nuitka
            QProcess.startDetached(executable, args, work_dir)
        else:
            script_path = os.path.abspath(sys.argv[0])
            QProcess.startDetached(executable, [script_path] + args[1:], work_dir)

        # Корректное завершение текущего экземпляра Qt
        QApplication.instance().quit()

    def _on_save_clicked(self):
        """Обработчик нажатия кнопки Сохранить с предложением перезапуска."""
        if self.settings_dialog and hasattr(self.settings_dialog, 'save'):
            self.settings_dialog.save()

        reply = QMessageBox.question(
            self, "Настройки сохранены",
            "Изменения вступят в силу после перезапуска.\nПерезапустить сейчас?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._handle_restart()

    def closeEvent(self, event):
        """Очистка ссылок на дочерние окна при закрытии главного окна."""
        if self.settings_dialog:
            self.settings_dialog.close()
            self.settings_dialog = None
        super().closeEvent(event)
