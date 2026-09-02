# الخطوة 6 (نسخة 4.3 النهائية) - شكل احترافي + تعليم الباريستا بالبصمة + رقم ثابت للبصمة
import cv2
import numpy as np
import time
import json
import os
import sqlite3
from datetime import datetime
from ultralytics import YOLO

# ================= إعدادات قابلة للتعديل =================
MODEL_NAME = "yolo11s.pt"   # لو جهازك بطيء: رجّعها "yolo11n.pt"
                            # في الإنتاج الحقيقي (GPU/Edge): yolo11m.pt أو yolo11l.pt

# مصدر الكاميرا:
#   0                = كاميرا اللابتوب
#   "rtsp://..."     = كاميرا IP حقيقية (أي كاميرا مراقبة ONVIF حديثة)
# مثال: "rtsp://admin:password@192.168.1.10:554/stream1"
CAMERA_SOURCE = 0

ZONES_FILE = "zones.json"

GREEN_UPTO         = 60      # أخضر لحد 60 ثانية
YELLOW_UPTO        = 90      # أصفر من 60 لـ 90 | بعدها أحمر
MIN_CONF           = 0.50
CUP_CONF           = 0.35
MIN_AREA_PCT       = 0.015
MIN_FRAMES         = 8
GONE_AFTER         = 15.0    # غاب كام ثانية = خرج رسمي (لحظة التأكيد)
BARISTA_MIN_TIME   = 10.0
BARISTA_ZONE_RATIO = 0.6
DWELL_SECONDS      = 4.0
CUP_NEAR_PCT       = 0.40
ZONE_FILL_ALPHA    = 0.18    # شفافية تعبئة المنطقة

# ---------- تعليم الباريستا (بصمة الملابس) ----------
ENROLL_KEY         = 'e'     # اضغط E وإنت قاعد جوه الكادر عشان تسجل نفسك
APPEAR_THRESHOLD   = 0.45    # لو التعرف غلط: ارفعها 0.55 | لو مش بيجيب: نقّلها 0.40
HIST_BINS          = 16

GREEN  = (0, 200, 0)
YELLOW = (0, 220, 220)
RED    = (0, 0, 230)
BLUE   = (255, 160, 0)
ORANGE = (0, 140, 255)
DARK   = (30, 30, 30)
WHITE  = (255, 255, 255)

model = YOLO(MODEL_NAME)

# ================= دوال الرسم الاحترافية =================
def text_color_for(bgr):
    """نص أسود على الخلفيات الفاتحة، أبيض على الغامقة"""
    b, g, r = bgr
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return (0, 0, 0) if lum > 150 else (255, 255, 255)

def draw_badge(img, text, x, y, bg_color, font_scale=0.55):
    """بادج معبأ بلون - النقطة (x,y) هي أسفل-شمال البادج"""
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2)
    pad = 5
    bx1 = x
    by1 = max(0, y - th - baseline - 2 * pad)
    bx2 = x + tw + 2 * pad
    by2 = by1 + th + baseline + 2 * pad
    cv2.rectangle(img, (bx1, by1), (bx2, by2), bg_color, -1)
    cv2.putText(img, text, (bx1 + pad, by2 - baseline - pad),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color_for(bg_color), 2)
    return (bx2, by2)

def box_center(box):
    return (int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2))

# ---------- بصمة الملابس (numpy مباشرة - متوافقة مع OpenCV 5) ----------
def extract_appearance(frame, box):
    """بصمة لونية للجذع - بترجع None لو مفيش مقطع صالح"""
    try:
        fh, fw = frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in box]
        x1, x2 = max(0, x1), min(fw, x2)
        y1, y2 = max(0, y1), min(fh, y2)
        w, h = x2 - x1, y2 - y1
        if w < 10 or h < 10:
            print(f"   [debug] المربع صغير جداً: {w}x{h} بكسل")
            return None
        top = max(0, y1 + int(h * 0.10))
        bot = max(0, y1 + int(h * 0.60))
        crop = frame[top:bot, x1:x2]
        if crop is None or crop.size == 0 or crop.shape[0] < 5 or crop.shape[1] < 5:
            print(f"   [debug] مقطع فاضي: top={top} bot={bot} x1={x1} x2={x2}")
            return None
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hue = hsv[:, :, 0].ravel().astype(np.float32)
        val = hsv[:, :, 2].ravel().astype(np.float32)
        hist_h, _ = np.histogram(hue, bins=HIST_BINS, range=(0, 180))
        hist_v, _ = np.histogram(val, bins=HIST_BINS, range=(0, 256))
        hist = np.concatenate([hist_h, hist_v]).astype(np.float32)
        total = hist.sum()
        if total <= 0:
            print("   [debug] البصمة فاضية (الصورة سودا؟)")
            return None
        return hist / total
    except Exception as e:
        print(f"   [debug] خطأ حقيقي في البصمة: {e}")
        return None

