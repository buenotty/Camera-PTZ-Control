from enum import Enum
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication


class ThemeMode(Enum):
    DARK = 'dark'
    LIGHT = 'light'


class ThemeManager(QObject):
    theme_changed = Signal(object)
    DARK_COLORS = dict(background='#0c111b', surface='#141c29', surface_variant='#1d293b',
        text='#e9eff8', text_secondary='#92a1b8', border='#29374b', primary='#57d6bd',
        primary_hover='#7be5d0', on_primary='#0a2922', focus_ring='#57d6bd')
    LIGHT_COLORS = dict(background='#eef3f7', surface='#ffffff', surface_variant='#e3ecf2',
        text='#18273b', text_secondary='#5b6d81', border='#c5d2dd', primary='#087c66',
        primary_hover='#096653', on_primary='#ffffff', focus_ring='#087c66')

    def __init__(self, mode=ThemeMode.DARK):
        super().__init__()
        self._mode = mode

    def get_color(self, name):
        return (self.DARK_COLORS if self._mode == ThemeMode.DARK else self.LIGHT_COLORS).get(name, '#ffffff')

    def set_mode(self, mode):
        self._mode = mode
        self.theme_changed.emit(mode)

    def toggle(self):
        self.set_mode(ThemeMode.LIGHT if self._mode == ThemeMode.DARK else ThemeMode.DARK)

    def get_stylesheet(self):
        c = self.DARK_COLORS if self._mode == ThemeMode.DARK else self.LIGHT_COLORS
        return f'''
        QWidget {{ background: {c['background']}; color: {c['text']}; font-size: 13px; }}
        QLabel {{ background: transparent; }}
        QLabel#brand {{ font-size: 23px; font-weight: 700; }}
        QLabel#sectionTitle {{ font-size: 17px; font-weight: 600; }}
        QLabel#muted {{ color: {c['text_secondary']}; }}
        QFrame#header, QWidget#workspaceCard {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; }}
        QPushButton {{ background: {c['surface_variant']}; border: 1px solid {c['border']}; border-radius: 7px; padding: 9px 12px; font-weight: 600; }}
        QPushButton:hover {{ border-color: {c['primary']}; }}
        QPushButton:pressed {{ background: {c['primary']}; color: {c['on_primary']}; }}
        QPushButton:disabled {{ color: {c['text_secondary']}; background: {c['surface']}; }}
        QPushButton#primaryButton {{ background: {c['primary']}; color: {c['on_primary']}; border: none; }}
        QPushButton#primaryButton:hover {{ background: {c['primary_hover']}; }}
        QPushButton#emergencyButton {{ color: #ffbcc2; background: #42202b; border: 1px solid #7b3448; }}
        QPushButton#emergencyButton:hover {{ background: #642b39; }}
        QLineEdit, QSpinBox, QComboBox {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 7px; min-height: 20px; }}
        QComboBox QAbstractItemView {{ background: {c['surface']}; selection-background-color: {c['surface_variant']}; }}
        QPushButton:focus, QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {c['focus_ring']}; }}
        QGroupBox {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; margin-top: 12px; padding: 16px 10px 10px; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 15px; padding: 0 5px; color: {c['text_secondary']}; font-weight: 600; }}
        QScrollArea {{ border: none; }}
        QTabWidget::pane {{ border: none; background: {c['surface']}; }}
        QTabBar::tab {{ background: {c['background']}; color: {c['text_secondary']}; padding: 12px 14px; border-bottom: 2px solid transparent; }}
        QTabBar::tab:selected {{ color: {c['primary']}; border-bottom-color: {c['primary']}; }}
        QTabBar::tab:hover {{ color: {c['text']}; }}
        QCheckBox {{ spacing: 8px; }}
        QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {c['border']}; background: {c['surface_variant']}; }}
        QCheckBox::indicator:checked {{ background: {c['primary']}; }}
        QSlider::groove:horizontal {{ background: {c['border']}; height: 5px; border-radius: 2px; }}
        QSlider::sub-page:horizontal {{ background: {c['primary']}; border-radius: 2px; }}
        QSlider::handle:horizontal {{ background: {c['primary']}; width: 14px; margin: -5px 0; border-radius: 7px; }}
        QScrollBar:vertical {{ background: transparent; width: 8px; }}
        QScrollBar::handle:vertical {{ background: {c['border']}; min-height: 24px; border-radius: 4px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QSplitter::handle {{ background: {c['background']}; width: 12px; }}
        QMenuBar, QMenu, QStatusBar {{ background: {c['background']}; color: {c['text_secondary']}; }}
        QMenu::item:selected {{ background: {c['surface_variant']}; color: {c['text']}; }}
        QToolTip {{ background: {c['surface_variant']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 6px; }}
        '''

    def apply(self, app):
        app.setStyle('Fusion')
        app.setFont(QFont('Inter', 10))
        app.setStyleSheet(self.get_stylesheet())
