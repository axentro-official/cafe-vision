# الداشبورد الحية - Cafe Vision (نسخة 3 - ستايل احترافي)
import sqlite3
import time
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Cafe Vision", page_icon="☕", layout="wide")

# ---------- التحديث الحي ----------
live = st.sidebar.checkbox("🔴 LIVE — تحديث تلقائي كل 10 دقايق", value=True)
REFRESH = 600
st.markdown(f'<meta http-equiv="refresh" content="{REFRESH}">', unsafe_allow_html=True)

st.sidebar.title("☕ Cafe Vision")
st.sidebar.caption("تحليل ذكي من الكاميرا")
st.sidebar.info(f"آخر تحديث: {time.strftime('%I:%M:%S %p')}")

st.title("☕ لوحة تحكم الكافيه")

# ---------- قراءة البيانات ----------
@st.cache_data(ttl=REFRESH)
def load_data():
    conn = sqlite3.connect("cafe.db")
    visits = conn.execute(
        "SELECT id, customer_no, entry_time, exit_time, wait_seconds "
        "FROM visits ORDER BY id").fetchall()
    orders = conn.execute(
        "SELECT id, status, created_at, delivered_at, prep_seconds, customer_no, barista_label "
        "FROM orders ORDER BY id").fetchall()
    conn.close()
    return visits, orders

visits, orders = load_data()

if not visits and not orders:
    st.warning("مفيش بيانات لسه — شغّل step6.py و pos.py وسيبهم شغالين 😄")
    st.stop()

