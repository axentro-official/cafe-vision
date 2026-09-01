# الخطوة 5 (نسخة 3) - ترقيم عملاء حقيقي + فلترة الوهميات
import cv2
import time
import sqlite3
from datetime import datetime
from ultralytics import YOLO

model = YOLO("yolo11n.pt")

# ---------- قاعدة البيانات ----------
conn = sqlite3.connect("cafe.db")
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
conn.commit()

# الترقيم بيكمل من آخر عميل حتى بعد إقفال البرنامج
row = cursor.execute("SELECT MAX(customer_no) FROM visits").fetchone()
next_customer = (row[0] or 0) + 1

def save_visit(cno, entry, exit_t):
    duration = exit_t - entry
    if duration < 2:
        return False
    cursor.execute(
        "INSERT INTO visits (customer_no, entry_time, exit_time, wait_seconds) VALUES (?, ?, ?, ?)",
        (cno,
         datetime.fromtimestamp(entry).strftime("%Y-%m-%d %I:%M:%S %p"),
         datetime.fromtimestamp(exit_t).strftime("%Y-%m-%d %I:%M:%S %p"),
         duration))
    conn.commit()
    return True

# ---------- إعدادات الفلترة ----------
MIN_CONF = 0.50        # لو التيشرت لسه بيتسجل: ارفعها لـ 0.60
MIN_AREA_PCT = 0.015   # تجاهل المربعات أصغر من 1.5% من الشاشة
MIN_FRAMES = 8         # لازم يظهر ~ثانية قبل ما نطلعله رقم عميل
GONE_AFTER = 15.0

# ---------- الذاكرة ----------
wait_start = {}     # أول لحظة اتشاف فيها
last_seen = {}      # آخر لحظة اتشاف فيها
seen_frames = {}    # عدد الفريمات اللي ظهر فيها
customer_no = {}    # الرقم الرسمي اللي إحنا ولدناه

GREEN = (0, 200, 0)
YELLOW = (0, 220, 220)
RED = (0, 0, 230)
YELLOW_AFTER = 60
RED_AFTER = 120

print("الكاميرا بتفتح... اضغط Q عشان تقفل")
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # الكاميرا مغطاة؟ جمّد كل حاجة
    brightness = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean()
    if brightness < 20:
        cv2.putText(frame, "Camera Covered - Paused", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        cv2.imshow("Cafe Vision - Step 5 (Database)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        continue

    results = model.track(frame, persist=True, verbose=False,
                          classes=[0], tracker="tracker.yaml", conf=MIN_CONF)
    annotated = frame.copy()
    now = time.time()
    fh, fw = frame.shape[:2]
    min_area = MIN_AREA_PCT * fh * fw

    confirmed = []
    if results[0].boxes.id is not None:
        ids = results[0].boxes.id.int().tolist()
        boxes = results[0].boxes.xyxy.tolist()
        confs = results[0].boxes.conf.tolist()

        for tid, box, conf in zip(ids, boxes, confs):
            x1, y1, x2, y2 = map(int, box)
            if conf < MIN_CONF or (x2 - x1) * (y2 - y1) < min_area:
                continue  # وهمية أو صغيرة جداً

            confirmed.append(tid)
            seen_frames[tid] = seen_frames.get(tid, 0) + 1

            if tid not in wait_start:
                wait_start[tid] = now

            # بعد ثانية استقرار -> يستاهل رقم عميل رسمي
            if tid not in customer_no and seen_frames[tid] >= MIN_FRAMES:
                customer_no[tid] = next_customer
                next_customer += 1
                print(f"عميل جديد: Customer #{customer_no[tid]}")

            last_seen[tid] = now

            if tid in customer_no:
                elapsed = now - wait_start[tid]
                if elapsed < YELLOW_AFTER:
                    color, status = GREEN, "OK"
                elif elapsed < RED_AFTER:
                    color, status = YELLOW, "WAITING"
                else:
                    color, status = RED, "ALERT"
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                cv2.putText(annotated,
                            f"Customer #{customer_no[tid]} {minutes:02d}:{seconds:02d} {status}",
                            (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        active = [t for t in confirmed if t in customer_no]
        cv2.putText(annotated, f"Customers: {len(active)}", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
    else:
        cv2.putText(annotated, "Customers: 0", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

    # اللي غاب كفاية -> نسجل خروجه
    for tid in list(wait_start.keys()):
        if tid not in confirmed and now - last_seen.get(tid, now) > GONE_AFTER:
            cno = customer_no.pop(tid, None)
            if cno is not None:
                if save_visit(cno, wait_start.pop(tid), last_seen.pop(tid)):
                    print(f"خرج واتسجل: Customer #{cno}")
            else:
                wait_start.pop(tid)      # عمره ما اتأكد -> وهمية، نرميها
            last_seen.pop(tid, None)
            seen_frames.pop(tid, None)

    cv2.imshow("Cafe Vision - Step 5 (Database)", annotated)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# حفظ اللي لسه موجودين
now = time.time()
for tid in list(wait_start.keys()):
    if tid in customer_no:
        save_visit(customer_no[tid], wait_start[tid], last_seen[tid])

cap.release()
cv2.destroyAllWindows()

print("\n===== سجل الزيارات =====")
cursor.execute("SELECT * FROM visits ORDER BY id")
for r in cursor.fetchall():
    print(f"زيارة #{r[0]}: Customer #{r[1]} | {r[2]} -> {r[3]} | انتظر {r[4]:.0f} ثانية")

conn.close()