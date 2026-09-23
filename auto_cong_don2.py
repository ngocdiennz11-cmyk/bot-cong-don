# -*- coding: utf-8 -*-
"""
Hệ thống ĐẾM SỐ LẦN XUẤT HIỆN qua Telegram Bot + Web Admin.
Chỉ đếm các tài khoản đã được khai báo trước trong DB.
Chia nhóm: Diễn, Hiếu.
"""

import re
import os
import logging
import asyncio
import threading
import certifi
from telethon import TelegramClient, events
from pymongo import MongoClient
from flask import Flask, request, render_template_string, redirect, session, url_for, flash

# ==========================================
# ⚙️ CẤU HÌNH MÔI TRƯỜNG (Lấy từ Render)
# ==========================================
API_ID = int(os.environ.get("API_ID", 38363563))
API_HASH = os.environ.get("API_HASH", "9477629b42cefd32af155992effeab8b")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URL = os.environ.get("MONGO_URL", "")
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "123456")
FLASK_SECRET = os.environ.get("FLASK_SECRET", "ngocdien_sieu_cap_bao_mat")
ADMIN_URL = os.environ.get("ADMIN_URL", "Web Admin")

MAIN_DOC_ID = "dem_so_main"

DEFAULT_DOC = {
    "tong_he_thong": 0,
    "tong_dien": 0,
    "tong_hieu": 0,
    "danh_sach_nick": {} # Cấu trúc: {"ten_nick": {"nhom": "dien/hieu", "dem": 0}}
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("bot")

# ==========================================
# 🗄️ KẾT NỐI DATABASE
# ==========================================
collection = None
try:
    if MONGO_URL:
        db_client = MongoClient(MONGO_URL, tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=True)
        collection = db_client["telegram_bot"]["dem_so_db"]
        log.info("✅ Đã kết nối MongoDB thành công!")
    else:
        log.error("❌ Chưa cấu hình MONGO_URL")
except Exception as e:
    log.error("❌ Lỗi kết nối Database: %s", e)

def doc_data():
    doc = collection.find_one({"_id": MAIN_DOC_ID}) if collection is not None else None
    if not doc:
        return {"_id": MAIN_DOC_ID, **DEFAULT_DOC}
    return {
        "_id": MAIN_DOC_ID,
        "tong_he_thong": doc.get("tong_he_thong", 0),
        "tong_dien": doc.get("tong_dien", 0),
        "tong_hieu": doc.get("tong_hieu", 0),
        "danh_sach_nick": doc.get("danh_sach_nick", {})
    }

def luu_data(data):
    if collection is None: return
    payload = {k: v for k, v in data.items() if k != "_id"}
    collection.update_one({"_id": MAIN_DOC_ID}, {"$set": payload}, upsert=True)

# ==========================================
# 🌐 PHẦN 1: WEB QUẢN TRỊ (FLASK)
# ==========================================
app = Flask(__name__)
app.secret_key = FLASK_SECRET

BASE_STYLE = """
:root{ --bg:#f5f7fb; --card:#ffffff; --primary:#4f6bf6; --green:#16a34a; --red:#e0384a; }
body{ background:var(--bg); font-family:sans-serif; margin:0; padding:20px; color:#333; }
.wrap{ max-width:900px; margin:0 auto; }
.card{ background:var(--card); padding:20px; border-radius:10px; box-shadow:0 4px 6px rgba(0,0,0,0.05); margin-bottom:20px; }
.stats{ display:flex; gap:20px; margin-bottom:20px; flex-wrap: wrap; }
.stat-box{ flex:1; min-width: 200px; padding:20px; border-radius:10px; color:#fff; text-align:center; font-weight:bold; }
.b-tong{ background:#7c3aed; } .b-dien{ background:#0ea5e9; } .b-hieu{ background:#f43f5e; }
table{ width:100%; border-collapse:collapse; margin-top:10px; font-size:15px; }
th, td{ padding:12px; border-bottom:1px solid #eee; text-align:left; }
button{ cursor:pointer; padding:8px 12px; border:none; border-radius:5px; background:var(--primary); color:#fff; font-weight:bold; }
input, select{ padding:8px; border:1px solid #ccc; border-radius:5px; outline:none; }
.flash{ background:#e8f8ee; color:var(--green); padding:10px; border-radius:5px; margin-bottom:15px; font-weight:bold; }
"""

TEMPLATE = """
<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Quản Lý Đếm Tên</title><style>{{style}}</style></head>
<body>
<div class="wrap">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; margin-bottom: 20px;">
        <h2>📊 Hệ Thống Đếm Lượt Tài Khoản</h2>
        <a href="{{url_for('logout')}}" style="color:var(--red); text-decoration:none; font-weight:bold;">Đăng xuất</a>
    </div>

    {% if get_flashed_messages() %}
      {% for m in get_flashed_messages() %}<div class="flash">✅ {{ m }}</div>{% endfor %}
    {% endif %}

    <div class="stats">
        <div class="stat-box b-tong">TỔNG HỆ THỐNG<br><h1 style="margin:10px 0 0 0;">{{data.tong_he_thong}}</h1></div>
        <div class="stat-box b-dien">NHÓM DIỄN<br><h1 style="margin:10px 0 0 0;">{{data.tong_dien}}</h1></div>
        <div class="stat-box b-hieu">NHÓM HIẾU<br><h1 style="margin:10px 0 0 0;">{{data.tong_hieu}}</h1></div>
    </div>

    <div class="card">
        <h3>➕ Thêm tài khoản theo dõi</h3>
        <form action="{{url_for('add_user')}}" method="POST" style="display:flex; gap:10px; flex-wrap:wrap;">
            <input type="text" name="tk" placeholder="Nhập tên tài khoản..." required style="flex:1; min-width: 200px;">
            <select name="nhom">
                <option value="dien">Nhóm Diễn</option>
                <option value="hieu">Nhóm Hiếu</option>
            </select>
            <button type="submit">Thêm ngay</button>
        </form>
    </div>

    <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
            <h3>📋 Danh sách đang theo dõi</h3>
            <form action="{{url_for('reset_all')}}" method="POST" onsubmit="return confirm('Reset toàn bộ số lượt đếm về 0?');">
                <button type="submit" style="background:var(--red);">🔄 Reset Tất Cả Lượt Đếm Về 0</button>
            </form>
        </div>
        <div style="overflow-x:auto;">
            <table>
                <tr><th>Tên tài khoản</th><th>Nhóm</th><th>Lượt đếm</th><th>Thao tác</th></tr>
                {% for tk, info in data.danh_sach_nick.items() %}
                <tr>
                    <td><b>{{tk}}</b></td>
                    <td><span style="background:#eef1f8; padding:4px 8px; border-radius:5px; font-size:13px; font-weight:bold;">{{ 'Diễn' if info.nhom == 'dien' else 'Hiếu' }}</span></td>
                    <td style="font-size:18px; font-weight:bold; color:var(--primary);">{{info.dem}}</td>
                    <td>
                        <form action="{{url_for('delete_user')}}" method="POST" style="display:inline;" onsubmit="return confirm('Xóa {{tk}} khỏi danh sách?');">
                            <input type="hidden" name="tk" value="{{tk}}">
                            <button type="submit" style="background:var(--red); padding:6px 10px; font-size:12px;">Xóa</button>
                        </form>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="4" style="text-align:center; color:#888;">Chưa có tài khoản nào được thêm.</td></tr>
                {% endfor %}
            </table>
        </div>
    </div>
</div>
</body></html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    if not session.get("logged_in"):
        if request.method == "POST":
            if request.form.get("password") == WEB_PASSWORD:
                session["logged_in"] = True
                return redirect(url_for("index"))
            return '<div style="color:red; text-align:center; margin-top:20px;">Sai mật khẩu!</div>' + login_form()
        return login_form()
    return render_template_string(TEMPLATE, data=doc_data(), style=BASE_STYLE)

def login_form():
    return '''
    <body style="background:#f5f7fb; font-family:sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; margin:0;">
        <form method="POST" style="background:#fff; padding:30px; border-radius:10px; box-shadow:0 4px 10px rgba(0,0,0,0.1); text-align:center;">
            <h3>🔒 Đăng nhập hệ thống</h3>
            <input type="password" name="password" placeholder="Nhập mật khẩu..." required style="padding:10px; width:200px; border:1px solid #ccc; border-radius:5px; margin-bottom:15px; outline:none;"><br>
            <button type="submit" style="padding:10px 20px; border:none; background:#4f6bf6; color:#fff; font-weight:bold; border-radius:5px; cursor:pointer;">Đăng nhập</button>
        </form>
    </body>
    '''

@app.route("/add_user", methods=["POST"])
def add_user():
    if not session.get("logged_in"): return redirect(url_for("index"))
    tk = request.form.get("tk").strip().lower()
    nhom = request.form.get("nhom")
    data = doc_data()
    if tk and tk not in data["danh_sach_nick"]:
        data["danh_sach_nick"][tk] = {"nhom": nhom, "dem": 0}
        luu_data(data)
        flash(f"Đã thêm {tk} vào nhóm {nhom}.")
    return redirect(url_for("index"))

@app.route("/delete_user", methods=["POST"])
def delete_user():
    if not session.get("logged_in"): return redirect(url_for("index"))
    tk = request.form.get("tk")
    data = doc_data()
    if tk in data["danh_sach_nick"]:
        dem = data["danh_sach_nick"][tk]["dem"]
        nhom = data["danh_sach_nick"][tk]["nhom"]
        data["tong_he_thong"] -= dem
        if nhom == "dien": data["tong_dien"] -= dem
        if nhom == "hieu": data["tong_hieu"] -= dem
        del data["danh_sach_nick"][tk]
        luu_data(data)
        flash(f"Đã xóa {tk}.")
    return redirect(url_for("index"))

@app.route("/reset_all", methods=["POST"])
def reset_all():
    if not session.get("logged_in"): return redirect(url_for("index"))
    data = doc_data()
    data["tong_he_thong"] = 0
    data["tong_dien"] = 0
    data["tong_hieu"] = 0
    for tk in data["danh_sach_nick"]:
        data["danh_sach_nick"][tk]["dem"] = 0
    luu_data(data)
    flash("Đã reset toàn bộ lượt đếm về 0.")
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/ping")
def ping():
    return "Bot is alive!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

threading.Thread(target=run_flask, daemon=True).start()

# ==========================================
# 🤖 PHẦN 2: BOT TELEGRAM
# ==========================================
async def main():
    if not BOT_TOKEN:
        log.error("❌ Chưa cấu hình BOT_TOKEN")
        return
        
    # KHOẢN MỤC ĐƯỢC SỬA: Đưa client vào trong hàm main()
    client = TelegramClient("bot_session", API_ID, API_HASH)
    
    await client.start(bot_token=BOT_TOKEN)
    log.info("🚀 Bot Telegram đã trực chiến!")

    @client.on(events.NewMessage)
    async def handler(event):
        msg_text = event.raw_text
        if not msg_text: return
        
        # 1. Lệnh kiểm tra điểm
        if msg_text.strip().lower() == ".check":
            data = doc_data()
            msg = f"📊 **THỐNG KÊ LƯỢT XUẤT HIỆN**\n\n"
            msg += f"👑 **Nhóm Diễn:** {data['tong_dien']} lượt\n"
            msg += f"👑 **Nhóm Hiếu:** {data['tong_hieu']} lượt\n"
            msg += f"🌍 **Tổng Hệ Thống:** {data['tong_he_thong']} lượt\n"
            await event.reply(msg)
            return

        # 2. Xử lý tin nhắn đếm số
        words = re.findall(r'[a-zA-Z0-9_]+', msg_text.lower())
        data = doc_data()
        danh_sach_db = data["danh_sach_nick"]
        
        matched_users = {}
        for word in words:
            if word in danh_sach_db:
                matched_users[word] = matched_users.get(word, 0) + 1

        if not matched_users:
            return 
            
        summary = []
        for tk, times in matched_users.items():
            nhom = danh_sach_db[tk]["nhom"]
            
            data["danh_sach_nick"][tk]["dem"] += times
            data["tong_he_thong"] += times
            if nhom == "dien":
                data["tong_dien"] += times
            else:
                data["tong_hieu"] += times
                
            summary.append(f"✅ Đếm `{tk}` (+{times} lượt)")
            
        luu_data(data)
        reply_msg = "\n".join(summary) + f"\n\n🌍 Tổng hệ thống hiện tại: {data['tong_he_thong']} lượt."
        await event.reply(reply_msg)

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
