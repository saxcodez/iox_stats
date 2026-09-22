"""Qt side of the CPU temperature helper setup: ask once, install in the background, report the result."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from .. import __app_name__, helpers


class HelperSetup(QObject):
    """Finds / installs the tool that reads the CPU temperature on macOS (see ``iox_stats.helpers``)."""

    done = Signal(bool, str)          # (ok, message) - emitted on the UI thread

    def __init__(self, on_installed: Optional[Callable[[], None]] = None,
                 status_fn: Callable[[], helpers.HelperStatus] = helpers.status,
                 install_fn: Callable = helpers.install_async, parent=None):
        super().__init__(parent)
        self._on_installed = on_installed
        self._status_fn = status_fn
        self._install_fn = install_fn
        self.busy = False
        self.last_message = ""
        self.done.connect(self._finished)      # queued onto the UI thread when emitted from the worker thread

    # -- state ---------------------------------------------------------------
    def status(self) -> helpers.HelperStatus:
        return self._status_fn()

    @property
    def available(self) -> bool:
        """True on systems that need a helper at all (macOS)."""
        return self.status().supported

    def menu_text(self) -> str:
        st = self.status()
        if self.busy:
            return f"Installing {st.recommended}..."
        return st.summary() if st.ready else "Set Up CPU Temperature..."

    # -- actions -------------------------------------------------------------
    def start_install(self) -> bool:
        """Begin installing the recommended helper in the background. False if not possible / already running."""
        st = self.status()
        if self.busy or not st.can_install:
            return False
        self.busy = True
        self._install_fn(st, lambda ok, msg: self.done.emit(ok, msg))
        return True

    def _finished(self, ok: bool, message: str) -> None:
        self.busy = False
        self.last_message = message
        if ok and self._on_installed:
            self._on_installed()
        self.notify(ok, message)

    # -- dialogs (overridable in tests) ----------------------------------------
    def confirm(self, st: helpers.HelperStatus, parent=None) -> bool:
        box = QMessageBox(QMessageBox.Icon.Question, __app_name__, "Show the CPU temperature?",
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, parent)
        box.setInformativeText(
            f"macOS gives apps no direct access to the temperature. IOX Stats can install the small tool "
            f"\"{st.recommended}\" with Homebrew for that.\n\nNo driver, no administrator password. "
            f"It runs quietly in the background and can be removed at any time with "
            f"\"brew uninstall {st.recommended}\".")
        box.setDefaultButton(QMessageBox.StandardButton.Yes)
        return box.exec() == QMessageBox.StandardButton.Yes

    def explain_homebrew(self, st: helpers.HelperStatus, parent=None) -> None:
        box = QMessageBox(QMessageBox.Icon.Information, __app_name__, "Homebrew is needed for the temperature",
                          QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Close, parent)
        box.setInformativeText(
            f"The CPU temperature needs the tool \"{st.recommended}\", which is installed with Homebrew "
            f"({helpers.BREW_URL}). Install Homebrew first, then choose \"Set Up CPU Temperature...\" again.")
        if box.exec() == QMessageBox.StandardButton.Open:
            QDesktopServices.openUrl(QUrl(helpers.BREW_URL))

    def notify(self, ok: bool, message: str, parent=None) -> None:
        icon = QMessageBox.Icon.Information if ok else QMessageBox.Icon.Warning
        box = QMessageBox(icon, __app_name__, "CPU temperature is set up" if ok else "Could not set up the temperature",
                          QMessageBox.StandardButton.Ok, parent)
        box.setInformativeText(message)
        box.exec()

    def run(self, parent=None) -> None:
        """Menu action / first-run question: explain, ask, install."""
        st = self.status()
        if not st.supported or st.tool or self.busy:
            return
        if st.needs_homebrew:
            self.explain_homebrew(st, parent)
        elif self.confirm(st, parent):
            self.start_install()
