# -*- coding: utf-8 -*-
"""
Hệ thống QUẢN LÝ ĐIỂM + ĐẾM LƯỢT qua Telegram Bot + Web Admin.
Cập nhật:
- Hiển thị TỔNG LƯỢT (thay vì tổng điểm) trên các bảng màu.
- Bổ sung chức năng chỉnh sửa trực tiếp số Lượt trên giao diện Web.
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

MAIN_DOC_ID = "main_data_v3"

DEFAULT_DOC = {
    "diem": {},
    "so_luot": {},       
    "app_names": {},     
    "tong_luot": 0,
    "luot_dien": 0,
    "luot_hieu": 0,
    "quan_ly": {},
    "trang_thai": {},
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
        collection = db_client["telegram_bot"]["diem_so_v3"]
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
        "diem": doc.get("diem", {}),
        "so_luot": doc.get("so_luot", {}),
        "app_names": doc.get("app_names", {}),
        "tong_luot": doc.get("tong_luot", 0),
        "luot_dien": doc.get("luot_dien", 0),
        "luot_hieu": doc.get("luot_hieu", 0),
        "quan_ly": doc.get("quan_ly", {}),
        "trang_thai": doc.get("trang_thai", {}),
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
:root{
  --bg:#f5f7fb; --card:#ffffff; --ink:#1f2430; --muted:#6b7280;
  --primary:#4f6bf6; --primary-dark:#3b52d1;
  --green:#16a34a; --green-bg:#e8f8ee;
  --red:#e0384a; --red-bg:#fdeceb;
  --border:#e7e9f2; --radius:14px;
}
*{box-sizing:border-box;}
body{ background:var(--bg); color:var(--ink); margin:0; font-family:sans-serif; }
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px;}
.top{display:flex;align-items:center;justify-content:space-between;margin-bottom:22px;}
.logout{color:var(--muted);text-decoration:none;font-size:13px;font-weight:600;padding:8px 14px;border:1px solid var(--border);border-radius:10px;background:var(--card);}
.logout:hover{background:var(--red-bg);color:var(--red);border-color:var(--red);}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:22px;}
.stat{border-radius:var(--radius);padding:20px 22px;color:#fff;position:relative;}
.stat small{opacity:.85;font-weight:600;font-size:12.5px;}
.stat h2{margin:6px 0 0;font-size:28px;}
.stat.total{background:linear-gradient(135deg,#4f6bf6,#7c3aed);}
.stat.dien{background:linear-gradient(135deg,#0ea5e9,#0284c7);}
.stat.hieu{background:linear-gradient(135deg,#f43f5e,#e11d48);}
.stat-row{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;}
.stat-reset{background:rgba(255,255,255,.2);border:1px solid rgba(255,255,255,.4);color:#fff;font-size:12px;padding:6px 11px;border-radius:8px;cursor:pointer;}
.card{background:var(--card);border-radius:var(--radius);border:1px solid var(--border);box-shadow:0 8px 24px rgba(30,40,90,.05);}
.card-pad{padding:18px 20px;}
.flash{padding:11px 16px;border-radius:10px;background:var(--green-bg);color:var(--green);font-weight:bold;font-size:14px;margin-bottom:16px;}
.tabs{display:flex;gap:6px;padding:6px;background:#eef1f8;border-radius:12px;margin-bottom:18px;}
.tabs a{flex:1;text-align:center;padding:10px 14px;border-radius:9px;font-weight:bold;font-size:14px;color:var(--muted);text-decoration:none;}
.tabs a.active{background:#fff;color:var(--primary);box-shadow:0 2px 6px rgba(0,0,0,.08);}
.toolbar{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px;}
.search{padding:8px 14px;border:1px solid var(--border);border-radius:10px;font-size:13px;outline:none;}
.search:focus{border-color:var(--primary);}
.batch{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;}
.batch button{border:none;border-radius:9px;padding:9px 14px;font-size:13px;font-weight:bold;cursor:pointer;color:#fff;}
.b-dien{background:#0ea5e9;} .b-hieu{background:#f43f5e;} .b-chung{background:#94a3b8;} .b-reset{background:#f59e0b;} .b-xoa{background:var(--red);}
table{width:100%;border-collapse:collapse;font-size:14px;}
thead th{text-align:left;color:var(--muted);font-size:13px;padding:10px 12px;border-bottom:2px solid var(--border);}
tbody td{padding:11px 12px;border-bottom:1px solid var(--border);}
.tag-on{color:var(--green);font-weight:bold;font-size:13px;}
.tag-off{color:var(--red);font-weight:bold;font-size:13px;}
.badge{background:#eef1f8;color:#4b5570;font-size:12px;font-weight:bold;padding:4px 8px;border-radius:6px;}
.score-cell{display:flex;gap:6px;align-items:center;}
.score-cell input{width:75px;padding:7px;border:1px solid var(--border);border-radius:8px; font-weight:bold; text-align:center;}
.luot-input{color: var(--primary);}
.save-btn{background:var(--primary);color:#fff;border:none;border-radius:8px;padding:8px 12px;font-weight:bold;cursor:pointer;}
"""

