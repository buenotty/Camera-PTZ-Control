import logging
from typing import Optional, List
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QAction, QIcon
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QGridLayout, QMenu, QInputDialog, QMessageBox, QPushButton
)

# Mock definitions for src.core.models to ensure typing works
from src.core.models import Preset

logger = logging.getLogger(__name__)

class PresetCard(QFrame):
    """
    Cartão visual para gerenciar e chamar um preset.
    """

    # Signals
    recalled = Signal(int)
    deleted = Signal(int)
    renamed = Signal(int, str)
    saved_current = Signal(int)

    def __init__(self, preset: Preset, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.preset = preset
        self.is_active = False

        self.setFixedSize(120, 100)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self.init_ui()
        self.update_style()

    def init_ui(self):
        """Inicializa a interface do cartão de preset."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # Header: badge + type icon
        header_layout = QHBoxLayout()
        self.lbl_number = QLabel(str(self.preset.number))
        self.lbl_number.setStyleSheet("font-weight: bold; font-size: 14px;")

        icon = "🔧" if self.preset.is_hardware else "💾"
        self.lbl_type = QLabel(icon)

        header_layout.addWidget(self.lbl_number)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_type)
        layout.addLayout(header_layout)

        # Thumbnail
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if hasattr(self.preset, 'thumbnail_path') and self.preset.thumbnail_path and Path(self.preset.thumbnail_path).exists():
            pixmap = QPixmap(self.preset.thumbnail_path).scaled(
                100, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_thumb.setPixmap(pixmap)
        else:
            self.lbl_thumb.setText("Sem foto")
            self.lbl_thumb.setStyleSheet("color: gray;")
        layout.addWidget(self.lbl_thumb)

        # Name
        self.lbl_name = QLabel(self.preset.name)
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_name)

    def update_style(self):
        """Atualiza a aparência baseada no estado."""
        bg_color = "#141c29"
        border_color = "#29374b"

        if self.is_active:
            border_color = "#57d6bd"
            bg_color = "#203b3b"
        elif self.hasFocus():
            border_color = "#57d6bd"

        style = f"""
            PresetCard {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 5px;
            }}
            PresetCard:hover {{
                background-color: #1d293b;
            }}
        """
        self.setStyleSheet(style)

    def set_active(self, active: bool):
        """Define se este preset é o último chamado."""
        self.is_active = active
        self.update_style()

    def update_thumbnail(self, pixmap: QPixmap):
        """Atualiza a miniatura visual do preset."""
        scaled = pixmap.scaled(100, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.lbl_thumb.setPixmap(scaled)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.recalled.emit(self.preset.number)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.recalled.emit(self.preset.number)
        elif event.key() == Qt.Key.Key_Delete:
            self.deleted.emit(self.preset.number)
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        self.update_style()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.update_style()
        super().focusOutEvent(event)

    def _show_context_menu(self, pos):
        """Exibe o menu de contexto com opções do preset."""
        menu = QMenu(self)

        act_rename = QAction("Renomear", self)
        act_rename.triggered.connect(self._rename_preset)

        act_save = QAction("Salvar Posição Atual", self)
        act_save.triggered.connect(lambda: self.saved_current.emit(self.preset.number))

        act_delete = QAction("Deletar", self)
        act_delete.triggered.connect(lambda: self.deleted.emit(self.preset.number))

        menu.addAction(act_rename)
        menu.addAction(act_save)
        menu.addSeparator()
        menu.addAction(act_delete)

        menu.exec(self.mapToGlobal(pos))

    def _rename_preset(self):
        new_name, ok = QInputDialog.getText(self, "Renomear Preset", "Novo nome:", text=self.preset.name)
        if ok and new_name:
            self.preset.name = new_name
            self.lbl_name.setText(new_name)
            self.renamed.emit(self.preset.number, new_name)


class PresetManagerPanel(QWidget):
    """
    Painel de gerenciamento de presets com grade de cartões.
    """

    preset_recalled = Signal(int)
    preset_saved = Signal(int, str)
    preset_deleted = Signal(int)
    preset_renamed = Signal(int, str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.cards = {}  # type: dict[int, PresetCard]
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Posições salvas")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")

        btn_new = QPushButton("+ Salvar posição")
        btn_new.clicked.connect(self._create_new_preset)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(btn_new)
        main_layout.addLayout(header_layout)

        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

    def load_presets(self, presets: List[Preset]):
        """Carrega uma lista de presets limpando os existentes."""
        for num in list(self.cards.keys()):
            self.remove_preset(num)

        for preset in presets:
            self.add_preset(preset)

    def add_preset(self, preset: Preset):
        """Adiciona ou atualiza um cartão de preset na grade."""
        if preset.number in self.cards:
            self.remove_preset(preset.number)

        card = PresetCard(preset)
        card.recalled.connect(self.preset_recalled.emit)
        card.deleted.connect(self.preset_deleted.emit)
        card.renamed.connect(self.preset_renamed.emit)
        card.saved_current.connect(lambda n: self.preset_saved.emit(n, card.preset.name))

        self.cards[preset.number] = card
        self._reorganize_grid()

    def remove_preset(self, number: int):
        """Remove o cartão de preset do painel."""
        if number in self.cards:
            card = self.cards.pop(number)
            self.grid_layout.removeWidget(card)
            card.deleteLater()
            self._reorganize_grid()

    def set_active_preset(self, number: int):
        """Destaca o preset atualmente ativo."""
        for num, card in self.cards.items():
            card.set_active(num == number)

    def update_thumbnail(self, number: int, pixmap: QPixmap):
        """Atualiza a miniatura de um preset existente."""
        if number in self.cards:
            self.cards[number].update_thumbnail(pixmap)

    def _reorganize_grid(self):
        """Reorganiza os widgets no layout de grade de 4 colunas."""
        # Remover todos os widgets do layout
        for i in reversed(range(self.grid_layout.count())):
            self.grid_layout.itemAt(i).widget().setParent(None)

        # Adicionar de volta na ordem
        col_count = 4
        for idx, number in enumerate(sorted(self.cards.keys())):
            row = idx // col_count
            col = idx % col_count
            self.grid_layout.addWidget(self.cards[number], row, col)

    def _create_new_preset(self):
        """Cria um novo preset buscando o primeiro número disponível."""
        available_number = 1
        while available_number in self.cards and available_number <= 255:
            available_number += 1

        if available_number > 255:
            QMessageBox.warning(self, "Erro", "Limite máximo de 255 presets atingido.")
            return

        name, ok = QInputDialog.getText(self, "Novo Preset", "Nome do preset:")
        if ok and name:
            self.preset_saved.emit(available_number, name)
