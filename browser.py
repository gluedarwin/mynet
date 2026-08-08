"""
MyNet Browser — Lightweight browser for the MNET protocol.
Uses PyQt6 for the GUI.
"""

import sys
import os
import json
import ssl
import socket
import threading
import re
import html as html_module
import shutil
import subprocess

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabBar, QToolButton, QLineEdit, QPushButton, QLabel,
    QScrollArea, QStyle, QStyleOption, QStyleFactory, QFrame,
    QMenu, QMenuBar, QMessageBox, QDialog, QFormLayout,
    QTextEdit, QFileDialog, QTextBrowser, QSizePolicy,
)
from PyQt6.QtGui import (
    QFont, QIcon, QPalette, QColor, QAction,
    QDesktopServices, QPixmap, QCursor,
)
from PyQt6.QtCore import Qt, QUrl, QSize, QMargins

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mynet

DATA_DIR = mynet.BROWSER_DATA_DIR
BOOKMARKS_FILE = os.path.join(DATA_DIR, "bookmarks.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
TABS_FILE = os.path.join(DATA_DIR, "tabs.json")

SIZES = mynet.BROWSER_SIZE_MAP


def _load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default or []


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Tab:
    __slots__ = ("url", "title", "source", "headers")

    def __init__(self, url="", title="New Tab", source="", headers=None):
        self.url = url
        self.title = title
        self.source = source
        self.headers = headers or {}


class HTMLRenderer:
    """Convert MNET response source (HTML) into Qt widgets."""

    def __init__(self, parent_widget, zoom=14, on_link_click=None):
        self.parent = parent_widget
        self.zoom = zoom
        self.on_link_click = on_link_click or (lambda url: None)

    def clear(self):
        while self.parent.layout().count():
            child = self.parent.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def render(self, source):
        self.clear()
        if not source:
            return

        elements = self._parse_html(source)
        for el in elements:
            self._render_element(el)

    def _parse_html(self, source):
        from html.parser import HTMLParser

        elements = []

        class Parser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []

            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                el = {"tag": tag, "text": "", "attrs": attrs_dict, "children": []}
                if self.stack:
                    self.stack[-1]["children"].append(el)
                else:
                    elements.append(el)
                if tag not in ("br", "hr", "img", "input"):
                    self.stack.append(el)

            def handle_endtag(self, tag):
                if self.stack and self.stack[-1]["tag"] == tag:
                    self.stack.pop()

            def handle_data(self, data):
                if self.stack:
                    self.stack[-1]["text"] += data
                else:
                    if data.strip():
                        elements.append({"tag": "p", "text": data.strip(), "attrs": {}, "children": []})

        parser = Parser()
        parser.feed(source)
        return elements

    def _apply_inline(self, text):
        text = re.sub(r'<strong>(.*?)</strong>', r'<b>\1</b>', text)
        text = re.sub(r'<em>(.*?)</em>', r'<i>\1</i>', text)
        return text

    def _render_element(self, el):
        tag = el["tag"]
        text = el.get("text", "")
        attrs = el.get("attrs", {})
        children = el.get("children", [])

        if tag in SIZES:
            font = QFont("Arial", SIZES[tag])
            font.setBold(True)
            lbl = QLabel(text)
            lbl.setFont(font)
            lbl.setWordWrap(True)
            self.parent.layout().addWidget(lbl)

        elif tag == "p":
            lbl = QLabel(text)
            lbl.setFont(QFont("Arial", self.zoom))
            lbl.setWordWrap(True)
            self.parent.layout().addWidget(lbl)

        elif tag == "br":
            self.parent.layout().addSpacing(10)

        elif tag == "ul":
            for ch in children:
                if ch["tag"] == "li":
                    lbl = QLabel(f"•  {ch['text']}")
                    lbl.setWordWrap(True)
                    self.parent.layout().addWidget(lbl)

        elif tag == "ol":
            for i, ch in enumerate(children, 1):
                if ch["tag"] == "li":
                    lbl = QLabel(f"{i}.  {ch['text']}")
                    lbl.setWordWrap(True)
                    self.parent.layout().addWidget(lbl)

        elif tag == "hr":
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            self.parent.layout().addWidget(line)

        elif tag == "a":
            href = attrs.get("href", attrs.get("_0", ""))
            text_content = text or href
            btn = QPushButton(text_content)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet("text-align: left; padding: 2px;")
            btn.clicked.connect(lambda _, u=href: self.on_link_click(u))
            self.parent.layout().addWidget(btn)

        elif tag == "img":
            src = attrs.get("src", attrs.get("_0", ""))
            lbl = QLabel(f"[image: {src}]")
            lbl.setStyleSheet("color: #888;")
            self.parent.layout().addWidget(lbl)

        elif tag == "pre":
            lbl = QLabel(text)
            lbl.setFont(QFont("monospace", max(11, self.zoom - 1)))
            lbl.setStyleSheet("background: #1e1e2e; padding: 8px;")
            lbl.setTextFormat(Qt.TextFormat.PlainText)
            self.parent.layout().addWidget(lbl)

        elif tag == "code":
            if children and children[0]["tag"] in ("pre",):
                pass
            else:
                lbl = QLabel(text)
                lbl.setFont(QFont("monospace", max(11, self.zoom - 1)))
                lbl.setStyleSheet("background: #1e1e2e; padding: 4px;")
                self.parent.layout().addWidget(lbl)

        elif tag == "blockquote":
            lbl = QLabel(text)
            lbl.setStyleSheet("border-left: 3px solid #555; padding-left: 12px; color: #aaa;")
            lbl.setWordWrap(True)
            self.parent.layout().addWidget(lbl)

        elif tag in ("video", "audio"):
            src = attrs.get("src", attrs.get("_0", ""))
            lbl = QLabel(f"[media: {src}]")
            lbl.setStyleSheet("color: #888;")
            self.parent.layout().addWidget(lbl)

        else:
            for ch in children:
                self._render_element(ch)
            if text and tag == "body":
                lbl = QLabel(text)
                lbl.setWordWrap(True)
                self.parent.layout().addWidget(lbl)


class MyNetBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MyNet Browser")
        self.resize(1024, 700)
        self.setMinimumSize(600, 400)

        self.tabs = [Tab()]
        self.tab_index = 0
        self.zoom = 14
        self.theme = "dark"
        self.auth_token = ""
        self.bookmarks = _load_json(BOOKMARKS_FILE)
        self.history = _load_json(HISTORY_FILE)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        self.tab_bar = QTabBar()
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.tabCloseRequested.connect(self._on_tab_close_requested)

        self.add_tab_btn = QToolButton()
        self.add_tab_btn.setText("+")
        self.add_tab_btn.setToolTip("New Tab (Ctrl+T)")
        self.add_tab_btn.setFixedSize(28, 24)
        self.add_tab_btn.clicked.connect(self._new_tab)

        tab_nav = QHBoxLayout()
        tab_nav.setSpacing(2)
        tab_nav.setContentsMargins(0, 0, 0, 0)
        tab_nav.addWidget(self.tab_bar, 1)
        tab_nav.addWidget(self.add_tab_btn)
        main_layout.addLayout(tab_nav)

        nav = QHBoxLayout()
        nav.setSpacing(4)
        nav.setContentsMargins(0, 0, 0, 0)

        self.back_btn = QToolButton()
        self.back_btn.setText("◀")
        self.back_btn.setFixedSize(28, 28)
        self.back_btn.clicked.connect(self._back)
        self.back_btn.setToolTip("Back (Ctrl+[)")
        nav.addWidget(self.back_btn)

        self.fwd_btn = QToolButton()
        self.fwd_btn.setText("▶")
        self.fwd_btn.setFixedSize(28, 28)
        self.fwd_btn.clicked.connect(self._fwd)
        self.fwd_btn.setToolTip("Forward (Ctrl+])")
        nav.addWidget(self.fwd_btn)

        self.refresh_btn = QToolButton()
        self.refresh_btn.setText("↻")
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.clicked.connect(self._refresh)
        self.refresh_btn.setToolTip("Refresh (F5)")
        nav.addWidget(self.refresh_btn)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("mynet://localhost:7443/")
        self.url_edit.returnPressed.connect(self._go)
        self.url_edit.setFixedHeight(28)
        nav.addWidget(self.url_edit, 1)

        self.go_btn = QToolButton()
        self.go_btn.setText("→")
        self.go_btn.setFixedSize(28, 28)
        self.go_btn.clicked.connect(self._go)
        self.go_btn.setToolTip("Go")
        nav.addWidget(self.go_btn)

        self.bookmark_btn = QToolButton()
        self.bookmark_btn.setText("☆")
        self.bookmark_btn.setFixedSize(28, 28)
        self.bookmark_btn.clicked.connect(self._toggle_bookmark)
        self.bookmark_btn.setToolTip("Toggle Bookmark")
        nav.addWidget(self.bookmark_btn)

        main_layout.addLayout(nav)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(2)
        toolbar.setContentsMargins(0, 0, 0, 0)

        for txt, cmd, tip in [
            ("🔍 Find", self._show_find, "Find (Cmd+F)"),
            ("📋 History", self._show_history, "History"),
            ("⭐ Marks", self._show_bookmarks, "Bookmarks"),
            ("📄 Source", self._view_source, "View Source"),
            ("💾 Save", self._save_page, "Save Page"),
            ("☀ Theme", self._toggle_theme, "Toggle Theme"),
            ("A+", self._zoom_in, "Zoom In"),
            ("A-", self._zoom_out, "Zoom Out"),
            ("⛶ Full", self._toggle_fullscreen, "Fullscreen"),
            ("📋URL", self._copy_url, "Copy URL"),
            ("🔐 Auth", self._show_auth, "Authentication"),
            ("📡 API", self._show_api_helper, "API Helper"),
            ("⬆ Upload", self._show_upload, "Upload File"),
        ]:
            btn = QToolButton()
            btn.setText(txt)
            btn.setFixedSize(70, 24)
            btn.setToolTip(tip)
            btn.clicked.connect(cmd)
            toolbar.addWidget(btn)

        main_layout.addLayout(toolbar)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(12, 12, 12, 12)
        self.content_layout.setSpacing(8)
        self.content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.content_widget)
        main_layout.addWidget(scroll, 1)

        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")
        main_layout.addWidget(self.status_bar)

        self._renderer = None
        self._update_tab_bar()
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        self._render_tab()

    def _update_tab_bar(self):
        while self.tab_bar.count() > 0:
            self.tab_bar.removeTab(0)
        for i, tab in enumerate(self.tabs):
            label = tab.title[:14] + "..." if len(tab.title) > 14 else tab.title or "New Tab"
            self.tab_bar.addTab(label)
        if self.tabs:
            self.tab_bar.setCurrentIndex(self.tab_index)

    def _on_tab_changed(self, idx):
        if 0 <= idx < len(self.tabs):
            self.tab_index = idx
            self._render_tab()

    def _render_tab(self):
        tab = self.tabs[self.tab_index]
        self.url_edit.setText(tab.url)
        self._update_bookmark_btn()
        self._clear_content()

        if tab.source:
            self._render_content(tab.source)
        else:
            self._show_welcome()

    def _render_content(self, source):
        self.status_bar.showMessage(f"Rendering {len(source)} bytes")
        self._renderer = HTMLRenderer(self.content_widget, self.zoom, on_link_click=self._open_url)
        self._renderer.render(mynet.parse_md(source))

    def _show_welcome(self):
        self._clear_content()

        title_label = QLabel("MyNet Browser")
        title_label.setStyleSheet("font-size: 32pt; font-weight: bold;")
        self.content_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignCenter)

        desc_label = QLabel("Enter a mynet:// URL")
        desc_label.setStyleSheet("font-size: 15pt;")
        self.content_layout.addWidget(desc_label, 0, Qt.AlignmentFlag.AlignCenter)

        help_label = QLabel(
            "Cmd+T: New Tab | Cmd+W: Close | Cmd+R: Refresh | Cmd+L: URL\n"
            "Cmd+F: Find | Ctrl+/-: Zoom | F5: Refresh | Esc: Fullscreen"
        )
        help_label.setStyleSheet("color: #888; font-size: 11pt;")
        self.content_layout.addWidget(help_label, 0, Qt.AlignmentFlag.AlignCenter)

    def _clear_content(self):
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _new_tab(self):
        self.tabs.append(Tab())
        self.tab_index = len(self.tabs) - 1
        self._update_tab_bar()
        self._render_tab()

    def _on_tab_close_requested(self, idx):
        if len(self.tabs) <= 1:
            return
        self.tabs.pop(idx)
        self.tab_index = min(self.tab_index, len(self.tabs) - 1)
        self._update_tab_bar()
        self._render_tab()

    def _go(self):
        raw = self.url_edit.text().strip()
        if not raw:
            return
        if not raw.startswith("mynet://"):
            raw = "mynet://" + raw

        tab = self.tabs[self.tab_index]
        if tab.url and (not self.history or self.history[-1] != raw):
            self.history.append(raw)
            _save_json(HISTORY_FILE, self.history)

        tab.url = raw
        self._update_tab_bar()
        self.status_bar.showMessage(f"Loading {raw}…")
        threading.Thread(target=self._fetch, args=(raw,), daemon=True).start()

    def _back(self):
        tab = self.tabs[self.tab_index]
        if tab.url in self.history:
            idx = self.history.index(tab.url)
            if idx > 0:
                self.url_edit.setText(self.history[idx - 1])
                self._go()

    def _fwd(self):
        tab = self.tabs[self.tab_index]
        if tab.url in self.history:
            idx = self.history.index(tab.url)
            if idx < len(self.history) - 1:
                self.url_edit.setText(self.history[idx + 1])
                self._go()

    def _refresh(self):
        tab = self.tabs[self.tab_index]
        if tab.url:
            self.status_bar.showMessage("Refreshing…")
            threading.Thread(target=self._fetch, args=(tab.url,), daemon=True).start()

    def _load(self, url):
        self.url_edit.setText(url)
        self._go()

    def _fetch(self, url):
        clean = url.replace("mynet://", "")
        hostport, *rest = clean.split("/", 1)
        path = "/" + rest[0] if rest else "/"
        if ":" in hostport:
            host, port = hostport.rsplit(":", 1)
            port = int(port)
        else:
            host, port = hostport, 7443

        try:
            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            resp = mynet.fetch(host, path, port, headers)
            src = resp.body.decode(errors="replace")
            tab = self.tabs[self.tab_index]

            tab.source = src
            tab.url = url
            tab.headers = resp.headers
            tab.title = resp.headers.get("Title", tab.title) or f"Page {self.tab_index + 1}"

            self._update_tab_bar()

            QApplication.postEvent(self, _RenderEvent(src, resp.status))
        except Exception as e:
            QApplication.postEvent(self, _ErrorEvent(str(e)))

    def _render_from_event(self, source, status):
        self._render_content(source)
        self.status_bar.showMessage(f"Done — [{status}]")

    def _show_error(self, msg):
        self._clear_content()
        lbl = QLabel(f"Error:\n{msg}")
        lbl.setStyleSheet("color: #ff5555; font-size: 14pt;")
        self.content_layout.addWidget(lbl, 0, Qt.AlignmentFlag.AlignCenter)
        self.status_bar.showMessage("Error")

    def _open(self, url):
        self.url_edit.setText(url)
        self._go()

    def _update_bookmark_btn(self):
        tab = self.tabs[self.tab_index]
        if tab.url and any(b.get("url") == tab.url for b in self.bookmarks):
            self.bookmark_btn.setText("★")
        else:
            self.bookmark_btn.setText("☆")

    def _toggle_bookmark(self):
        tab = self.tabs[self.tab_index]
        if not tab.url:
            return
        if any(b.get("url") == tab.url for b in self.bookmarks):
            self.bookmarks = [b for b in self.bookmarks if b.get("url") != tab.url]
            self.bookmark_btn.setText("☆")
        else:
            self.bookmarks.append({"url": tab.url, "title": tab.title})
            self.bookmark_btn.setText("★")
        _save_json(BOOKMARKS_FILE, self.bookmarks)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _copy_url(self):
        cb = QApplication.clipboard()
        cb.setText(self.url_edit.text())
        self.status_bar.showMessage("URL copied")

    def _zoom_in(self):
        self.zoom = min(28, self.zoom + 2)
        self._refresh()

    def _zoom_out(self):
        self.zoom = max(8, self.zoom - 2)
        self._refresh()

    def _toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self._apply_theme()

    def _apply_theme(self):
        if self.theme == "dark":
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(15, 15, 28))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
            palette.setColor(QPalette.ColorRole.Base, QColor(20, 20, 30))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(25, 25, 35))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 35))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 220))
            palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
            palette.setColor(QPalette.ColorRole.Button, QColor(26, 26, 46))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
            palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Link, QColor(79, 195, 247))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(79, 195, 247))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
        else:
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Base, QColor(250, 250, 250))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.BrightText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Link, QColor(65, 105, 225))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(65, 105, 225))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        QApplication.instance().setPalette(palette)

    def _show_find(self):
        text, ok = QInputDialog.getText(self, "Find", "Search:")
        if ok and text:
            tab = self.tabs[self.tab_index]
            count = tab.source.lower().count(text.lower()) if tab.source else 0
            self.status_bar.showMessage(f'Found {count} matches for "{text}"')

    def _show_bookmarks(self):
        self._clear_content()

        header = QHBoxLayout()
        header.addWidget(QLabel("Bookmarks"))
        header.addStretch()
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_bookmarks)
        header.addWidget(clear_btn)
        self.content_layout.addLayout(header)

        lbl = QLabel("Bookmarks")
        lbl.setStyleSheet("font-size: 22pt; font-weight: bold;")

        if not self.bookmarks:
            lbl = QLabel("No bookmarks yet.\n\nBrowse to a page and click the ★ button to save it here.")
            lbl.setStyleSheet("font-size: 14pt; color: #888;")
            lbl.setWordWrap(True)
            self.content_layout.addWidget(lbl)
            return

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        for b in self.bookmarks:
            row = QHBoxLayout()
            btn = QPushButton(b.get("title") or b.get("url", ""))
            btn.setToolTip(b.get("url", ""))
            btn.clicked.connect(lambda _, u=b.get("url"): self._load(u))
            row.addWidget(btn, 1)

            if b.get("title") and b.get("url"):
                url_lbl = QLabel(b.get("url", ""))
                url_lbl.setStyleSheet("color: #888; font-size: 11pt;")
                url_lbl.setTextFormat(Qt.TextFormat.RichText)
                url_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                row.addWidget(url_lbl)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(24, 24)
            del_btn.setStyleSheet("color: #ff5555;")
            del_btn.clicked.connect(lambda _, u=b.get("url"): self._remove_bookmark(u))
            row.addWidget(del_btn)

            container_layout.addLayout(row)

        self.content_layout.addWidget(container)

    def _remove_bookmark(self, url):
        self.bookmarks = [b for b in self.bookmarks if b.get("url") != url]
        _save_json(BOOKMARKS_FILE, self.bookmarks)
        self._show_bookmarks()

    def _clear_bookmarks(self):
        self.bookmarks = []
        _save_json(BOOKMARKS_FILE, self.bookmarks)
        self._show_bookmarks()

    def _show_history(self):
        self._clear_content()

        header = QHBoxLayout()
        header.addWidget(QLabel("History"))
        header.addStretch()
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_history)
        header.addWidget(clear_btn)
        self.content_layout.addLayout(header)

        if not self.history:
            lbl = QLabel("No history yet.\n\nNavigate to pages and they'll appear here.")
            lbl.setStyleSheet("font-size: 14pt; color: #888;")
            lbl.setWordWrap(True)
            self.content_layout.addWidget(lbl)
            return

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(2)

        for url in reversed(self.history[-50:]):
            row = QHBoxLayout()
            btn = QPushButton(url)
            btn.setToolTip(url)
            btn.clicked.connect(lambda _, u=url: self._load(u))
            btn.setTextFormat(Qt.TextFormat.RichText)
            btn.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            btn.setStyleSheet("text-align: left; padding: 4px 8px;")
            row.addWidget(btn, 1)
            container_layout.addLayout(row)

        self.content_layout.addWidget(container)

    def _clear_history(self):
        self.history = []
        _save_json(HISTORY_FILE, self.history)
        self._show_history()

    def _view_source(self):
        tab = self.tabs[self.tab_index]
        if not tab.source:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Source — {tab.url}")
        dlg.resize(700, 500)
        layout = QVBoxLayout(dlg)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setFont(QFont("monospace", 12))
        text.setPlainText(tab.source)
        layout.addWidget(text)
        dlg.exec()

    def _save_page(self):
        tab = self.tabs[self.tab_index]
        if not tab.source:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Page", "",
                                                "All Files (*);;MN Files (*.mn)")
        if path:
            with open(path, "w") as f:
                f.write(tab.source)
            self.status_bar.showMessage(f"Saved to {path}")

    def _show_auth(self):
        text, ok = QInputDialog.getText(self, "Authentication", "Token:",
                                         text=self.auth_token)
        if ok:
            self.auth_token = text.strip()
            self.status_bar.showMessage(f"Auth token {'set' if self.auth_token else 'cleared'}")

    def _show_upload(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
        if not path:
            return
        tab = self.tabs[self.tab_index]
        if not tab.url:
            self.status_bar.showMessage("Navigate to a URL first")
            return

        clean = tab.url.replace("mynet://", "")
        hostport, *rest = clean.split("/", 1)
        path_part = "/" + rest[0] if rest else "/"
        if ":" in hostport:
            host, port = hostport.rsplit(":", 1)
            port = int(port)
        else:
            host, port = hostport, 7443

        def do_upload():
            try:
                filename = os.path.basename(path)
                with open(path, "rb") as f:
                    file_data = f.read()
                boundary = "MyNetBoundary"
                body = (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                    f"Content-Type: application/octet-stream\r\n\r\n"
                ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

                resp = mynet.post(host, path_part, body, port, {
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                })
                self.status_bar.showMessage(f"Upload {resp.status}: {filename}")
            except Exception as e:
                self.status_bar.showMessage(f"Upload error: {e}")

        threading.Thread(target=do_upload, daemon=True).start()

    def _show_api_helper(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("API Helper")
        dlg.resize(500, 300)
        layout = QVBoxLayout(dlg)

        QLabel("POST JSON", self).setStyleSheet("font-weight: bold;")
        layout.addWidget(QLabel("URL (mynet://host/path)"))
        url_edit = QLineEdit()
        layout.addWidget(url_edit)

        body_edit = QTextEdit()
        body_edit.setPlainText('{"key": "value"}')
        layout.addWidget(body_edit)

        result_label = QLabel("")
        result_label.setStyleSheet("color: #4fc3f7;")
        layout.addWidget(result_label)

        def send():
            url = url_edit.text().strip()
            raw = body_edit.toPlainText().strip()
            if not url or not raw:
                return
            clean = url.replace("mynet://", "")
            hostport, *rest = clean.split("/", 1)
            path = "/" + rest[0] if rest else "/"
            if ":" in hostport:
                host, port = hostport.rsplit(":", 1)
                port = int(port)
            else:
                host, port = hostport, 7443

            def do():
                try:
                    resp = mynet.post(host, path, raw.encode(), port, {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.auth_token}" if self.auth_token else "",
                    })
                    result_label.setText(f"[{resp.status}] {resp.body.decode(errors='replace')[:200]}")
                except Exception as e:
                    result_label.setText(f"Error: {e}")

            threading.Thread(target=do, daemon=True).start()

        btn = QPushButton("Send POST")
        btn.clicked.connect(send)
        layout.addWidget(btn)
        dlg.exec()


from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import QInputDialog, QStatusBar


_RENDER_EVENT_TYPE = QEvent.registerEventType()
_ERROR_EVENT_TYPE = QEvent.registerEventType()


class _RenderEvent(QEvent):
    def __init__(self, source, status):
        super().__init__(_RENDER_EVENT_TYPE)
        self.source = source
        self.status = status


class _ErrorEvent(QEvent):
    def __init__(self, message):
        super().__init__(_ERROR_EVENT_TYPE)
        self.message = message


class _EventFilter(QObject):
    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser

    def eventFilter(self, obj, event):
        if event.type() == _RENDER_EVENT_TYPE:
            self.browser._render_from_event(event.source, event.status)
            return True
        elif event.type() == _ERROR_EVENT_TYPE:
            self.browser._show_error(event.message)
            return True
        return False


def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))

    browser = MyNetBrowser()
    browser._apply_theme()
    browser.show()

    event_filter = _EventFilter(browser)
    app.installEventFilter(event_filter)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