PAGE_TEMPLATE = """
<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><title>Quản Lý Điểm Số</title><style>{{ style }}</style></head>
<body>
<div class="wrap">
  <div class="top"><h2>🚀 Quản Lý Tài Khoản Hệ Thống</h2><a class="logout" href="{{ url_for('logout') }}">Đăng xuất</a></div>
  {% if get_flashed_messages() %}{% for m in get_flashed_messages() %}<div class="flash">✅ {{ m }}</div>{% endfor %}{% endif %}

  <div class="stats">
    <div class="stat total"><small>🌍 TỔNG HỆ THỐNG</small><div class="stat-row"><h2>{{ data.tong_luot }} Lượt</h2>
        <form action="{{ url_for('reset_fund') }}" method="POST" onsubmit="return confirm('Reset?');"><input type="hidden" name="field" value="tong"><input type="hidden" name="tab" value="{{ tab }}"><button class="stat-reset" type="submit">↺ Reset</button></form>
    </div></div>
    <div class="stat dien"><small>📘 QUỸ DIỄN</small><div class="stat-row"><h2>{{ data.luot_dien }} Lượt</h2>
        <form action="{{ url_for('reset_fund') }}" method="POST" onsubmit="return confirm('Reset?');"><input type="hidden" name="field" value="dien"><input type="hidden" name="tab" value="{{ tab }}"><button class="stat-reset" type="submit">↺ Reset</button></form>
    </div></div>
    <div class="stat hieu"><small>📕 QUỸ HIẾU</small><div class="stat-row"><h2>{{ data.luot_hieu }} Lượt</h2>
        <form action="{{ url_for('reset_fund') }}" method="POST" onsubmit="return confirm('Reset?');"><input type="hidden" name="field" value="hieu"><input type="hidden" name="tab" value="{{ tab }}"><button class="stat-reset" type="submit">↺ Reset</button></form>
    </div></div>
  </div>

  <div class="tabs">
    <a href="{{ url_for('index', tab='dien') }}" class="{{ 'active' if tab=='dien' else '' }}">Tab Diễn</a>
    <a href="{{ url_for('index', tab='hieu') }}" class="{{ 'active' if tab=='hieu' else '' }}">Tab Hiếu</a>
    <a href="{{ url_for('index', tab='chung') }}" class="{{ 'active' if tab=='chung' else '' }}">Danh Sách Chung</a>
  </div>

  <div class="card card-pad" style="margin-bottom: 18px; border-left: 5px solid var(--primary);">
    <h3 style="margin-top:0; margin-bottom:12px; font-size:16px;">➕ Khai báo tài khoản theo dõi</h3>
    <form action="{{ url_for('add_acc') }}" method="POST" style="display:flex; gap:10px; flex-wrap:wrap;">
        <input type="text" name="tk" placeholder="Nhập tên tài khoản (VD: anhba191)..." required class="search" style="flex:1;">
        <select name="owner" class="search" style="width:180px;">
            <option value="dien" {% if tab=='dien' %}selected{% endif %}>Thêm vào Quỹ Diễn</option>
            <option value="hieu" {% if tab=='hieu' %}selected{% endif %}>Thêm vào Quỹ Hiếu</option>
            <option value="chung" {% if tab=='chung' %}selected{% endif %}>Thêm vào Chung</option>
        </select>
        <button type="submit" class="save-btn" style="padding:0 20px;">Thêm vào DB</button>
    </form>
  </div>

  <div class="card card-pad">
    <div class="toolbar"><input class="search" id="searchBox" placeholder="🔎 Tìm kiếm tên nick..." onkeyup="filterSearch()" style="width:100%;"></div>
    
    <form action="{{ url_for('batch_action') }}" method="POST">
      <input type="hidden" name="tab" value="{{ tab }}">
      <div class="batch">
        <button class="b-dien" type="submit" name="action_type" value="chuyen_dien">➡️ Chuyển Diễn</button>
        <button class="b-hieu" type="submit" name="action_type" value="chuyen_hieu">➡️ Chuyển Hiếu</button>
        <button class="b-chung" type="submit" name="action_type" value="chuyen_chung">↩️ Rút về Chung</button>
        <button class="b-reset" type="submit" name="action_type" value="reset" onclick="return confirm('Reset Điểm & Lượt?');">🧹 Reset Điểm & Lượt</button>
        <button class="b-xoa" type="submit" name="action_type" value="xoa" onclick="return confirm('Xóa vĩnh viễn?');">🗑️ Xóa</button>
      </div>
      <table id="accTable">
        <thead>
          <tr>
            <th style="width:36px;"><input type="checkbox" onclick="toggleAll(this)"></th>
            <th>Trạng thái</th><th>Tên tài khoản</th><th>App</th><th>Lượt</th><th>Điểm số</th>
          </tr>
        </thead>
        <tbody>
        {% for tk, diem, luot, app_name, status in rows %}
          <tr>
            <td><input type="checkbox" name="tks" value="{{ tk }}"></td>
            <td>{% if status == 'khoa' %}<span class="tag-off">Bị khóa</span>{% else %}<span class="tag-on">Hoạt động</span>{% endif %}</td>
            <td style="font-weight:bold;">{{ tk }}</td>
            <td><span class="badge">{{ app_name }}</span></td>
            <td>
                <!-- Ô Nhập Lượt -->
                <input type="number" form="form_{{ tk }}" name="new_luot" value="{{ luot }}" class="luot-input" style="width:60px; padding:7px; border:1px solid var(--border); border-radius:8px; font-weight:bold; text-align:center;">
            </td>
            <td>
              <div class="score-cell">
                <!-- Ô Nhập Điểm -->
                <input type="number" form="form_{{ tk }}" name="new_score" value="{{ diem }}">
                <button class="save-btn" type="submit" form="form_{{ tk }}">Lưu</button>
              </div>
            </td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </form>

    {% for tk, diem, luot, app_name, status in rows %}
    <!-- Form gộp dùng để lưu cả Điểm và Lượt -->
    <form id="form_{{ tk }}" action="{{ url_for('edit_data') }}" method="POST" style="display:none;">
      <input type="hidden" name="tk" value="{{ tk }}">
      <input type="hidden" name="tab" value="{{ tab }}">
    </form>
    {% endfor %}
  </div>
</div>
<script>
function toggleAll(src){ document.querySelectorAll('input[name=tks]').forEach(cb => cb.checked = src.checked); }
function filterSearch(){
  const q = document.getElementById('searchBox').value.toLowerCase();
  document.querySelectorAll('#accTable tbody tr').forEach(row => {
    row.style.display = row.innerText.toLowerCase().includes(q) ? '' : 'none';
  });
}
</script>
</body></html>
"""

