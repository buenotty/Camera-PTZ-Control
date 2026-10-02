from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QWidget, QPushButton, QGridLayout, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
import typing

class KeyBadge(QLabel):
    """
    Componente visual que representa uma tecla do teclado.
    """
    def __init__(self, text: str, parent: typing.Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                font-family: 'Courier New', monospace;
                font-weight: bold;
                margin: 2px;
            }
        """)

class ShortcutRow(QWidget):
    """
    Linha da tabela de atalhos, contendo a combinação de teclas e sua descrição.
    """
    def __init__(self, keys: list[str], description: str, parent: typing.Optional[QWidget] = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        keys_layout = QHBoxLayout()
        keys_layout.setSpacing(4)
        for i, key in enumerate(keys):
            keys_layout.addWidget(KeyBadge(key))
            if i < len(keys) - 1 and key != "/":
                if keys[i+1] == "/":
                    slash_label = QLabel("/")
                    slash_label.setStyleSheet("color: palette(text); font-weight: bold;")
                    keys_layout.addWidget(slash_label)
                elif key != "/":
                    plus_label = QLabel("+")
                    plus_label.setStyleSheet("color: palette(text); font-weight: bold;")
                    keys_layout.addWidget(plus_label)

        keys_widget = QWidget()
        keys_widget.setLayout(keys_layout)
        keys_widget.setMinimumWidth(150)

        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: palette(text); font-size: 10pt;")

        layout.addWidget(keys_widget)
        layout.addWidget(desc_label, 1) # Description takes remaining space

class KeyboardOverlayDialog(QDialog):
    """
    Diálogo modal que exibe todos os atalhos de teclado disponíveis na aplicação.
    """
    def __init__(self, parent: typing.Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Atalhos de Teclado")
        self.setFixedSize(600, 500)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Configura a interface de usuário do diálogo."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Atalhos de Teclado")
        title_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(10)

        sections = [
            ("Movimento PTZ", [
                (["W", "/", "↑"], "Mover para Cima"),
                (["S", "/", "↓"], "Mover para Baixo"),
                (["A", "/", "←"], "Mover para Esquerda"),
                (["D", "/", "→"], "Mover para Direita"),
                (["Q"], "Mover Diagonal Cima-Esquerda"),
                (["E"], "Mover Diagonal Cima-Direita"),
                (["Z"], "Mover Diagonal Baixo-Esquerda"),
                (["C"], "Mover Diagonal Baixo-Direita"),
                (["Space"], "Parar Movimento")
            ]),
            ("Zoom", [
                (["+", "/", "PageUp"], "Aumentar Zoom (In)"),
                (["-", "/", "PageDown"], "Diminuir Zoom (Out)")
            ]),
            ("Foco", [
                (["F"], "Auto Foco"),
                (["["], "Foco Perto"),
                (["]"], "Foco Longe")
            ]),
            ("Presets", [
                (["1-9"], "Chamar Preset"),
                (["Ctrl", "1-9"], "Salvar Preset")
            ]),
            ("Gravação", [
                (["Ctrl", "Shift", "R"], "Iniciar/Parar Gravação"),
                (["Ctrl", "P"], "Tirar Foto (Snapshot)")
            ]),
            ("Visualização", [
                (["G"], "Alternar Grade"),
                (["F11"], "Alternar Tela Cheia")
            ]),
            ("Ajustes", [
                (["Ctrl", "Z"], "Desfazer Ajuste"),
                (["Ctrl", "Y"], "Refazer Ajuste"),
                (["Ctrl", "R"], "Ler Parâmetros da Câmera")
            ]),
            ("Geral", [
                (["F1"], "Mostrar Atalhos de Teclado"),
                (["Ctrl", "T"], "Iniciar/Parar Tour"),
                (["Esc"], "Fechar Janela / Sair do Modo")
            ])
        ]

        for section_title, shortcuts in sections:
            sec_label = QLabel(section_title)
            sec_font = QFont("Segoe UI", 12, QFont.Weight.Bold)
            sec_label.setFont(sec_font)
            sec_label.setStyleSheet("color: palette(highlight); margin-top: 10px;")
            content_layout.addWidget(sec_label)

            for keys, desc in shortcuts:
                content_layout.addWidget(ShortcutRow(keys, desc))

        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

        close_btn = QPushButton("Fechar")
        close_btn.setMinimumHeight(35)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)

    def keyPressEvent(self, event) -> None:
        """Sobrescreve evento de teclado para fechar com Esc."""
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)
