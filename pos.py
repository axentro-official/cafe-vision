# شاشة الكاشير التجريبية (POS) - نسخة 3 - ستايل مطابق للداشبورد + شبكة كروت
import sqlite3
import time
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Cafe POS", page_icon="🧾", layout="wide")

# ---------- التحديث الحي ----------
auto = st.sidebar.checkbox("🟠 LIVE — تحديث تلقائي كل 10 دقايق", value=True)
if auto:
    st.markdown('<meta http-equiv="refresh" content="600">', unsafe_allow_html=True)

st.sidebar.title("🧾 Cafe POS")
st.sidebar.caption("شاشة الكاشير — توليد الطلبات")
st.sidebar.info(f"آخر تحديث: {time.strftime('%I:%M:%S %p')}")

st.title("🧾 شاشة الكاشير")

# ---------- الوقت بصيغة عربية مقروءة (نفس دالة الداشبورد) ----------
def fmt(sec):
    sec = int(sec)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    parts = []
    if h:
        parts.append("ساعة" if h == 1 else "ساعتان" if h == 2 else f"{h} ساعات")
    if m:
        parts.append("دقيقة" if m == 1 else "دقيقتان" if m == 2 else
                     f"{m} دقائق" if m <= 10 else f"{m} دقيقة")
    if s:
        parts.append("ثانية واحدة" if s == 1 else "ثانيتان" if s == 2 else f"{s} ثانية")
    return " و".join(parts) if parts else "0 ثانية"

def hex_tint(h, a=0.15):
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"

def card(icon, label, value, color):
    vfont = "32px" if len(str(value)) <= 8 else "21px"
    st.markdown(
        f"""
        <div style="background:#171f2b;padding:20px 18px;border-radius:14px;
                    border-left:6px solid {color};margin-bottom:10px;
                    display:flex;align-items:center;gap:14px;">
          <div style="min-width:56px;height:56px;border-radius:12px;
                      background:{hex_tint(color, 0.13)};
                      display:flex;align-items:center;justify-content:center;
                      font-size:28px;">{icon}</div>
          <div style="text-align:right;">
            <div style="font-size:14px;color:#8fa1b3;margin-bottom:4px;">{label}</div>
            <div style="font-size:{vfont};font-weight:800;color:{color};">{value}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------- قاعدة البيانات ----------
conn = sqlite3.connect("cafe.db", timeout=10)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    created_epoch REAL,
    delivered_at TEXT,
    delivered_epoch REAL,
    prep_seconds REAL,
    customer_no INTEGER,
    barista_label TEXT
)
""")
conn.commit()

# ---------- الزر + عداد المستنيين ----------
pending_count = cursor.execute(
    "SELECT COUNT(*) FROM orders WHERE status='pending'").fetchone()[0]

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    if st.button("➕ طلب جديد", use_container_width=True, type="primary"):
        cursor.execute(
            "INSERT INTO orders (status, created_at, created_epoch) VALUES (?, ?, ?)",
            ("pending",
             datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
             time.time()))
        conn.commit()
        st.rerun()
with c2:
    card("⏳", "طلبات مستنية التسليم", pending_count, "#ffd166")

# ---------- إحصائيات ----------
rows_all = cursor.execute(
    "SELECT id, status, created_at, delivered_at, prep_seconds, customer_no, barista_label "
    "FROM orders ORDER BY id DESC").fetchall()

total_o = len(rows_all)
delivered_all = [r for r in rows_all if r[1] == "delivered"]
preps = [r[4] for r in delivered_all if r[4]]

s1, s2, s3 = st.columns(3)
with s1: card("🧾", "إجمالي الطلبات", total_o, "#4da3ff")
with s2: card("✅", "تم تسليمها", len(delivered_all), "#4ade80")
with s3: card("⚡", "متوسط وقت التجهيز",
              fmt(sum(preps)/len(preps)) if preps else "—",
              "#ff5d5d")

st.divider()

# ---------- قسم الطلبات المستنية (شبكة كروت) ----------
pending_rows = [r for r in rows_all if r[1] == "pending"]

st.subheader(f"⏳ مستنية التسليم ({len(pending_rows)})")
if not pending_rows:
    st.markdown(
        """
        <div style="background:#171f2b;border:1px dashed #2a3441;border-radius:12px;
                    padding:18px;text-align:center;color:#8fa1b3;">
          مفيش طلبات مستنية — اضغط (➕ طلب جديد) لما عميل يدفع
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    chunk = 3   # كام كارت في الصف
    for i in range(0, len(pending_rows), chunk):
        cols = st.columns(chunk)
        for j, r in enumerate(pending_rows[i:i + chunk]):
            oid, status, created = r[0], r[1], r[2]
            with cols[j]:
                st.markdown(
                    f"""
                    <div style="background:#171f2b;padding:16px;border-radius:12px;
                                border-left:6px solid #ffd166;margin-bottom:10px;
                                min-height:130px;">
                      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                        <span style="font-size:18px;">🟡</span>
                        <span style="font-size:17px;font-weight:800;color:#ffd166;">Order #{oid}</span>
                      </div>
                      <div style="font-size:12.5px;color:#8fa1b3;margin-bottom:4px;">أُنشئ</div>
                      <div style="font-size:14px;color:#e6edf3;font-weight:600;">{created}</div>
                      <div style="margin-top:10px;">
                        <span style="background:rgba(255,209,102,0.15);color:#ffd166;
                                     font-weight:700;padding:3px 12px;border-radius:7px;
                                     font-size:12px;">مستني التسليم</span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

st.divider()

# ---------- قسم الطلبات المسلمة (شبكة كروت) ----------
st.subheader("✅ آخر الطلبات المسلمة")

if not delivered_all:
    st.markdown(
        """
        <div style="background:#171f2b;border:1px dashed #2a3441;border-radius:12px;
                    padding:18px;text-align:center;color:#8fa1b3;">
          لسه مفيش تسليمات — أول ما الكاميرا تأكد تسليم، الطلب هيظهر هنا 🟢
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    chunk = 3   # كام كارت في الصف
    for i in range(0, min(len(delivered_all), 9), chunk):
        cols = st.columns(chunk)
        for j, r in enumerate(delivered_all[i:i + chunk]):
            oid, status, created, delivered, prep, cust, barista = r
            prep_txt = fmt(prep) if prep else "—"
            cust_txt = f"Customer #{cust}" if cust else "—"
            with cols[j]:
                st.markdown(
                    f"""
                    <div style="background:#171f2b;padding:16px;border-radius:12px;
                                border-left:6px solid #4ade80;margin-bottom:10px;
                                min-height:180px;">
                      <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
                        <span style="font-size:18px;">🟢</span>
                        <span style="font-size:17px;font-weight:800;color:#4ade80;">Order #{oid}</span>
                      </div>
                      <div style="margin-bottom:10px;">
                        <span style="background:rgba(74,222,128,0.15);color:#4ade80;
                                     font-weight:700;padding:3px 12px;border-radius:7px;
                                     font-size:12px;">⚡ تجهيز: {prep_txt}</span>
                      </div>
                      <div dir="rtl" style="font-size:12.5px;color:#8fa1b3;line-height:1.9;">
                        <div>🕒 أُنشئ: <span style="color:#e6edf3;">{created}</span></div>
                        <div>📦 اتسلم: <span style="color:#e6edf3;">{delivered}</span></div>
                        <div>👤 للعميل: <span style="color:#e6edf3;">{cust_txt}</span></div>
                        <div>👨‍🍳 بواسطة: <span style="color:#e6edf3;">{barista or "غير معروف"}</span></div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

conn.close()