def _set_owner(data, tk, new_owner):
    old_owner = data["quan_ly"].get(tk, "chung")
    if old_owner == new_owner: return
    
    # Chuyển đổi Lượt đếm khi đổi nhóm
    luot = data["so_luot"].get(tk, 0)
    
    if old_owner == "dien": data["luot_dien"] -= luot
    elif old_owner == "hieu": data["luot_hieu"] -= luot
    
    if new_owner == "dien": data["luot_dien"] += luot
    elif new_owner == "hieu": data["luot_hieu"] += luot
    
    if new_owner == "chung": data["quan_ly"].pop(tk, None)
    else: data["quan_ly"][tk] = new_owner

def _rows_for_tab(data, owner_key):
    items = []
    for tk, diem in data["diem"].items():
        if data["quan_ly"].get(tk, "chung") == owner_key:
            luot = data.get("so_luot", {}).get(tk, 0)
            app_name = data.get("app_names", {}).get(tk, "Chưa rõ")
            status = data["trang_thai"].get(tk, "hoat_dong")
            items.append((tk, diem, luot, app_name, status))
    items.sort(key=lambda x: x[1], reverse=True)
    return items

@app.route("/", methods=["GET", "POST"])
def index():
    if not session.get("logged_in"):
        if request.method == "POST":
            if request.form.get("password") == WEB_PASSWORD:
                session["logged_in"] = True
                return redirect(url_for("index"))
            return "Sai mật khẩu!"
        return '<form method="POST" style="text-align:center;margin-top:50px;"><h3>Đăng nhập</h3><input type="password" name="password"><button>Vào</button></form>'
    
    tab = request.args.get("tab", "dien")
    data = doc_data()
    return render_template_string(PAGE_TEMPLATE, data=data, rows=_rows_for_tab(data, tab), tab=tab, style=BASE_STYLE)

