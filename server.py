"""
Example MyNet server — demonstrates all new features.
Run:  ./run_server.sh
Open: mynet://localhost:7443/
"""

import os
import mynet

# Create public dir for static files
os.makedirs("public", exist_ok=True)

app = mynet.Server(
    port=7443,
    static_dir="public",    # ← static files from ./public/
    # token="mysecret123",  # ← uncomment for auth
)

HOME = """\
title: صفحه اصلی — MyNet

h1: به MyNet خوش آمدید!

p: این یک صفحه نمونه روی پروتکل MNET است.

hr:

h2: قابلیت‌های سرور

ul:
    - فایل‌های استاتیک (تصاویر، ویدیو، صدا)
    - فشرده‌سازی gzip خودکار
    - کش پاسخ‌ها
    - Range Request (دانلود جزئی)
    - لاگ درخواست‌ها
    - آپلود فایل
    - احراز هویت با توکن
    - WebSocket
    - API JSON
    - هدر سفارشی

hr:

h2: صفحات نمونه

link("mynet://localhost:7443/about"): درباره MyNet
link("mynet://localhost:7443/demo"): دموی تگ‌ها
link("mynet://localhost:7443/api"): API نمونه
link("mynet://localhost:7443/upload"): صفحه آپلود
link("mynet://localhost:7443/ws-chat"): چت WebSocket

hr:

h2: مالتی مدیا

p: ویدیوی نمونه:
video(mynet://localhost:7443/sample.mp4)

p: صدای نمونه:
audio(mynet://localhost:7443/sample.mp3)

hr:

code: pip install customtkinter
"""

ABOUT = """\
title: درباره MyNet

h1: درباره MyNet

p: MyNet یک جایگزین سبک و امن برای HTTPS است.

h2: پروتکل MNET

ul:
    - رمزنگاری TLS
    - فرمت سبک درخواست/پاسخ
    - پشتیبانی از Range Request
    - فشرده‌سازی gzip

h2: زبان MN

p: سینتکس شبیه پایتون:

code:
 title: صفحه من

 h1: سلام دنیا

 p: پاراگراف

 ul:
     - آیتم اول
     - آیتم دوم

hr:

link("mynet://localhost:7443/"): صفحه اصلی
"""

DEMO = """\
title: دموی تگ‌ها

h1: دموی تمام تگ‌های MN

hr:

h2: عنوان‌ها

h1: h1 عنوان
h2: h2 عنوان
h3: h3 عنوان
h4: h4 عنوان

hr:

h2: متن

p: این یک پاراگراف معمولی است.

bold: این متن ضخیم است.

code: این کد است

hr:

h2: لیست

ul:
    - بدون ترتیب ۱
    - بدون ترتیب ۲
    - بدون ترتیب ۳

ol:
    - مرتب ۱
    - مرتب ۲
    - مرتب ۳

hr:

h2: جدول

table:
    row:
        cell: نام
        cell: سن
        cell: شهر
    row:
        cell: علی
        cell: 25
        cell: تهران
    row:
        cell: سارا
        cell: 22
        cell: اصفهان

hr:

h2: فرم

form(mynet://localhost:7443/api):
    input(name="username", placeholder="نام کاربری")
    input(name="password", type="password", placeholder="رمز عبور")
    button: ورود

hr:

h2: لینک‌ها

link("mynet://localhost:7443/"): صفحه اصلی
link("mynet://localhost:7443/about"): درباره
"""

API = """\
title: API نمونه

h1: API JSON

p: این صفحه یک API JSON ساده است.

code:
 GET /api/data → JSON
 POST /api/data → JSON

p: برای تست:

code:
 curl -k mynet://localhost:7443/api/data

link("mynet://localhost:7443/"): صفحه اصلی
"""

UPLOAD_PAGE = """\
title: آپلود فایل

h1: آپلود فایل

p: از دکمه ⬆ Upload در نوار ابزار استفاده کنید.

p: فایل به سرور ارسال می‌شود.

link("mynet://localhost:7443/"): صفحه اصلی
"""

WS_CHAT = """\
title: چت WebSocket

h1: چت WebSocket

p: این صفحه از WebSocket پشتیبانی می‌کند.

p: به زودی...

link("mynet://localhost:7443/"): صفحه اصلی
"""

# ── Routes ────────────────────────────────────────────────────────

app.route("/")(lambda req: HOME)
app.route("/about")(lambda req: ABOUT)
app.route("/demo")(lambda req: DEMO)
app.route("/upload")(lambda req: UPLOAD_PAGE)
app.route("/ws-chat")(lambda req: WS_CHAT)


# ── JSON API ──────────────────────────────────────────────────────

@app.route("/api/data")
def api_data(req):
    return mynet.json_response({
        "status": "ok",
        "protocol": "MNET/1.0",
        "features": ["cache", "gzip", "range", "ws", "upload", "auth"],
    })


@app.route("/api/echo", methods=["POST"])
def api_echo(req):
    data = mynet.json_body(req)
    return mynet.json_response({"echo": data})


# ── WebSocket handler ─────────────────────────────────────────────

@app.ws("/ws")
def ws_chat(ws, addr):
    print(f"[WS] {addr} connected")
    try:
        while True:
            msg = ws.recv()
            if msg is None:
                break
            ws.send(f"echo: {msg}")
            print(f"[WS] {addr}: {msg}")
    except Exception:
        pass
    print(f"[WS] {addr} disconnected")


if __name__ == "__main__":
    app.start()
