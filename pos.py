# شاشة الكاشير التجريبية (POS) - من هنا بيتولد الأوردرات
import sqlite3
import time
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Cafe POS", page_icon="🧾", layout="wide")

auto = st.sidebar.checkbox("تحديث تلقائي كل 10 دقايق", value=True)
if auto:
    st.markdown('<meta http-equiv="refresh" content="600">', unsafe_allow_html=True)

st.title("🧾 شاشة الكاشير (POS تجريبي)")
st.caption("كل ضغطة على الزر = طلب جديد اتسجل في النظام زي ما الكاشير بيسجل فعلاً")

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

c1, c2 = st.columns([1, 2])
if c1.button("➕ طلب جديد", use_container_width=True):
    cursor.execute(
        "INSERT INTO orders (status, created_at, created_epoch) VALUES (?, ?, ?)",
        ("pending",
         datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
         time.time()))
    conn.commit()

pending = cursor.execute(
    "SELECT COUNT(*) FROM orders WHERE status='pending'").fetchone()[0]
c2.metric("⏳ طلبات مستنية التسليم", pending)

st.divider()
st.subheader("آخر الطلبات")
rows = cursor.execute(
    "SELECT id, status, created_at, delivered_at, prep_seconds, customer_no, barista_label "
    "FROM orders ORDER BY id DESC LIMIT 10").fetchall()

if not rows:
    st.info("مفيش طلبات لسه — دوس (طلب جديد) فوق")
else:
    for r in rows:
        oid, status, created, delivered, prep, cust, barista = r
        if status == "pending":
            st.write(f"🟡 **Order #{oid}** — أُنشئ {created} — مستني التسليم")
        else:
            st.write(f"🟢 **Order #{oid}** — أُنشئ {created} — اتسلم {delivered} — "
                     f"تجهيزه اخد {prep:.0f} ثانية — لـ Customer #{cust} بواسطة {barista}")

conn.close()