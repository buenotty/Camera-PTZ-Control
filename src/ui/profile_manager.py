"""Local image profiles. Passwords are never included in saved/exported profiles."""
from pathlib import Path
import json
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QInputDialog, QFileDialog, QMessageBox
from src.core.models import Profile
from src.utils.settings import SettingsManager


class ProfileManager(QObject):
    profile_loaded = Signal(object)
    profile_saved = Signal(str)
    profiles_changed = Signal(list)

    def __init__(self, parent=None, directory=None):
        super().__init__(parent)
        self.profiles_dir = Path(directory) if directory else SettingsManager().settings_dir / 'profiles'
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        if not name.strip() or name in ('.', '..') or any(c in name for c in '/\\'):
            raise ValueError('Nome de perfil inválido')
        return self.profiles_dir / f'{name}.json'

    def list_profiles(self):
        return sorted(p.stem for p in self.profiles_dir.glob('*.json'))

    def load_profile(self, name):
        profile = Profile.load(self._path(name))
        self.profile_loaded.emit(profile)
        return profile

    def save_profile(self, profile):
        self._path(profile.name)
        profile.save(self.profiles_dir)
        self.profile_saved.emit(profile.name)
        self.profiles_changed.emit(self.list_profiles())

    def delete_profile(self, name):
        self._path(name).unlink(missing_ok=True)
        self.profiles_changed.emit(self.list_profiles())

    def export_profile(self, name, destination):
        # Re-serialize older profiles too, so old credentials cannot leak.
        profile = Profile.load(self._path(name))
        Path(destination).write_text(json.dumps(profile.to_dict(), indent=2, ensure_ascii=False), encoding='utf-8')

    def import_profile(self, source):
        profile = Profile.load(Path(source))
        name = profile.name
        self._path(name)
        index = 1
        while self._path(profile.name).exists():
            profile.name = f'{name}_{index}'
            index += 1
        self.save_profile(profile)
        return profile.name


class ProfileManagerWidget(QWidget):
    save_requested = Signal(str)

    def __init__(self, manager=None, parent=None):
        super().__init__(parent)
        self.manager = manager or ProfileManager(self)
        self.current_profile = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        self.cb_profiles = QComboBox()
        self.cb_profiles.setPlaceholderText('Selecione um perfil salvo')
        layout.addWidget(self.cb_profiles)
        for items in [[('Carregar', self._load), ('Salvar ajustes atuais', self._save)],
                      [('Importar', self._import_profile), ('Exportar', self._export_profile)],
                      [('Excluir perfil', self._delete_profile)]]:
            row = QHBoxLayout()
            for label, callback in items:
                button = QPushButton(label)
                button.clicked.connect(callback)
                row.addWidget(button)
            layout.addLayout(row)
        self.manager.profiles_changed.connect(self._update_combobox)
        self.manager.profile_loaded.connect(self._on_profile_loaded)
        self._update_combobox(self.manager.list_profiles())

    def _update_combobox(self, profiles):
        current = self.cb_profiles.currentText()
        self.cb_profiles.clear()
        self.cb_profiles.addItems(profiles)
        if current in profiles:
            self.cb_profiles.setCurrentText(current)

    def _on_profile_loaded(self, profile):
        self.current_profile = profile

    def _load(self):
        name = self.cb_profiles.currentText()
        if name:
            try:
                self.manager.load_profile(name)
            except (ValueError, OSError, KeyError, TypeError):
                QMessageBox.warning(self, 'Perfil inválido', 'Não foi possível carregar este perfil.')

    def _save(self):
        name, ok = QInputDialog.getText(self, 'Salvar perfil', 'Nome do perfil:', text=self.cb_profiles.currentText())
        if ok and name.strip():
            if name in self.manager.list_profiles() and QMessageBox.question(self, 'Substituir perfil',
                f"Substituir os ajustes de '{name}'?") != QMessageBox.StandardButton.Yes:
                return
            self.save_requested.emit(name.strip())

    def _delete_profile(self):
        name = self.cb_profiles.currentText()
        if name and QMessageBox.question(self, 'Excluir perfil', f"Excluir '{name}'?") == QMessageBox.StandardButton.Yes:
            self.manager.delete_profile(name)

    def _import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Importar perfil', '', 'Perfil JSON (*.json)')
        if path:
            try:
                name = self.manager.import_profile(path)
                self.cb_profiles.setCurrentText(name)
            except (ValueError, OSError, KeyError, TypeError):
                QMessageBox.warning(self, 'Perfil inválido', 'Não foi possível importar este perfil.')

    def _export_profile(self):
        name = self.cb_profiles.currentText()
        if name:
            path, _ = QFileDialog.getSaveFileName(self, 'Exportar perfil', f'{name}.json', 'Perfil JSON (*.json)')
            if path:
                self.manager.export_profile(name, path)
