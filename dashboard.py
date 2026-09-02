# الداشبورد الحية - Cafe Vision (نسخة 6 - وقت عربي مقروء + بادجات الذروة)
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

# ---------- الوقت بصيغة عربية مقروءة ----------
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

def wait_color(w):
    if w < 60:  return "#4ade80"
    if w < 90:  return "#ffd166"
    return "#ff5d5d"

def wait_status(w):
    if w < 60:  return "● جيد"
    if w < 90:  return "● متوسط"
    return "● مرتفع"

def hex_tint(h, a=0.15):
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"

def split_dt(s):
    p = s.split()
    if len(p) == 3:
        return p[0], p[1] + " " + p[2]
    return "", s

# ---------- كارت الريفرنس: أيقونة في مربع ملون + شريط جانبي ----------
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

# ---------- ستايل موحد للرسومات ----------
def style_fig(fig, height=320):
    fig.update_layout(
        paper_bgcolor="#171f2b",
        plot_bgcolor="#171f2b",
        font=dict(color="#e6edf3", family="Segoe UI"),
        height=height,
        margin=dict(t=40, b=40, l=40, r=40),
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
    with c1: card("📊", "إجمالي الزيارات", total, "#4da3ff")
    with c2: card("🕐", "متوسط الانتظار", fmt(avg), "#ffd166")
    with c3: card("⏰", "أطول انتظار", fmt(longest), "#ff5d5d")
    with c4: card("👥", "عدد العملاء", len(set(v[1] for v in visits)), "#4ade80")

    st.divider()

    ok = sum(1 for w in waits if w < 60)
    mid = sum(1 for w in waits if 60 <= w < 90)
    alert = sum(1 for w in waits if w >= 90)

    # في الريفرنس: رسم الانتظار شمال (أعرض) + الدونات يمين
    colBar, colDonut = st.columns([3, 2])

    with colBar:
        st.markdown("##### وقت الانتظار لكل زيارة")
        labels = [str(v[0]) for v in visits]
        colors = [wait_color(w) for w in waits]
        hover_texts = [fmt(w) for w in waits]
        fig = go.Figure(go.Bar(
            x=labels, y=waits, marker_color=colors,
            marker_line=dict(width=0),
            customdata=hover_texts,
            hovertemplate="زيارة %{x}<br>انتظر: %{customdata}<extra></extra>",
        ))
        
        fig.update_xaxes(type="category")
        fig.update_layout(barcornerradius=8)
        fig.add_hline(y=60, line_dash="dash", line_color="#ffd166", line_width=2)
        fig.add_hline(y=90, line_dash="dash", line_color="#ff5d5d", line_width=2)
        fig.update_xaxes(title="الزيارات (بالترتيب)")
        fig.update_yaxes(title="الوقت (ثانية)")
        st.plotly_chart(style_fig(fig, 340), use_container_width=True)

    with colDonut:
        st.markdown("##### توزيع الحالات")
        donut = go.Figure(go.Pie(
            values=[ok, mid, alert],
            labels=["أقل من 60 ثانية", "من 60 إلى 90 ثانية", "أكثر من 90 ثانية"],
            hole=0.62,
            marker=dict(colors=["#4ade80", "#ffd166", "#ff5d5d"],
                        line=dict(color="#171f2b", width=3)),
            textinfo="percent",
            textposition="outside",
            textfont=dict(color="#e6edf3", size=13),
            hovertemplate="%{label}: %{value} زيارة<br>%{percent}<extra></extra>",
        ))
        donut.update_layout(
            annotations=[dict(text=f"<b>{total}</b>", x=0.5, y=0.5,
                              font=dict(size=30, color="#e6edf3"),
                              showarrow=False)],
            showlegend=True,
            legend=dict(font=dict(color="#8fa1b3"), orientation="v",
                        x=1.0, y=0.5, xanchor="left", yanchor="middle"),
        )
        st.plotly_chart(style_fig(donut, 340), use_container_width=True)

    st.divider()

    # ---------- ساعة الذروة (بادجات منسقة - كل عنصر معزول) ----------
    hours = {}
    for v in visits:
        parts = v[2].split()
        if len(parts) == 3:
            h = f"{parts[1][:2]}|{parts[2]}"
            hours[h] = hours.get(h, 0) + 1

    if hours:
        peak_key = max(hours, key=hours.get)
        ph, pampm = peak_key.split("|")
        peak_text = f"{int(ph)}:00 {'مساءً' if pampm == 'PM' else 'صباحاً'}"
        st.markdown(
            f"""
            <div dir="rtl" style="background:#171f2b;border:1px solid #2a3441;
                        border-radius:12px;padding:14px 18px;
                        display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
              <span style="font-size:22px;">⏰</span>
              <span style="font-size:15px;color:#e6edf3;">ساعة الذروة حتى الآن</span>
              <span style="background:rgba(255,209,102,0.15);color:#ffd166;font-weight:800;
                           padding:5px 16px;border-radius:8px;font-size:16px;">{peak_text}</span>
              <span style="font-size:15px;color:#e6edf3;">عدد الزيارات فيها</span>
              <span style="background:rgba(74,222,128,0.15);color:#4ade80;font-weight:800;
                           padding:5px 16px;border-radius:8px;font-size:16px;">{hours[peak_key]} زيارة</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ---------- آخر الزيارات (بنفس أعمدة الريفرنس + التاريخ بعد العميل) ----------
    st.subheader("آخر الزيارات")
    recent = list(reversed(visits[-15:]))
    n = len(recent)

    status_txt = [wait_status(v[4]) for v in recent]
    status_col = [wait_color(v[4]) for v in recent]
    wait_fill  = [hex_tint(wait_color(v[4]), 0.18) for v in recent]

    dates = [split_dt(v[2])[0] for v in recent]
    ins   = [split_dt(v[2])[1] for v in recent]
    outs  = [split_dt(v[3])[1] for v in recent]

    dark = ["#171f2b"] * n
    light = ["#e6edf3"] * n

    # الترتيب من الشمال لليمين (زي الريفرنس بالظبط):
    # حالة الانتظار | وقت الانتظار | وقت المغادرة | وقت الوصول | التاريخ | معرف العميل | #
    tbl = go.Figure(go.Table(
        header=dict(
            values=["حالة الانتظار", "وقت الانتظار", "وقت المغادرة",
                    "وقت الوصول", "التاريخ", "معرف العميل", "#"],
            fill_color="#1c2634",
            font=dict(color="#9fb3c8", size=14),
            align="center", height=40),
        cells=dict(
            values=[
                status_txt,
                [fmt(v[4]) for v in recent],
                outs,
                ins,
                dates,
                [f"Customer #{v[1]}" for v in recent],
                [str(v[0]) for v in recent],
            ],
            fill_color=[
                dark,        # الحالة: خلفية غامقة والنقطة الملونة
                wait_fill,   # الانتظار: خلفية ملونة زي الختم
                dark, dark, dark, dark, dark,
            ],
            font=dict(color=[
                status_col,
                status_col,
                light, light, light, light, light,
            ], size=13),
            align="center", height=34),
    ))
    tbl.update_layout(height=max(300, 90 + 36 * n), margin=dict(t=10, b=10, l=10, r=10))
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
    with o1: card("🧾", "إجمالي الطلبات", len(orders), "#4da3ff")
    with o2: card("✅", "تم تسليمها", len(delivered), "#4ade80")
    with o3: card("⏳", "مستنية التسليم", len(pending_o), "#ffd166")
    with o4: card("⚡", "متوسط وقت التجهيز",
                  fmt(sum(preps)/len(preps)) if preps else "—",
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

        colT, colG = st.columns([1, 2])

        with colT:
            st.markdown("##### 👨‍🍳 أداء الباريستات")
            st.markdown(
                f"""
                <div style="background:#171f2b;padding:16px;border-radius:14px;
                            border-left:6px solid #4da3ff;margin-bottom:12px;text-align:center;">
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
            d_labels = [str(o[0]) for o in delivered]
            d_vals = [o[4] or 0 for o in delivered]
            avg_prep = sum(d_vals) / len(d_vals)
            d_colors = ["#4ade80" if w < avg_prep else "#ffd166" if w < avg_prep * 1.5 else "#ff5d5d"
                        for w in d_vals]
            d_hover = [fmt(v) for v in d_vals]
            d_fig = go.Figure(go.Bar(
                x=d_labels, y=d_vals, marker_color=d_colors,
                customdata=d_hover,
                hovertemplate="Order %{x}<br>تجهيز: %{customdata}<extra></extra>",
            ))

            d_fig.update_xaxes(type="category")
            d_fig.update_layout(barcornerradius=8)
            d_fig.add_hline(y=avg_prep, line_dash="dash", line_color="#4da3ff",
                            annotation_text=f"المتوسط: {fmt(avg_prep)}",
                            annotation_font_color="#4da3ff")
            d_fig.update_xaxes(title="الطلبات (بالترتيب)")
            d_fig.update_yaxes(title="الوقت (ثانية)")
            st.plotly_chart(style_fig(d_fig, 340), use_container_width=True)