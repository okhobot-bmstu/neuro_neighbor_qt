import os
from PyQt6.QtWidgets import QMainWindow, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap, QColor, QPen, QImage

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Neuro_neighbor")
        self.showMaximized()
        self.is_mic_active = False
        self.assets = {}
        self.init_ui()

    def init_ui(self):
        self.load_asset('mic', 'microphone.png')
        self.load_asset('settings', 'settings.png')

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Настройки
        top = QHBoxLayout()
        top.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.setFixedSize(50, 50)
        self.settings_btn.setToolTip("Настройки")
        self.settings_btn.clicked.connect(self.open_settings)
        self.settings_btn.setIcon(self.make_icon('settings', "#999999"))
        self.settings_btn.setIconSize(self.settings_btn.size() * 0.6)
        top.addWidget(self.settings_btn)
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
        self.is_mic_active = not self.is_mic_active
        self.mic_btn.setObjectName("micButtonActive" if self.is_mic_active else "micButton")
        self.mic_btn.style().unpolish(self.mic_btn)
        self.mic_btn.style().polish(self.mic_btn)
        self.update_mic_icon()
        print("🎤 Микрофон", "ВКЛ" if self.is_mic_active else "ВЫКЛ")

    def open_settings(self):
        print("⚙️ Настройки")