def appearance_match(h1, h2):
    """نسبة التشابه (correlation) — numpy مباشرة، متوافقة مع أي نسخة"""
    try:
        h1 = h1.flatten().astype(np.float32)
        h2 = h2.flatten().astype(np.float32)
        h1m = h1 - h1.mean()
        h2m = h2 - h2.mean()
        denom = float(np.sqrt((h1m ** 2).sum() * (h2m ** 2).sum()))
        if denom < 1e-6:
            return 0.0
        return float((h1m * h2m).sum() / denom)
    except Exception:
        return 0.0

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
pending = {}
pending_barista = {}
barista_no, orders = {}, {}
next_barista = 1
enrolled_signatures = []   # بصمات الباريستات المسجلين (زرار E)
announced_baristas = set() # أرقام الباريستات اللي أعلنّا عنها الجلسة دي

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

# ================= الكاميرا =================
cap = cv2.VideoCapture(CAMERA_SOURCE)
for _ in range(10):
    ret, frame = cap.read()
if not ret:
    print("مفيش كاميرا!")
    exit()

cv2.namedWindow("Cafe Vision", cv2.WINDOW_AUTOSIZE)

# ================= تحديد منطقة الباريستا (مضلع 4 نقاط) =================
def pick_zone_poly(src_frame):
    """المستخدم بينقر 4 نقاط حول الكاونتر | ENTER=حفظ R=إعادة ESC=تخطي"""
    pts = []
    win = "Click 4 corners around the counter | ENTER=Save  R=Reset  ESC=Skip"
    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(param) < 4:
            param.append((x, y))
    cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(win, on_mouse, pts)
    while True:
        img = cv2.resize(src_frame, (960, 720))
        scale_x, scale_y = src_frame.shape[1] / 960, src_frame.shape[0] / 720
        for p in pts:
            cv2.circle(img, p, 7, BLUE, -1)
        if len(pts) >= 2:
            cv2.polylines(img, [np.array(pts, np.int32)], len(pts) == 4, BLUE, 2)
        msg = "Click corner " + str(len(pts) + 1) + " of 4"
        cv2.putText(img, msg, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, YELLOW, 2)
        cv2.imshow(win, img)
        k = cv2.waitKey(1) & 0xFF
        if k in (13, 10) and len(pts) == 4:
            break
        elif k == ord('r'):
            pts.clear()
        elif k == 27:
            pts = []
            break
    cv2.destroyAllWindows()
    if len(pts) == 4:
        return [(int(x * scale_x), int(y * scale_y)) for x, y in pts]
    return None

if os.path.exists(ZONES_FILE):
    data = json.load(open(ZONES_FILE))
    if "barista_poly" in data:
        zone_poly = [tuple(p) for p in data["barista_poly"]]
    else:
        # توافق مع الملف القديم (مستطيل) — نحوله لمضلع
        x, y, w, h = data["barista"]
        zone_poly = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    # تحميل بصمات الباريستا المحفوظة
    if "barista_signatures" in data:
        for flat in data["barista_signatures"]:
            enrolled_signatures.append(np.array(flat, np.float32))
        next_barista = len(enrolled_signatures) + 1
    print(f"المنطقة المحفوظة: {zone_poly}")
    print(f"بصمات باريستا محفوظة: {len(enrolled_signatures)} (لإعادة الكل من الأول: امسح zones.json)")
else:
    print(">>> انقر 4 زوايا حول منطقة الكاونتر ثم ENTER <<<")
    zone_poly = pick_zone_poly(frame)
    if zone_poly:
        json.dump({"barista_poly": zone_poly}, open(ZONES_FILE, "w"))
        print(f"اتحفظت المنطقة: {zone_poly}")
    else:
        print("مفيش منطقة - الكل هيتعامل كعملاء")

