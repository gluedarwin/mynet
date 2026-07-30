"""
MyNet Browser — Lightweight browser for the MNET protocol.
Requires: pip install customtkinter
"""

import threading
import json
import os
import webbrowser
import customtkinter as ctk

import mynet
import mn

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

SIZES = {"h1": 28, "h2": 22, "h3": 18, "h4": 16, "h5": 14, "h6": 12}
DATA_DIR = os.path.join(os.path.expanduser("~"), ".mynet")
BOOKMARKS_FILE = os.path.join(DATA_DIR, "bookmarks.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")


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


class Browser(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MyNet Browser")
        self.geometry("1024x700")
        self.minsize(600, 400)

        self.tabs = [Tab()]
        self.tab_index = 0
        self.zoom = 14
        self.theme = "dark"
        self.bookmarks = _load_json(BOOKMARKS_FILE)
        self.full_history = _load_json(HISTORY_FILE)
        self.auth_token = ""

        self._build_ui()
        self._bind_keys()
        self._update_tab_bar()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # UI
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _build_ui(self):
        # ── tab bar ───────────────────────────────────────────────
        self.tab_frame = ctk.CTkFrame(self, height=36, fg_color="#1a1a2e")
        self.tab_frame.pack(fill="x", padx=0, pady=0)
        self.tab_frame.pack_propagate(False)

        self.add_tab_btn = ctk.CTkButton(self.tab_frame, text="+", width=32,
                                          height=28, font=ctk.CTkFont(size=16),
                                          command=self._new_tab)
        self.add_tab_btn.pack(side="left", padx=4, pady=4)

        # ── nav bar ───────────────────────────────────────────────
        nav = ctk.CTkFrame(self, height=44)
        nav.pack(fill="x", padx=8, pady=(4, 0))

        ctk.CTkButton(nav, text="◀", width=36, command=self._back).pack(side="left", padx=3)
        ctk.CTkButton(nav, text="▶", width=36, command=self._fwd).pack(side="left", padx=3)
        ctk.CTkButton(nav, text="↻", width=36, command=self._refresh).pack(side="left", padx=3)

        self.url = ctk.CTkEntry(nav, placeholder_text="mynet://localhost:7443/")
        self.url.pack(side="left", fill="x", expand=True, padx=6)
        self.url.bind("<Return>", lambda _: self._go())

        ctk.CTkButton(nav, text="→", width=36, command=self._go).pack(side="left", padx=3)

        self.bookmark_btn = ctk.CTkButton(nav, text="☆", width=36,
                                           fg_color="transparent",
                                           command=self._toggle_bookmark)
        self.bookmark_btn.pack(side="left", padx=3)

        # ── toolbar ───────────────────────────────────────────────
        tools = ctk.CTkFrame(self, height=32)
        tools.pack(fill="x", padx=8, pady=(2, 0))

        for txt, cmd in [
            ("🔍 Find", self._show_find),
            ("📋 History", self._show_history),
            ("⭐ Marks", self._show_bookmarks),
            ("📄 Source", self._view_source),
            ("💾 Save", self._save_page),
            ("☀ Theme", self._toggle_theme),
            ("A+", self._zoom_in),
            ("A-", self._zoom_out),
            ("⛶ Full", self._toggle_fullscreen),
            ("📋URL", self._copy_url),
            ("🔐 Auth", self._show_auth),
            ("📡 API", self._show_api_helper),
            ("⬆ Upload", self._show_upload),
        ]:
            ctk.CTkButton(tools, text=txt, width=52, height=26, font=ctk.CTkFont(size=11),
                           fg_color="transparent", command=cmd).pack(side="left", padx=1)

        # ── content ───────────────────────────────────────────────
        self.page = ctk.CTkScrollableFrame(self)
        self.page.pack(fill="both", expand=True, padx=8, pady=4)

        # ── status bar ────────────────────────────────────────────
        self.status = ctk.CTkLabel(self, text="Ready", anchor="w",
                                    height=24, font=ctk.CTkFont(size=11),
                                    fg_color="#1a1a2e")
        self.status.pack(fill="x", padx=0, pady=0)

        self._welcome()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # KEYBOARD SHORTCUTS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _bind_keys(self):
        for key, cmd in [
            ("<Command-r>", self._refresh), ("<Control-r>", self._refresh),
            ("<Command-l>", self._focus_url), ("<Control-l>", self._focus_url),
            ("<Command-t>", self._new_tab), ("<Control-t>", self._new_tab),
            ("<Command-w>", self._close_tab), ("<Control-w>", self._close_tab),
            ("<Command-f>", self._show_find), ("<Control-f>", self._show_find),
            ("<Command-plus>", self._zoom_in), ("<Command-equal>", self._zoom_in),
            ("<Command-minus>", self._zoom_out),
            ("<F5>", self._refresh),
            ("<Escape>", self._exit_fullscreen),
        ]:
            self.bind(key, lambda _, c=cmd: c())
        for i in range(5):
            self.bind(f"<Command-{i+1}>", lambda _, i=i: self._switch_tab(i))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TABS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _new_tab(self):
        self.tabs.append(Tab())
        self.tab_index = len(self.tabs) - 1
        self._update_tab_bar()
        self._render_tab()

    def _close_tab(self):
        if len(self.tabs) <= 1:
            return
        self.tabs.pop(self.tab_index)
        self.tab_index = min(self.tab_index, len(self.tabs) - 1)
        self._update_tab_bar()
        self._render_tab()

    def _switch_tab(self, idx):
        if idx < len(self.tabs):
            self.tab_index = idx
            self._update_tab_bar()
            self._render_tab()

    def _update_tab_bar(self):
        for w in self.tab_frame.winfo_children():
            if w != self.add_tab_btn:
                w.destroy()
        for i, tab in enumerate(self.tabs):
            label = tab.title[:12] + "…" if len(tab.title) > 12 else tab.title
            ctk.CTkButton(self.tab_frame, text=label, height=28, width=120,
                           font=ctk.CTkFont(size=12),
                           fg_color="#2a2a4a" if i == self.tab_index else "#1a1a2e",
                           command=lambda i=i: self._switch_tab(i)).pack(side="left", padx=2, pady=4)

    def _render_tab(self):
        tab = self.tabs[self.tab_index]
        self.url.delete(0, "end")
        self.url.insert(0, tab.url)
        self._update_tab_bar()
        if tab.source:
            self._clear()
            for el in mn.parse(tab.source):
                self._draw(el)
        else:
            self._welcome()

    def _focus_url(self):
        self.url.focus_set()
        self.url.select_range(0, "end")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # NAVIGATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _go(self):
        raw = self.url.get().strip()
        if not raw:
            return
        if not raw.startswith("mynet://"):
            raw = "mynet://" + raw
        tab = self.tabs[self.tab_index]
        if tab.url and (not self.full_history or self.full_history[-1] != raw):
            self.full_history.append(raw)
            _save_json(HISTORY_FILE, self.full_history)
        tab.url = raw
        self._update_tab_bar()
        self.status.configure(text=f"Loading {raw}…")
        threading.Thread(target=self._fetch, args=(raw,), daemon=True).start()

    def _back(self):
        tab = self.tabs[self.tab_index]
        idx = self.full_history.index(tab.url) if tab.url in self.full_history else -1
        if idx > 0:
            self.url.delete(0, "end")
            self.url.insert(0, self.full_history[idx - 1])
            self._go()

    def _fwd(self):
        tab = self.tabs[self.tab_index]
        idx = self.full_history.index(tab.url) if tab.url in self.full_history else -1
        if idx < len(self.full_history) - 1:
            self.url.delete(0, "end")
            self.url.insert(0, self.full_history[idx + 1])
            self._go()

    def _refresh(self):
        tab = self.tabs[self.tab_index]
        if tab.url:
            self.status.configure(text="Refreshing…")
            threading.Thread(target=self._fetch, args=(tab.url,), daemon=True).start()

    def _load(self, url):
        self.url.delete(0, "end")
        self.url.insert(0, url)
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
            self.after(0, self._render_content, src)
            self.after(0, lambda: self.status.configure(
                text=f"Done — {url} [{resp.status}]"))
        except Exception as e:
            self.after(0, self._error, str(e))
            self.after(0, lambda: self.status.configure(text="Error"))

    def _error(self, msg):
        self._clear()
        ctk.CTkLabel(self.page, text=f"Error:\n{msg}",
                      text_color="#ff5555", font=ctk.CTkFont(size=14)).pack(pady=60)

    def _render_content(self, source):
        self._clear()
        for el in mn.parse(source):
            self._draw(el)

    def _welcome(self):
        self._clear()
        ctk.CTkLabel(self.page, text="MyNet Browser",
                      font=ctk.CTkFont(size=32, weight="bold")).pack(pady=50)
        ctk.CTkLabel(self.page, text="mynet:// URL وارد کنید",
                      font=ctk.CTkFont(size=15)).pack()
        ctk.CTkLabel(self.page, text=(
            "Cmd+T: تب جدید | Cmd+W: بستن | Cmd+R: رفرش | Cmd+L: آدرس\n"
            "Cmd+F: جستجو | Cmd+/-: زوم | F5: رفرش | Esc: تمام‌صفحه"
        ), font=ctk.CTkFont(size=12), text_color="#888").pack(pady=20)

    def _clear(self):
        for w in self.page.winfo_children():
            w.destroy()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BOOKMARKS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _toggle_bookmark(self):
        tab = self.tabs[self.tab_index]
        if not tab.url:
            return
        if any(b["url"] == tab.url for b in self.bookmarks):
            self.bookmarks = [b for b in self.bookmarks if b["url"] != tab.url]
            self.bookmark_btn.configure(text="☆")
        else:
            self.bookmarks.append({"url": tab.url, "title": tab.title})
            self.bookmark_btn.configure(text="★")
        _save_json(BOOKMARKS_FILE, self.bookmarks)

    def _show_bookmarks(self):
        self._clear()
        ctk.CTkLabel(self.page, text="Bookmarks",
                      font=ctk.CTkFont(size=22, weight="bold")).pack(pady=15, anchor="w", padx=12)
        if not self.bookmarks:
            ctk.CTkLabel(self.page, text="No bookmarks.", font=ctk.CTkFont(size=14)).pack(pady=20)
            return
        for b in self.bookmarks:
            row = ctk.CTkFrame(self.page, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkButton(row, text=b.get("title", b["url"]), anchor="w",
                           fg_color="transparent", text_color="#4fc3f7",
                           font=ctk.CTkFont(size=14),
                           command=lambda u=b["url"]: self._load(u)).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="✕", width=28, fg_color="transparent",
                           text_color="#ff5555",
                           command=lambda u=b["url"]: self._remove_bookmark(u)).pack(side="right")

    def _remove_bookmark(self, url):
        self.bookmarks = [b for b in self.bookmarks if b["url"] != url]
        _save_json(BOOKMARKS_FILE, self.bookmarks)
        self._show_bookmarks()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # HISTORY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _show_history(self):
        self._clear()
        ctk.CTkLabel(self.page, text="History",
                      font=ctk.CTkFont(size=22, weight="bold")).pack(pady=15, anchor="w", padx=12)
        if not self.full_history:
            ctk.CTkLabel(self.page, text="No history.", font=ctk.CTkFont(size=14)).pack(pady=20)
            return
        for url in reversed(self.full_history[-50:]):
            ctk.CTkButton(self.page, text=url, anchor="w",
                           fg_color="transparent", text_color="#4fc3f7",
                           font=ctk.CTkFont(size=13),
                           command=lambda u=url: self._load(u)).pack(fill="x", padx=12, pady=1)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FIND
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _show_find(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Find")
        popup.geometry("360x80")
        popup.transient(self)
        popup.grab_set()
        frame = ctk.CTkFrame(popup)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        ctk.CTkLabel(frame, text="Search:").pack(side="left", padx=4)
        entry = ctk.CTkEntry(frame, width=200)
        entry.pack(side="left", padx=4, fill="x", expand=True)
        entry.focus_set()

        def do_find():
            q = entry.get().strip().lower()
            if not q:
                return
            tab = self.tabs[self.tab_index]
            count = tab.source.lower().count(q) if tab.source else 0
            self.status.configure(text=f"Found {count} matches for \"{q}\"")
            popup.destroy()

        entry.bind("<Return>", lambda _: do_find())
        ctk.CTkButton(frame, text="Find", width=60, command=do_find).pack(side="left", padx=4)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # VIEW SOURCE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _view_source(self):
        tab = self.tabs[self.tab_index]
        if not tab.source:
            return
        popup = ctk.CTkToplevel(self)
        popup.title(f"Source — {tab.url}")
        popup.geometry("700x500")
        popup.transient(self)
        text = ctk.CTkTextbox(popup, font=ctk.CTkFont(family="monospace", size=13))
        text.pack(fill="both", expand=True, padx=8, pady=8)
        text.insert("1.0", tab.source)
        text.configure(state="disabled")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SAVE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _save_page(self):
        tab = self.tabs[self.tab_index]
        if not tab.source:
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".mn",
                                             filetypes=[("MN files", "*.mn"), ("All", "*.*")])
        if path:
            with open(path, "w") as f:
                f.write(tab.source)
            self.status.configure(text=f"Saved to {path}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # AUTH
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _show_auth(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Authentication")
        popup.geometry("400x120")
        popup.transient(self)
        popup.grab_set()
        frame = ctk.CTkFrame(popup)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        ctk.CTkLabel(frame, text="Token:").pack(anchor="w", padx=4)
        entry = ctk.CTkEntry(frame, width=350, placeholder_text="Bearer token…")
        entry.pack(padx=4, pady=4, fill="x")
        if self.auth_token:
            entry.insert(0, self.auth_token)

        def save():
            self.auth_token = entry.get().strip()
            self.status.configure(text=f"Auth token {'set' if self.auth_token else 'cleared'}")
            popup.destroy()

        ctk.CTkButton(frame, text="Save", command=save).pack(pady=4)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # UPLOAD
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _show_upload(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename()
        if not path:
            return
        tab = self.tabs[self.tab_index]
        if not tab.url:
            self.status.configure(text="Navigate to a URL first")
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
                boundary = "MyNetBoundary"
                filename = os.path.basename(path)
                with open(path, "rb") as f:
                    file_data = f.read()
                body = (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                    f"Content-Type: application/octet-stream\r\n\r\n"
                ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

                resp = mynet.post(host, path_part, body, port, {
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                })
                self.after(0, lambda: self.status.configure(
                    text=f"Upload {resp.status}: {filename}"))
            except Exception as e:
                self.after(0, lambda: self.status.configure(text=f"Upload error: {e}"))

        threading.Thread(target=do_upload, daemon=True).start()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # API HELPER
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _show_api_helper(self):
        popup = ctk.CTkToplevel(self)
        popup.title("API Helper")
        popup.geometry("500x300")
        popup.transient(self)
        popup.grab_set()

        frame = ctk.CTkFrame(popup)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(frame, text="POST JSON", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=4)

        url_entry = ctk.CTkEntry(frame, placeholder_text="URL (mynet://host/path)")
        url_entry.pack(fill="x", padx=4, pady=4)

        body_text = ctk.CTkTextbox(frame, height=120, font=ctk.CTkFont(family="monospace", size=12))
        body_text.pack(fill="both", expand=True, padx=4, pady=4)
        body_text.insert("1.0", '{"key": "value"}')

        result_label = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=11), text_color="#4fc3f7")
        result_label.pack(anchor="w", padx=4)

        def send():
            url = url_entry.get().strip()
            raw = body_text.get("1.0", "end").strip()
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
                    self.after(0, lambda: result_label.configure(
                        text=f"[{resp.status}] {resp.body.decode(errors='replace')[:200]}"))
                except Exception as e:
                    self.after(0, lambda: result_label.configure(text=f"Error: {e}"))

            threading.Thread(target=do, daemon=True).start()

        ctk.CTkButton(frame, text="Send POST", command=send).pack(pady=4)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ZOOM / THEME / FULLSCREEN / COPY URL
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _zoom_in(self):
        self.zoom = min(28, self.zoom + 2)
        self._refresh()

    def _zoom_out(self):
        self.zoom = max(8, self.zoom - 2)
        self._refresh()

    def _toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        ctk.set_appearance_mode(self.theme)

    def _toggle_fullscreen(self):
        self.attributes("-fullscreen", not self.attributes("-fullscreen"))

    def _exit_fullscreen(self):
        self.attributes("-fullscreen", False)

    def _copy_url(self):
        self.clipboard_clear()
        self.clipboard_append(self.url.get())
        self.status.configure(text="URL copied")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # RENDER
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _draw(self, el):
        t = el.tag.lower()
        z = self.zoom

        if t == "title":
            self.title(f"MyNet — {el.text}")
            self.tabs[self.tab_index].title = el.text
            self._update_tab_bar()
            return

        if t in SIZES:
            ctk.CTkLabel(self.page, text=el.text,
                          font=ctk.CTkFont(size=SIZES[t], weight="bold"),
                          anchor="w").pack(fill="x", padx=12, pady=(14, 4))
            return

        if t == "p":
            ctk.CTkLabel(self.page, text=el.text, anchor="w",
                          wraplength=820, justify="left",
                          font=ctk.CTkFont(size=z)).pack(fill="x", padx=12, pady=3)
            return

        if t == "ul":
            for ch in el.children:
                if ch.tag == "li":
                    ctk.CTkLabel(self.page, text=f"•  {ch.text}", anchor="w",
                                  wraplength=800, justify="left",
                                  font=ctk.CTkFont(size=z)).pack(fill="x", padx=24, pady=2)
            return

        if t == "ol":
            for i, ch in enumerate(el.children, 1):
                if ch.tag == "li":
                    ctk.CTkLabel(self.page, text=f"{i}.  {ch.text}", anchor="w",
                                  wraplength=800, justify="left",
                                  font=ctk.CTkFont(size=z)).pack(fill="x", padx=24, pady=2)
            return

        if t == "link":
            url = el.attrs.get("_0", "")
            ctk.CTkButton(self.page, text=el.text or url, anchor="w",
                           fg_color="transparent", text_color="#4fc3f7",
                           hovercolor="#2196f3", height=28,
                           font=ctk.CTkFont(size=z),
                           command=lambda u=url: self._open(u)).pack(fill="x", padx=12, pady=2)
            return

        if t == "hr":
            ctk.CTkFrame(self.page, height=2, fg_color="#555").pack(fill="x", padx=12, pady=10)
            return

        if t in ("bold", "b"):
            ctk.CTkLabel(self.page, text=el.text, anchor="w",
                          font=ctk.CTkFont(size=z, weight="bold")).pack(fill="x", padx=12, pady=3)
            return

        if t in ("italic", "i"):
            ctk.CTkLabel(self.page, text=el.text, anchor="w",
                          font=ctk.CTkFont(size=z)).pack(fill="x", padx=12, pady=3)
            return

        if t == "code":
            ctk.CTkLabel(self.page, text=el.text, anchor="w", justify="left",
                          font=ctk.CTkFont(family="monospace", size=max(11, z - 1)),
                          fg_color="#1e1e2e", corner_radius=6).pack(fill="x", padx=12, pady=4)
            return

        if t == "pre":
            ctk.CTkLabel(self.page, text=el.text, anchor="w", justify="left",
                          font=ctk.CTkFont(family="monospace", size=max(11, z - 1)),
                          fg_color="#1e1e2e", corner_radius=6,
                          wraplength=800).pack(fill="x", padx=12, pady=4)
            for ch in el.children:
                self._draw(ch)
            return

        if t == "image" or t == "img":
            src = el.attrs.get("_0", el.attrs.get("src", el.text))
            ctk.CTkLabel(self.page, text=f"[image: {src}]",
                          font=ctk.CTkFont(size=12), text_color="#888").pack(pady=6)
            return

        if t == "video":
            src = el.attrs.get("_0", el.attrs.get("src", el.text))
            row = ctk.CTkFrame(self.page, fg_color="#1e1e2e", corner_radius=8)
            row.pack(fill="x", padx=12, pady=6, ipady=20)
            ctk.CTkLabel(row, text=f"  ▶  Video: {src}",
                          font=ctk.CTkFont(size=13), text_color="#4fc3f7").pack(pady=10)
            ctk.CTkButton(row, text="Open in system player", height=28,
                           command=lambda: webbrowser.open(src)).pack(pady=4)
            return

        if t == "audio":
            src = el.attrs.get("_0", el.attrs.get("src", el.text))
            row = ctk.CTkFrame(self.page, fg_color="#1e1e2e", corner_radius=8)
            row.pack(fill="x", padx=12, pady=4, ipady=10)
            ctk.CTkLabel(row, text=f"  ♫  Audio: {src}",
                          font=ctk.CTkFont(size=13), text_color="#4fc3f7").pack(pady=6)
            return

        if t == "table":
            self._draw_table(el)
            return

        if t == "form":
            self._draw_form(el)
            return

        if t == "button":
            ctk.CTkButton(self.page, text=el.text, height=32,
                           font=ctk.CTkFont(size=z)).pack(padx=12, pady=4, anchor="w")
            return

        # fallback
        if el.text:
            ctk.CTkLabel(self.page, text=el.text, anchor="w",
                          wraplength=820, justify="left",
                          font=ctk.CTkFont(size=z)).pack(fill="x", padx=12, pady=3)
        for ch in el.children:
            self._draw(ch)

    def _draw_table(self, el):
        rows = [ch for ch in el.children if ch.tag == "row"]
        if not rows:
            return
        frame = ctk.CTkFrame(self.page, fg_color="transparent")
        frame.pack(fill="x", padx=12, pady=6)
        for i, row in enumerate(rows):
            cells = [ch for ch in row.children if ch.tag == "cell"]
            for j, cell in enumerate(cells):
                weight = "bold" if i == 0 else "normal"
                bg = "#2a2a4a" if i == 0 else ("#1e1e2e" if i % 2 == 0 else "transparent")
                ctk.CTkLabel(frame, text=cell.text, anchor="w",
                              font=ctk.CTkFont(size=self.zoom, weight=weight),
                              fg_color=bg, corner_radius=4,
                              width=200).grid(row=i, column=j, padx=2, pady=2, sticky="w")

    def _draw_form(self, el):
        action = el.attrs.get("_0", el.attrs.get("action", ""))
        frame = ctk.CTkFrame(self.page, fg_color="#1e1e2e", corner_radius=8)
        frame.pack(fill="x", padx=12, pady=8)
        entries = {}

        for ch in el.children:
            if ch.tag == "input":
                itype = ch.attrs.get("type", "text")
                name = ch.attrs.get("name", ch.attrs.get("_0", ""))
                placeholder = ch.attrs.get("placeholder", ch.text)
                ctk.CTkLabel(frame, text=name, font=ctk.CTkFont(size=12),
                              anchor="w").pack(fill="x", padx=8, pady=(6, 0))
                entry = ctk.CTkEntry(frame, placeholder_text=placeholder)
                entry.pack(fill="x", padx=8, pady=2)
                entries[name] = entry
            elif ch.tag == "button":
                pass

        def submit():
            data = {k: e.get() for k, e in entries.items()}
            self.status.configure(text=f"Form submitted: {data}")
            if action:
                self._load(action)

        ctk.CTkButton(frame, text="Submit", command=submit).pack(pady=8)

    def _open(self, url):
        self.url.delete(0, "end")
        self.url.insert(0, url)
        self._go()


if __name__ == "__main__":
    Browser().mainloop()
