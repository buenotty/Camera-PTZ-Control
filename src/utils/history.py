"""
Histórico de configurações de imagem com suporte a desfazer e refazer (undo/redo).
"""

from PySide6.QtCore import QObject, Signal
from typing import Optional
from copy import deepcopy
from src.core.models import ImageSettings

class SettingsHistory(QObject):
    """
    Pilha de desfazer/refazer para as configurações de imagem.
    """
    history_changed = Signal(bool, bool)  # (can_undo, can_redo)

    def __init__(self, max_states: int = 50) -> None:
        """
        Inicializa o histórico.

        Args:
            max_states: Número máximo de estados mantidos no histórico.
        """
        super().__init__()
        self._states: list[ImageSettings] = []
        self._current_index: int = -1
        self._max_states: int = max_states

    def push(self, state: ImageSettings) -> None:
        """
        Adiciona um novo estado ao histórico. Trunca o histórico de refazer.

        Args:
            state: O estado (ImageSettings) a ser adicionado.
        """
        # Remove any states after current index
        self._states = self._states[:self._current_index + 1]
        self._states.append(deepcopy(state))
        # Enforce max size
        if len(self._states) > self._max_states:
            self._states.pop(0)
        else:
            self._current_index += 1
        self.history_changed.emit(self.can_undo, self.can_redo)

    def undo(self) -> Optional[ImageSettings]:
        """
        Desfaz a última alteração e retorna o estado anterior.

        Returns:
            ImageSettings: O estado desfeito, ou None se não for possível.
        """
        if not self.can_undo:
            return None
        self._current_index -= 1
        self.history_changed.emit(self.can_undo, self.can_redo)
        return deepcopy(self._states[self._current_index])

    def redo(self) -> Optional[ImageSettings]:
        """
        Refaz a última alteração desfeita e retorna o estado.

        Returns:
            ImageSettings: O estado refeito, ou None se não for possível.
        """
        if not self.can_redo:
            return None
        self._current_index += 1
        self.history_changed.emit(self.can_undo, self.can_redo)
        return deepcopy(self._states[self._current_index])

    @property
    def can_undo(self) -> bool:
        """Indica se é possível realizar um 'undo'."""
        return self._current_index > 0

    @property
    def can_redo(self) -> bool:
        """Indica se é possível realizar um 'redo'."""
        return self._current_index < len(self._states) - 1

    def clear(self) -> None:
        """Limpa todo o histórico."""
        self._states.clear()
        self._current_index = -1
        self.history_changed.emit(self.can_undo, self.can_redo)

    def current(self) -> Optional[ImageSettings]:
        """
        Retorna o estado atual no histórico sem alterar a posição.

        Returns:
            ImageSettings: O estado atual, ou None se o histórico estiver vazio.
        """
        if self._current_index >= 0 and self._current_index < len(self._states):
            return deepcopy(self._states[self._current_index])
        return None