@app.route("/add_acc", methods=["POST"])
def add_acc():
    if not session.get("logged_in"): return redirect(url_for("index"))
    tk = request.form.get("tk").strip().lower()
    owner = request.form.get("owner")
    data = doc_data()
    if tk and tk not in data["diem"]:
        data["diem"][tk] = 0
        data["so_luot"][tk] = 0
        data["quan_ly"][tk] = owner
        data["trang_thai"][tk] = "hoat_dong"
        luu_data(data)
        flash(f"Đã khai báo tài khoản '{tk}' vào hệ thống.")
    return redirect(url_for("index", tab=owner))

@app.route("/reset_fund", methods=["POST"])
def reset_fund():
    if not session.get("logged_in"): return redirect(url_for("index"))
    data = doc_data()
    field = request.form.get("field")
    if field == "tong": data["tong_luot"] = 0
    elif field == "dien": data["luot_dien"] = 0
    elif field == "hieu": data["luot_hieu"] = 0
    luu_data(data)
    flash(f"Đã reset số lượt.")
    return redirect(url_for("index", tab=request.form.get("tab")))

@app.route("/batch_action", methods=["POST"])
def batch_action():
    if not session.get("logged_in"): return redirect(url_for("index"))
    data = doc_data()
    action_type = request.form.get("action_type")
    tks = request.form.getlist("tks")
    for tk in tks:
        if action_type == "chuyen_dien": _set_owner(data, tk, "dien")
        elif action_type == "chuyen_hieu": _set_owner(data, tk, "hieu")
        elif action_type == "chuyen_chung": _set_owner(data, tk, "chung")
        elif action_type == "reset":
            data["diem"][tk] = 0
            # Hoàn trả lại số lượt đã xóa vào tổng
            old_luot = data["so_luot"].get(tk, 0)
            owner = data["quan_ly"].get(tk, "chung")
            data["tong_luot"] -= old_luot
            if owner == "dien": data["luot_dien"] -= old_luot
            elif owner == "hieu": data["luot_hieu"] -= old_luot
            data["so_luot"][tk] = 0
            
        elif action_type == "xoa":
            old_luot = data["so_luot"].get(tk, 0)
            owner = data["quan_ly"].get(tk, "chung")
            data["tong_luot"] -= old_luot
            if owner == "dien": data["luot_dien"] -= old_luot
            elif owner == "hieu": data["luot_hieu"] -= old_luot
            
            data["diem"].pop(tk, None)
            data["so_luot"].pop(tk, None)
            data["quan_ly"].pop(tk, None)
            data["trang_thai"].pop(tk, None)
            data["app_names"].pop(tk, None)
    luu_data(data)
    flash(f"Đã xử lý {len(tks)} tài khoản.")
    return redirect(url_for("index", tab=request.form.get("tab")))