def save_signatures():
    """حفظ بصمات الباريستا في zones.json (تعيش بعد إقفال البرنامج)"""
    data = {}
    if os.path.exists(ZONES_FILE):
        data = json.load(open(ZONES_FILE))
    data["barista_signatures"] = [s.flatten().tolist() for s in enrolled_signatures]
    json.dump(data, open(ZONES_FILE, "w"))

zone_contour = np.array(zone_poly, np.int32).reshape(-1, 1, 2) if zone_poly else None

def in_zone(cx, cy):
    if zone_contour is None:
        return False
    return cv2.pointPolygonTest(zone_contour, (float(cx), float(cy)), False) >= 0

last_t = time.time()
fps_smooth = 0.0
print("الكاميرا بتشتغل... اضغط Q للخروج | اضغط E عشان تسجل الباريستا اللي قدام الكاميرا")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # الكاميرا مغطاة؟ جمّد كل حاجة
    if cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean() < 20:
        cover = cv2.resize(frame, (1280, 720))
        draw_badge(cover, "Camera Covered - Paused", 20, 60, RED, 0.9)
        cv2.imshow("Cafe Vision", cover)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        last_t = time.time()
        continue

    now = time.time()
    dt = now - last_t
    last_t = now
    if dt > 0:
        fps_smooth = 0.9 * fps_smooth + 0.1 * (1.0 / dt)

    results = model.track(frame, persist=True, verbose=False,
                          classes=[0, 41], tracker="tracker.yaml", conf=0.30)
    annotated = frame.copy()
    fh, fw = frame.shape[:2]
    min_area = MIN_AREA_PCT * fh * fw

    # ---------- المنطقة: مضلع شفاف + بادج ----------
    if zone_contour is not None:
        overlay = annotated.copy()
        cv2.fillPoly(overlay, [zone_contour], BLUE)
        cv2.addWeighted(overlay, ZONE_FILL_ALPHA, annotated, 1 - ZONE_FILL_ALPHA, 0, annotated)
        cv2.polylines(annotated, [zone_contour], True, BLUE, 2)
        zx, zy = int(zone_poly[0][0]), int(zone_poly[0][1])
        draw_badge(annotated, "Barista Zone", zx, zy - 8, BLUE)

    # ---------- فصل الأشخاص عن الكوبايات ----------
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

    for b in cup_boxes:
        x1, y1, x2, y2 = map(int, b)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), ORANGE, 2)
        draw_badge(annotated, "cup", x1, y1 - 6, ORANGE, 0.45)

    confirmed = []
    current_baristas = []
    person_boxes = {}

    for tid, box in person_dets:
        x1, y1, x2, y2 = map(int, box)
        confirmed.append(tid)
        person_boxes[tid] = box
        seen_frames[tid] = seen_frames.get(tid, 0) + 1
        if tid not in wait_start:
            wait_start[tid] = now
        last_seen[tid] = now

        cx, cy = box_center(box)
        inside = in_zone(cx, cy)
        total_time[tid] = total_time.get(tid, 0) + dt
        if inside:
            zone_time[tid] = zone_time.get(tid, 0) + dt

        ratio = (zone_time.get(tid, 0) / total_time[tid]) if total_time.get(tid) else 0

        # ---------- ترتيب التعرف: بصمة الملابس أولاً، ثم المنطقة، وأخيراً عميل ----------
        enrolled_match = False
        matched_sig_idx = -1
        is_barista = tid in barista_no

        if not is_barista and enrolled_signatures:
            sig = extract_appearance(frame, box)
            if sig is not None:
                sims = [appearance_match(sig, es) for es in enrolled_signatures]
                best_idx = int(np.argmax(sims))
                if sims[best_idx] >= APPEAR_THRESHOLD:
                    enrolled_match = True
                    matched_sig_idx = best_idx
                    is_barista = True

        if not is_barista and total_time[tid] >= BARISTA_MIN_TIME and ratio >= BARISTA_ZONE_RATIO:
            is_barista = True

        if is_barista:
            if tid not in barista_no:
                if enrolled_match:
                    # رقم ثابت مرتبط بالبصمة: البصمة الأولى = Barista #1 دايماً
                    barista_no[tid] = matched_sig_idx + 1
                else:
                    barista_no[tid] = next_barista
                    next_barista += 1
            bno = barista_no[tid]
            if bno not in announced_baristas:
                announced_baristas.add(bno)
                how = "بالبصمة (ملابسه)" if enrolled_match else "بمنطقة العمل"
                print(f"👨‍🍳 باريستا انضم: Barista #{bno} ({how})")
            # ننضف أي أثر إنه اتلخبط عميل قبل كده
            customer_no.pop(tid, None)
            wait_start.pop(tid, None)
            dwell.pop(tid, None)
            pending.pop(tid, None)
            pending_barista.pop(tid, None)
            current_baristas.append(tid)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), BLUE, 2)
            draw_badge(annotated, f"Barista #{bno} | Orders: {orders.get(tid, 0)}",
                       x1, y1 - 4, BLUE)
            continue

        # مش باريستا -> نكمل كعميل
        if tid not in customer_no and seen_frames[tid] >= MIN_FRAMES:
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

        # ---------- إشارات التسليم ----------
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
            if holding and (inside or best_b is not None):
                pending[tid] = True
                pending_barista[tid] = best_b
                print(f"🥤 إشارة تسليم: Customer #{cno} ماسك كوباية — التأكيد عند خروجه")
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
        draw_badge(annotated, label, x1, y1 - 4, color)

    # ---------- خط توصيل التسليم: العميل ↔ الباريستا ----------
    for tid in list(pending.keys()):
        b_tid = pending_barista.get(tid)
        if tid in person_boxes and b_tid in person_boxes:
            c_c = box_center(person_boxes[tid])
            b_c = box_center(person_boxes[b_tid])
            cv2.line(annotated, c_c, b_c, WHITE, 2, cv2.LINE_AA)
            cv2.circle(annotated, c_c, 5, WHITE, -1)
            cv2.circle(annotated, b_c, 5, WHITE, -1)
            mid = ((c_c[0] + b_c[0]) // 2, (c_c[1] + b_c[1]) // 2 - 12)
            draw_badge(annotated, "SERVING", mid[0], mid[1], DARK, 0.45)

    # ---------- العدادات العلوية ----------
    active = [t for t in confirmed if t in customer_no]
    dark_cover = annotated.copy()
    cv2.rectangle(dark_cover, (14, 14), (220, 56), DARK, -1)
    cv2.addWeighted(dark_cover, 0.55, annotated, 0.45, 0, annotated)
    cv2.putText(annotated, f"Customers: {len(active)}", (26, 44),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, GREEN, 2)
    fps_txt = f"FPS: {fps_smooth:.0f} | {MODEL_NAME}"
    (tw, _), _ = cv2.getTextSize(fps_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
    cv2.rectangle(annotated, (fw - tw - 40, 14), (fw - 14, 48), DARK, -1)
    cv2.putText(annotated, fps_txt, (fw - tw - 26, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 2)

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

    cv2.imshow("Cafe Vision", cv2.resize(annotated, (1280, 720)))
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord(ENROLL_KEY):
        # 🎓 تسجيل الباريستا: أول شخص موجود في الكادر هو اللي بيتعلم
        if not confirmed:
            print("❌ مفيش حد في الكادر! قف جوه الكادر الأول وبعدين اضغط E")
        else:
            cand = max(confirmed, key=lambda t: seen_frames.get(t, 0))
            cand_box = person_boxes.get(cand)
            sig = extract_appearance(frame, cand_box) if cand_box is not None else None
            if sig is None:
                print("⚠️ الشخص قريب أوي من حافة الكادر — قرّب من النص واضغط E تاني")
            else:
                enrolled_signatures.append(sig)
                save_signatures()
                # مسح أي أثر إنه كان عميل
                customer_no.pop(cand, None)
                wait_start.pop(cand, None)
                dwell.pop(cand, None)
                pending.pop(cand, None)
                pending_barista.pop(cand, None)
                # رقم ثابت: البصمة الجديدة = ترتيبها في القائمة
                new_bno = len(enrolled_signatures)
                barista_no[cand] = new_bno
                announced_baristas.add(new_bno)
                next_barista = max(next_barista, new_bno + 1)
                print(f"🎓 باريستا اتعلم! ده دلوقتي Barista #{new_bno} "
                      f"({len(enrolled_signatures)} بصمة محفوظة) — النظام هيعرف عليه دايماً بهذا الرقم")

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