"""Main dashboard window: a grid of glass widgets on a (native or simulated) blurred backdrop."""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent, QMouseEvent, QPainter
from PySide6.QtWidgets import QGridLayout, QMenu, QVBoxLayout, QWidget

from .. import __app_name__, __version__
from ..collectors import Snapshot
from ..history import History
from ..layout import DEFAULT_LAYOUT, LayoutStore, WidgetConfig
from . import glass
from .theme import Theme, resolve_theme
from .widget_menu import populate_layout_menu, populate_widget_menu
from .widgets import GAP, MARGIN, BaseCard, PingCard, build_widgets

COLUMNS = 4
WINDOW_PAD = 20      # visible distance between the window edge and the widgets


class Dashboard(QWidget):
    def __init__(self, theme_setting: str = "system", ping_label: str = "1.1.1.1",
                 hide_on_close: bool = False, use_glass: bool = True, store: Optional[LayoutStore] = None,
                 layout: Optional[List[WidgetConfig]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{__app_name__} {__version__}")
        self.hide_on_close = hide_on_close
        self.theme_setting = theme_setting
        self.theme: Theme = resolve_theme(theme_setting)
        self.ping_label = ping_label
        self.store = store
        self.cards: List[BaseCard] = []
        self._last: Optional[Tuple[Snapshot, History]] = None
        self.native_glass = False          # True once a native blur view is installed
        self._use_glass = use_glass
        self.desktop_mode = False          # frameless widgets that sit on the desktop
        self.on_moved: Optional[Callable[[int, int], None]] = None    # called (debounced) after the user moved it
        self._move_timer = QTimer(self)
        self._move_timer.setSingleShot(True)
        self._move_timer.setInterval(400)
        self._move_timer.timeout.connect(self._emit_moved)
        self._want_native = use_glass and glass.native_blur_supported()
        if self._want_native:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        root = QVBoxLayout(self)
        m = WINDOW_PAD - MARGIN
        root.setContentsMargins(m, m, m, m)
        root.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        self.grid = QGridLayout()
        self.grid.setSpacing(GAP - 2 * MARGIN)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        root.addLayout(self.grid)

        self.set_layout(layout or (store.layout if store else DEFAULT_LAYOUT))
        if store is not None:      # rebuild later (not inside a menu handler that is still running)
            store.subscribe(lambda lay: QTimer.singleShot(0, lambda: self.set_layout(lay)))

    # widgets ---------------------------------------------------------------
    def set_layout(self, layout: List[WidgetConfig]) -> None:
        """(Re)build the widget grid for ``layout``."""
        for card in self.cards:
            self.grid.removeWidget(card)
            card.hide()
            card.deleteLater()
        self.cards = build_widgets(layout)
        row = col = 0
        for i, card in enumerate(self.cards):
            if col + card.cols > COLUMNS:
                row, col = row + 1, 0
            self.grid.addWidget(card, row, col, card.rows, card.cols)
            col += card.cols
            card.set_theme(self.theme)
            if isinstance(card, PingCard):
                card.host_label = self.ping_label
            if self.store is not None:
                card.context_requested = lambda pos, i=i: self.show_widget_menu(i, pos)
            if self._last:
                card.update_data(*self._last)
            card.show()
        self.adjustSize()
        self.updateGeometry()

    def card_for(self, metric_id: str) -> Optional[BaseCard]:
        """First widget that shows ``metric_id``."""
        for card in self.cards:
            if metric_id in getattr(card, "metric_ids", [card.metric_id]):
                return card
        return None

    def show_widget_menu(self, index: int, global_pos) -> None:
        if self.store is None:
            return
        menu = QMenu(self)
        populate_widget_menu(menu, self.store, index)
        menu.addSeparator()
        populate_layout_menu(menu, self.store)
        menu.exec(global_pos)

    # desktop mode ----------------------------------------------------------
    def set_desktop_mode(self, enabled: bool) -> None:
        """Desktop mode: no frame, no backdrop, behind other windows - the glass cards float on the desktop.

        Live like the normal window (same update timer), so this is the way to get widgets that really tick
        every second - the macOS widget gallery cannot do that.
        """
        enabled = bool(enabled)
        if enabled == self.desktop_mode:
            return
        self.desktop_mode = enabled
        was_visible = self.isVisible()
        flags = Qt.WindowType.Window
        if enabled:
            flags |= Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnBottomHint
        self.setWindowFlags(flags)              # re-creates the native window (also drops a native blur view)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, enabled or self._use_glass and glass.native_blur_supported())
        self.native_glass = False
        self._want_native = (not enabled) and self._use_glass and glass.native_blur_supported()
        if was_visible:
            self.show()
        self.update()

    def _emit_moved(self) -> None:
        if self.on_moved is not None:
            self.on_moved(self.x(), self.y())

    def moveEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().moveEvent(event)
        if self.isVisible():
            self._move_timer.start()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt API)
        # without a title bar the widgets are dragged by their background / any card
        if self.desktop_mode and event.button() == Qt.MouseButton.LeftButton:
            handle = self.windowHandle()
            if handle is not None and handle.startSystemMove():
                return
        super().mousePressEvent(event)

    # theme -----------------------------------------------------------------
    def set_theme(self, theme_setting: str) -> None:
        self.theme_setting = theme_setting
        self.theme = resolve_theme(theme_setting)
        for card in self.cards:
            card.set_theme(self.theme)
        win = getattr(self, "_iox_effect_window", None)
        if win is not None:
            glass.set_native_appearance(win, theme_setting)
        self.update()

    # window ----------------------------------------------------------------
    def showEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().showEvent(event)
        if self._want_native and not self.native_glass:
            self.native_glass = glass.apply_native_blur(self, self.theme_setting)
            self._want_native = False      # only try once
            self.update()
        if self.desktop_mode:
            glass.set_desktop_behavior(self, True)

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt API)
        if self.desktop_mode:           # nothing behind the cards: the desktop shines through
            return
        p = QPainter(self)
        glass.paint_backdrop(p, self.rect(), self.theme, self.native_glass)
        p.end()

    def update_data(self, snap: Snapshot, hist: History) -> None:
        self._last = (snap, hist)
        for card in self.cards:
            card.update_data(snap, hist)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt API)
        if self.hide_on_close:
            event.ignore()
            self.hide()
        else:
            event.accept()
