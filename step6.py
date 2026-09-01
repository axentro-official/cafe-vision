# الخطوة 6 (نسخة 3.1) - إشارة تسليم (كوباية/وقوف) + تأكيد نهائي عند خروج العميل
import cv2
import time
import json
import os
import sqlite3
from datetime import datetime
from ultralytics import YOLO

model = YOLO("yolo11n.pt")

ZONES_FILE = "zones.json"

# ================= إعدادات قابلة للتعديل =================
GREEN_UPTO         = 60
YELLOW_UPTO        = 90
MIN_CONF           = 0.50
CUP_CONF           = 0.35    # ثقة كشف الكوباية
MIN_AREA_PCT       = 0.015
MIN_FRAMES         = 8
GONE_AFTER         = 15.0    # غاب كام ثانية = خرج رسمي (لحظة التأكيد)
BARISTA_MIN_TIME   = 10.0
BARISTA_ZONE_RATIO = 0.6
DWELL_SECONDS      = 4.0     # إشارة احتياطية: وقوف مع الباريستا
CUP_NEAR_PCT       = 0.40    # قرب الكوباية من العميل (نسبة من حجم المربع)

GREEN  = (0, 200, 0)
YELLOW = (0, 220, 220)
RED    = (0, 0, 230)
BLUE   = (255, 160, 0)
ORANGE = (0, 140, 255)

