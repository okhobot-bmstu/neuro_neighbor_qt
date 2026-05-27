from pathlib import Path
from PyQt6.QtWidgets import QPushButton, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPainter, QPixmap, QColor, QPen, QImage

class MicControl(QPushButton):
    """Кнопка микрофона: управление состоянием, отрисовка иконки, QSS-стили."""
    toggled = pyqtSignal(bool)

    def __init__(self, project_root: Path, size: int = 140, parent=None):
        super().__init__(parent)
        self.project_root = project_root
        self.setFixedSize(size, size)
        self.setObjectName("micButton")
        self.is_mic_active = False
        self.assets = {}
        self._load_assets()
        self._setup_ui()
        self.clicked.connect(self._on_click)

    def _load_assets(self):
        """Загрузка PNG-ассета и конвертация белого фона в прозрачность."""
        path = self.project_root / "assets" / "microphone.png"
        if not path.exists():
            return

        img = QPixmap(str(path)).toImage().convertToFormat(QImage.Format.Format_ARGB32)
        for y in range(img.height()):
            for x in range(img.width()):
                if img.pixelColor(x, y).lightness() > 240:
                    img.setPixelColor(x, y, QColor(0, 0, 0, 0))
        self.assets["mic"] = QPixmap.fromImage(img)

    def _setup_ui(self):
        """Применение тени и инициализация состояния иконки."""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(22)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)
        self._update_icon()

    def _on_click(self):
        """Переключение состояния микрофона и уведомление подписчиков."""
        self.is_mic_active = not self.is_mic_active
        self.toggled.emit(self.is_mic_active)
        self._update_icon()

    def _update_icon(self):
        """Обновление иконки и триггер перерисовки стилей через QSS."""
        self.setIcon(self._make_mic_icon("#FFFFFF", crossed=not self.is_mic_active))
        self.setIconSize(self.size() * 0.7)
        self.setObjectName("micButtonActive" if self.is_mic_active else "micButton")
        self.style().unpolish(self)
        self.style().polish(self)

    def _make_icon(self, name: str, color: str) -> QIcon:
        """Создание QIcon из PNG-ассета с перекраской по альфа-каналу."""
        asset = self.assets.get(name)
        if not asset or asset.isNull():
            return self._fallback(color)

        p = QPixmap(asset.size())
        p.fill(Qt.GlobalColor.transparent)
        qp = QPainter(p)
        qp.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.Antialiasing)
        qp.drawPixmap(0, 0, asset)
        qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        qp.fillRect(p.rect(), QColor(color))
        qp.end()
        return QIcon(p)

    def _make_mic_icon(self, color: str, crossed: bool = False) -> QIcon:
        """Генерация иконки микрофона. При crossed=True добавляет диагональную линию."""
        icon = self._make_icon('mic', color)
        if not crossed:
            return icon

        p = icon.pixmap(self.size())
        w, h = p.width(), p.height()
        margin = int(w * 0.15)

        qp = QPainter(p)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        qp.setPen(QPen(QColor(color), max(4, int(w * 0.05)), cap=Qt.PenCapStyle.RoundCap))
        qp.drawLine(margin, margin, w - margin, h - margin)
        qp.end()

        return QIcon(p)

    def _fallback(self, color: str) -> QIcon:
        """Векторная отрисовка схематичного микрофона при отсутствии ассета."""
        size = int(self.width())
        p = QPixmap(size, size)
        p.fill(Qt.GlobalColor.transparent)

        qp = QPainter(p)
        qp.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        qp.setPen(Qt.PenStyle.NoPen)
        center = size / 2.0

        qp.setBrush(QColor(color))
        qp.drawEllipse(int(center - 20), int(center - 30), 40, 40)  # Головка
        qp.drawRect(int(center - 8), int(center), 16, 35)           # Ножка
        qp.drawEllipse(int(center - 15), int(center + 25), 30, 10)  # Основание
        qp.end()

        return QIcon(p)