def fmt(sec):
    m, s = int(sec // 60), int(sec % 60)
    return f"{m:02d}:{s:02d}"

def wait_color(w):
    if w < 60:  return "#4ade80"
    if w < 90:  return "#ffd166"
    return "#ff5d5d"

def card(label, value, color):
    st.markdown(
        f"""
        <div style="background:#171f2b;padding:22px 18px;border-radius:14px;
                    border-right:6px solid {color};margin-bottom:10px;">
          <div style="font-size:14px;color:#8fa1b3;margin-bottom:6px;">{label}</div>
          <div style="font-size:34px;font-weight:800;color:{color};">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------- ستايل موحد لكل الرسومات (دي سر الشكل الاحترافي) ----------
def style_fig(fig, height=320):
    fig.update_layout(
        paper_bgcolor="#171f2b",      # خلفية الكارت
        plot_bgcolor="#171f2b",
        font=dict(color="#e6edf3", family="Segoe UI"),
        height=height,
        margin=dict(t=30, b=30, l=30, r=30),
    )
    fig.update_xaxes(gridcolor="#2a3441", zerolinecolor="#2a3441",
                     tickfont=dict(color="#8fa1b3"))
    fig.update_yaxes(gridcolor="#2a3441", zerolinecolor="#2a3441",
                     tickfont=dict(color="#8fa1b3"))
    return fig

# ================= قسم الزيارات =================
if visits:
    waits = [v[4] for v in visits]
    total = len(visits)
    avg = sum(waits) / total
    longest = max(waits)

    c1, c2, c3, c4 = st.columns(4)
    with c1: card("إجمالي الزيارات", total, "#4da3ff")
    with c2: card("متوسط الانتظار", fmt(avg), "#ffd166")
    with c3: card("أطول انتظار", fmt(longest), "#ff5d5d")
    with c4: card("عدد العملاء", len(set(v[1] for v in visits)), "#4ade80")

    st.divider()

    ok = sum(1 for w in waits if w < 60)
    mid = sum(1 for w in waits if 60 <= w < 90)
    alert = sum(1 for w in waits if w >= 90)

    colA, colB = st.columns([1, 2])

    with colA:
        st.subheader("توزيع الحالات")
        donut = go.Figure(go.Pie(
            values=[ok, mid, alert],
            labels=["طبيعي", "انتظار", "تأخير"],
            hole=0.65,
            marker=dict(colors=["#4ade80", "#ffd166", "#ff5d5d"],
                        line=dict(color="#171f2b", width=3)),
            textinfo="percent",
            textfont=dict(color="#e6edf3", size=14),
            hovertemplate="%{label}: %{value} زيارة<br>%{percent}<extra></extra>",
        ))
        donut.update_layout(
            annotations=[dict(text=f"<b>{total}</b><br>زيارة", x=0.5, y=0.5,
                              font=dict(size=22, color="#e6edf3"),
                              showarrow=False)],
            showlegend=True,
            legend=dict(font=dict(color="#8fa1b3"), orientation="h",
                        yanchor="bottom", y=-0.15, x=0.5, xanchor="center"),
        )
        st.plotly_chart(style_fig(donut, 320), use_container_width=True)

    with colB:
        st.subheader("وقت الانتظار لكل زيارة")
        labels = [f"#{v[0]}" for v in visits]
        colors = [wait_color(w) for w in waits]
        fig = go.Figure(go.Bar(
            x=labels, y=waits, marker_color=colors,
            marker_line=dict(width=0),
            hovertemplate="زيارة %{x}<br>انتظر: %{y:.0f} ثانية<extra></extra>",
        ))
        fig.update_layout(barcornerradius=8)
        fig.add_hline(y=60, line_dash="dash", line_color="#ffd166",
                      annotation_text="حد الأصفر", annotation_font_color="#ffd166")
        fig.add_hline(y=90, line_dash="dash", line_color="#ff5d5d",
                      annotation_text="حد الأحمر", annotation_font_color="#ff5d5d")
        st.plotly_chart(style_fig(fig, 320), use_container_width=True)

    st.divider()

    # ساعة الذروة
    hours = {}
    for v in visits:
        parts = v[2].split()
        if len(parts) == 3:
            h = f"{parts[1][:2]} {parts[2]}"
            hours[h] = hours.get(h, 0) + 1
    if hours:
        peak = max(hours, key=hours.get)
        st.info(f"⏰ ساعة الذروة حتى الآن: **{peak}** — عدد الزيارات فيها: **{hours[peak]}**")

    # آخر الزيارات
    st.subheader("آخر الزيارات")
    recent = list(reversed(visits[-15:]))
    n = len(recent)
    tbl = go.Figure(go.Table(
        header=dict(
            values=["⏱ الانتظار", "الخروج", "الدخول", "العميل", "الزيارة"],
            fill_color="#1c2634",
            font=dict(color="#9fb3c8", size=14),
            align="center", height=36),
        cells=dict(
            values=[
                [fmt(v[4]) for v in recent],
                [v[3] for v in recent],
                [v[2] for v in recent],
                [f"Customer #{v[1]}" for v in recent],
                [f"#{v[0]}" for v in recent],
            ],
            fill_color="#171f2b",
            font=dict(color=[
                [wait_color(v[4]) for v in recent],
                ["#e6edf3"] * n,
                ["#e6edf3"] * n,
                ["#e6edf3"] * n,
                ["#e6edf3"] * n,
            ], size=13),
            align="center", height=32),
    ))
    tbl.update_layout(height=max(300, 90 + 34 * n), margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(tbl, use_container_width=True)

# ================= قسم الطلبات والباريستا =================
st.divider()
st.subheader("🧾 الطلبات والباريستا")

if not orders:
    st.info("مفيش طلبات لسه — دوس (طلب جديد) في صفحة الكاشير")
else:
    delivered = [o for o in orders if o[1] == "delivered"]
    pending_o = [o for o in orders if o[1] == "pending"]
    preps = [o[4] for o in delivered if o[4]]

    o1, o2, o3, o4 = st.columns(4)
    with o1: card("إجمالي الطلبات", len(orders), "#4da3ff")
    with o2: card("تم تسليمها", len(delivered), "#4ade80")
    with o3: card("مستنية التسليم", len(pending_o), "#ffd166")
    with o4: card("متوسط وقت التجهيز",
                  f"{sum(preps)/len(preps):.0f} ثانية" if preps else "—",
                  "#ff5d5d")

    if delivered:
        perf = {}
        for o in delivered:
            b = o[6] or "غير معروف"
            perf.setdefault(b, []).append(o[4])
        rows_b = sorted(perf.items(), key=lambda kv: -len(kv[1]))
        best_barista = rows_b[0][0]
        best_count = len(rows_b[0][1])

        st.divider()

        # جدول الباريستات + رسم التجهيز جنب بعض
        colT, colG = st.columns([1, 2])

        with colT:
            st.markdown("##### 👨‍🍳 أداء الباريستات")
            # كارت أفضل باريستا
            st.markdown(
                f"""
                <div style="background:#171f2b;padding:16px;border-radius:14px;
                            border-right:6px solid #4da3ff;margin-bottom:12px;text-align:center;">
                  <div style="font-size:13px;color:#8fa1b3;">🏆 الأعلى إنتاجية</div>
                  <div style="font-size:20px;font-weight:800;color:#4da3ff;margin-top:4px;">{best_barista}</div>
                  <div style="font-size:13px;color:#8fa1b3;margin-top:4px;">{best_count} طلب</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            bar_tbl = go.Figure(go.Table(
                header=dict(
                    values=["📊 أوردرات", "⏱ متوسط التجهيز", "👨‍🍳 الباريستا"],
                    fill_color="#1c2634",
                    font=dict(color="#9fb3c8", size=13), align="center", height=34),
                cells=dict(
                    values=[
                        [f"{len(v)}" for b, v in rows_b],
                        [fmt(sum(v)/len(v)) for b, v in rows_b],
                        [b for b, v in rows_b],
                    ],
                    fill_color="#171f2b",
                    font=dict(color=[
                        ["#4ade80"] * len(rows_b),
                        ["#ffd166"] * len(rows_b),
                        ["#e6edf3"] * len(rows_b),
                    ], size=13),
                    align="center", height=30)))
            bar_tbl.update_layout(height=max(200, 80 + 32 * len(rows_b)),
                                  margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(bar_tbl, use_container_width=True)

        with colG:
            st.markdown("##### ⏱ وقت تجهيز كل أوردر")
            d_labels = [f"#{o[0]}" for o in delivered]
            d_vals = [o[4] or 0 for o in delivered]
            avg_prep = sum(d_vals) / len(d_vals)
            d_colors = ["#4ade80" if w < avg_prep else "#ffd166" if w < avg_prep * 1.5 else "#ff5d5d"
                        for w in d_vals]
            d_fig = go.Figure(go.Bar(
                x=d_labels, y=d_vals, marker_color=d_colors,
                hovertemplate="Order %{x}<br>تجهيز: %{y:.0f} ثانية<extra></extra>",
            ))
            d_fig.update_layout(barcornerradius=8)
            d_fig.add_hline(y=avg_prep, line_dash="dash", line_color="#4da3ff",
                            annotation_text=f"المتوسط: {fmt(avg_prep)}",
                            annotation_font_color="#4da3ff")
            st.plotly_chart(style_fig(d_fig, 340), use_container_width=True)