@app.route("/edit_data", methods=["POST"])
def edit_data():
    if not session.get("logged_in"): return redirect(url_for("index"))
    data = doc_data()
    tk = request.form.get("tk")
    new_score = request.form.get("new_score")
    new_luot = request.form.get("new_luot")
    
    if tk:
        # Cập nhật Điểm
        if new_score != "" and new_score is not None:
            data["diem"][tk] = int(new_score)
            
        # Cập nhật Lượt
        if new_luot != "" and new_luot is not None:
            new_val_luot = int(new_luot)
            old_val_luot = data["so_luot"].get(tk, 0)
            delta_luot = new_val_luot - old_val_luot
            
            data["so_luot"][tk] = new_val_luot
            data["tong_luot"] += delta_luot
            
            owner = data["quan_ly"].get(tk, "chung")
            if owner == "dien": data["luot_dien"] += delta_luot
            elif owner == "hieu": data["luot_hieu"] += delta_luot

        luu_data(data)
        flash(f"Đã lưu dữ liệu cho {tk}.")
        
    return redirect(url_for("index", tab=request.form.get("tab")))

@app.route("/ping")
def ping(): return "OK"
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False, use_reloader=False)

threading.Thread(target=run_flask, daemon=True).start()

# ==========================================
# 🤖 PHẦN 2: BOT TELEGRAM
# ==========================================
async def main():
    if not BOT_TOKEN:
        log.error("❌ Chưa cấu hình BOT_TOKEN")
        return
        
    client = TelegramClient("bot_session", API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    log.info("🚀 Bot Telegram đã trực chiến!")

    @client.on(events.NewMessage)
    async def handler(event):
        msg_text = event.raw_text
        if not msg_text: return
        
        data = doc_data()
        
        # --- Lệnh .check xem bảng điểm ---
        if msg_text.strip().lower() in (".check", "check"):
            msg = "📊 **BẢNG ĐIỂM & SỐ LƯỢT:**\n\n"
            team = {"dien": [], "hieu": [], "chung": []}
            for k, v in data["diem"].items():
                owner = data["quan_ly"].get(k, "chung")
                team[owner].append((k, v, data["so_luot"].get(k, 0)))
                
            for k_team, title, icon in [("dien", "TAB DIỄN", "📘"), ("hieu", "TAB HIẾU", "📕")]:
                if team[k_team]:
                    msg += f"{icon} **{title}**\n"
                    for i, (name, pts, luot) in enumerate(sorted(team[k_team], key=lambda x: x[1], reverse=True), 1):
                        msg += f"  {i}. {name}: {pts}đ ({luot} lượt)\n"
                    msg += "\n"
                    
            msg += f"----------------------------\n🌍 **TỔNG LƯỢT HỆ THỐNG: {data['tong_luot']}**\n"
            msg += f"👑 **Diễn**: {data['luot_dien']} lượt | 👑 **Hiếu**: {data['luot_hieu']} lượt\n👉 {ADMIN_URL}"
            await event.reply(msg)
            return

        # --- Phân tích tin nhắn cộng điểm / khóa nick ---
        pattern = r'#([a-zA-Z0-9_]+)\s+([a-zA-Z0-9_]+)\s+(\d+|đã bị khóa)'
        matches = re.findall(pattern, msg_text, re.IGNORECASE)
        
        if not matches: return

        summary = []
        diem_ok = False
        
        for m in matches:
            app = m[0].upper()
            tk = m[1].lower()
            val = m[2].lower()

            # QUAN TRỌNG: Chỉ xử lý nếu tk đã có trong DB
            if tk not in data["diem"]:
                continue
                
            diem_ok = True
            data.setdefault("app_names", {})[tk] = app

            if "khóa" in val or "khoa" in val:
                data["trang_thai"][tk] = "khoa"
                summary.append(f"🔴 `{tk}`: Bị khóa")
            else:
                diem_cong = int(val)
                data["diem"][tk] += diem_cong
                
                # Cập nhật số Lượt
                data.setdefault("so_luot", {})[tk] = data.get("so_luot", {}).get(tk, 0) + 1
                data["tong_luot"] += 1
                owner = data["quan_ly"].get(tk, "chung")
                if owner == "dien": data["luot_dien"] += 1
                elif owner == "hieu": data["luot_hieu"] += 1
                
                data["trang_thai"][tk] = "hoat_dong"
                
                luot_hien_tai = data["so_luot"][tk]
                summary.append(f"✅ `{tk}`: +{diem_cong}đ (Lượt {luot_hien_tai})")

        if diem_ok:
            luu_data(data)
            await event.reply("\n".join(summary) + f"\n\n🌍 TỔNG SỐ LƯỢT HỆ THỐNG: {data['tong_luot']}")

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