# ================= قاعدة البيانات =================
conn = sqlite3.connect("cafe.db", timeout=10)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_no INTEGER,
    entry_time TEXT,
    exit_time TEXT,
    wait_seconds REAL
)
""")
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

row = cursor.execute("SELECT MAX(customer_no) FROM visits").fetchone()
next_customer = (row[0] or 0) + 1

# ================= الذاكرة =================
wait_start, last_seen, seen_frames, customer_no = {}, {}, {}, {}
zone_time, total_time = {}, {}
dwell = {}
pending = {}          # تسليم مشتبه (لسه مش متأكد)
pending_barista = {}  # الباريستا اللي كان موجود لحظة الإشارة
barista_no, orders = {}, {}
next_barista = 1

# ================= دوال =================
def save_visit(cno, entry, exit_t):
    duration = exit_t - entry
    if duration < 3:
        return False
    cursor.execute(
        "INSERT INTO visits (customer_no, entry_time, exit_time, wait_seconds) VALUES (?, ?, ?, ?)",
        (cno,
         datetime.fromtimestamp(entry).strftime("%Y-%m-%d %I:%M:%S %p"),
         datetime.fromtimestamp(exit_t).strftime("%Y-%m-%d %I:%M:%S %p"),
         duration))
    conn.commit()
    return True

def confirm_delivery(cno, b_tid):
    """التأكيد النهائي - بيحصل فقط لما العميل يخرج من الكادر"""
    bno = barista_no.get(b_tid) if b_tid is not None else None
    if b_tid is not None:
        orders[b_tid] = orders.get(b_tid, 0) + 1
    row = cursor.execute(
        "SELECT id, created_epoch FROM orders WHERE status='pending' ORDER BY id LIMIT 1").fetchone()
    if row:
        oid, created_epoch = row
        cursor.execute(
            "UPDATE orders SET status='delivered', delivered_at=?, delivered_epoch=?, "
            "prep_seconds=?, customer_no=?, barista_label=? WHERE id=?",
            (datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %I:%M:%S %p"),
             time.time(), time.time() - created_epoch,
             cno, f"Barista #{bno}" if bno else "غير معروف", oid))
        conn.commit()
        cnt = f" — عداد الباريستا بقى: {orders[b_tid]}" if b_tid is not None else ""
        print(f"✅ تأكيد نهائي: Order #{oid} → Customer #{cno} بواسطة Barista #{bno}{cnt}")
    else:
        print(f"✅ تأكيد نهائي: تسليم بيد موثق → Customer #{cno} بواسطة Barista #{bno}")

# ================= الكاميرا + منطقة الباريستا =================
cap = cv2.VideoCapture(0)
for _ in range(10):
    ret, frame = cap.read()
if not ret:
    print("مفيش كاميرا!")
    exit()

cv2.namedWindow("Cafe Vision - Step 6", cv2.WINDOW_AUTOSIZE)

if os.path.exists(ZONES_FILE):
    zone = json.load(open(ZONES_FILE))["barista"]
    print(f"المنطقة المحفوظة: {zone} (عشان ترسمها من جديد: امسح zones.json)")
else:
    print(">>> ارسم مستطيل منطقة الباريستا بالماوس ثم اضغط ENTER <<<")
    x, y, w, h = cv2.selectROI("Draw Barista Zone", frame, False, False)
    cv2.destroyAllWindows()
    if w == 0 or h == 0:
        zone = None
        print("مفيش منطقة - الكل هيتعامل كعملاء")
    else:
        zone = [int(x), int(y), int(w), int(h)]
        json.dump({"barista": zone}, open(ZONES_FILE, "w"))
        print(f"اتحفظت المنطقة: {zone}")

def in_zone(cx, cy):
    if zone is None:
        return False
    zx, zy, zw, zh = zone
    return zx <= cx <= zx + zw and zy <= cy <= zy + zh

last_t = time.time()
print("الكاميرا بتشتغل... اضغط Q للخروج")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # الكاميرا مغطاة؟ جمّد كل حاجة
    if cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean() < 20:
        cv2.putText(frame, "Camera Covered - Paused", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        cv2.imshow("Cafe Vision - Step 6", cv2.resize(frame, (1280, 720)))
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        last_t = time.time()
        continue

    now = time.time()
    dt = now - last_t
    last_t = now

    # نكشف الأشخاص + الكوبايات (41 = cup في YOLO)
    results = model.track(frame, persist=True, verbose=False,
                          classes=[0, 41], tracker="tracker.yaml", conf=0.30)
    annotated = frame.copy()
    fh, fw = frame.shape[:2]
    min_area = MIN_AREA_PCT * fh * fw

    if zone is not None:
        zx, zy, zw, zh = zone
        cv2.rectangle(annotated, (zx, zy), (zx + zw, zy + zh), BLUE, 2)
        cv2.putText(annotated, "Barista Zone", (zx, zy - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, BLUE, 2)

    # ---------- افصل الأشخاص عن الكوبايات ----------
    person_dets, cup_boxes = [], []
    boxes_all = results[0].boxes.xyxy.tolist() if results[0].boxes is not None and len(results[0].boxes) else []
    if boxes_all:
        clss = results[0].boxes.cls.int().tolist()
        confs = results[0].boxes.conf.tolist()
        ids_raw = results[0].boxes.id
        ids_all = ids_raw.int().tolist() if ids_raw is not None else [None] * len(boxes_all)
        for b, c, cf, i in zip(boxes_all, clss, confs, ids_all):
            name = model.names[c]
            if name == "person" and cf >= MIN_CONF and (b[2]-b[0])*(b[3]-b[1]) >= min_area and i is not None:
                person_dets.append((i, b))
            elif name == "cup" and cf >= CUP_CONF:
                cup_boxes.append(b)

    # ارسم الكوبايات
    for b in cup_boxes:
        x1, y1, x2, y2 = map(int, b)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), ORANGE, 2)
        cv2.putText(annotated, "cup", (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, ORANGE, 2)

    confirmed = []
    current_baristas = []

    for tid, box in person_dets:
        x1, y1, x2, y2 = map(int, box)
        confirmed.append(tid)
        seen_frames[tid] = seen_frames.get(tid, 0) + 1
        if tid not in wait_start:
            wait_start[tid] = now
        last_seen[tid] = now

        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        inside = in_zone(cx, cy)
        total_time[tid] = total_time.get(tid, 0) + dt
        if inside:
            zone_time[tid] = zone_time.get(tid, 0) + dt

        ratio = (zone_time.get(tid, 0) / total_time[tid]) if total_time.get(tid) else 0
        is_barista = (tid in barista_no or
                      (total_time[tid] >= BARISTA_MIN_TIME and ratio >= BARISTA_ZONE_RATIO))

        if is_barista:
            if tid not in barista_no:
                barista_no[tid] = next_barista
                next_barista += 1
                print(f"👨‍🍳 باريستا انضم: Barista #{barista_no[tid]}")
            current_baristas.append(tid)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), BLUE, 2)
            cv2.putText(annotated, f"Barista #{barista_no[tid]} | Orders: {orders.get(tid, 0)}",
                        (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, BLUE, 2)
            continue

        if tid not in customer_no and seen_frames[tid] >= MIN_FRAMES and ratio < 0.5:
            customer_no[tid] = next_customer
            next_customer += 1
            print(f"عميل جديد: Customer #{customer_no[tid]}")

        if tid not in customer_no:
            continue

        cno = customer_no[tid]
        elapsed = now - wait_start[tid]
        if elapsed < GREEN_UPTO:
            color, status = GREEN, "OK"
        elif elapsed < YELLOW_UPTO:
            color, status = YELLOW, "WAITING"
        else:
            color, status = RED, "ALERT"
        m, s = int(elapsed // 60), int(elapsed % 60)

        # ---------- إشارات التسليم (مش تأكيد!) ----------
        holding = False
        for cb in cup_boxes:
            ccx, ccy = (cb[0] + cb[2]) / 2, (cb[1] + cb[3]) / 2
            ex1 = x1 - (x2 - x1) * CUP_NEAR_PCT
            ex2 = x2 + (x2 - x1) * CUP_NEAR_PCT
            ey1 = y1 - (y2 - y1) * CUP_NEAR_PCT
            ey2 = y2 + (y2 - y1) * CUP_NEAR_PCT
            if ex1 <= ccx <= ex2 and ey1 <= ccy <= ey2:
                holding = True
                break

        best_b = max(current_baristas, key=lambda b: zone_time.get(b, 0)) if current_baristas else None

        if not pending.get(tid):
            # إشارة 1: ماسك كوباية + (جوه المنطقة أو الباريستا موجود)
            if holding and (inside or best_b is not None):
                pending[tid] = True
                pending_barista[tid] = best_b
                print(f"🥤 إشارة تسليم: Customer #{cno} ماسك كوباية — التأكيد عند خروجه")
            # إشارة 2 (احتياطية): وقوف مع الباريستا لو الكوباية مش باينة
            elif inside and best_b is not None:
                dwell[tid] = dwell.get(tid, 0) + dt
                if dwell[tid] >= DWELL_SECONDS:
                    pending[tid] = True
                    pending_barista[tid] = best_b
                    print(f"⏳ إشارة تسليم: Customer #{cno} وقف مع الباريستا — التأكيد عند خروجه")

        label = f"Customer #{cno} {m:02d}:{s:02d} {status}"
        if pending.get(tid):
            label += " | SERVING"
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(annotated, label, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    active = [t for t in confirmed if t in customer_no]
    cv2.putText(annotated, f"Customers: {len(active)}", (fw - 260, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

    # ---------- الخروج من الكادر = لحظة التأكيد ----------
    for tid in list(wait_start.keys()):
        if tid not in confirmed and now - last_seen.get(tid, now) > GONE_AFTER:
            cno = customer_no.pop(tid, None)
            entry = wait_start.pop(tid)
            ls = last_seen.pop(tid, None)
            if cno is not None and tid not in barista_no:
                if save_visit(cno, entry, ls):
                    print(f"خرج من الكادر: Customer #{cno}")
                if pending.pop(tid, None):
                    confirm_delivery(cno, pending_barista.pop(tid, None))
            else:
                pending.pop(tid, None)
                pending_barista.pop(tid, None)
            seen_frames.pop(tid, None)
            zone_time.pop(tid, None)
            total_time.pop(tid, None)
            dwell.pop(tid, None)

    cv2.imshow("Cafe Vision - Step 6", cv2.resize(annotated, (1280, 720)))
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# ---------- إقفال البرنامج: نأكد اللي لسه pending ----------
now = time.time()
for tid in list(wait_start.keys()):
    cno = customer_no.get(tid)
    if cno is not None and tid not in barista_no:
        save_visit(cno, wait_start[tid], last_seen[tid])
        if pending.get(tid):
            confirm_delivery(cno, pending_barista.get(tid))

cap.release()
cv2.destroyAllWindows()

print("\n===== سجل الزيارات =====")
cursor.execute("SELECT * FROM visits ORDER BY id")
for r in cursor.fetchall():
    print(f"زيارة #{r[0]}: Customer #{r[1]} | {r[2]} -> {r[3]} | انتظر {r[4]:.0f} ثانية")

print("\n===== سجل الطلبات المؤكدة =====")
cursor.execute("SELECT id, customer_no, barista_label, prep_seconds "
               "FROM orders WHERE status='delivered' ORDER BY id")
for r in cursor.fetchall():
    print(f"Order #{r[0]} → Customer #{r[1]} | بواسطة {r[2]} | تجهيز {r[3]:.0f} ثانية")
conn.close()