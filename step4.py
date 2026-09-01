# الخطوة 4 - عداد وقت الانتظار لكل شخص
import cv2
import time
from ultralytics import YOLO

model = YOLO("yolo11n.pt")

print("الكاميرا بتفتح... اضغط Q عشان تقفل")

cap = cv2.VideoCapture(0)

# دي "ذاكرة" بنحفظ فيها: رقم الشخص -> وقت أول ظهور له
wait_start = {}

# ألوان الحالات: أخضر / أصفر / أحمر
GREEN = (0, 200, 0)
YELLOW = (0, 220, 220)
RED = (0, 0, 230)

# حدود تغيير الحالة بالثواني (هتخليها قابلة للتعديل بعدين)
YELLOW_AFTER = 60
RED_AFTER = 120

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model.track(frame, persist=True, verbose=False, classes=[0])
    annotated = frame.copy()

    if results[0].boxes.id is not None:
        ids = results[0].boxes.id.int().tolist()
        boxes = results[0].boxes.xyxy.tolist()

        for tid, box in zip(ids, boxes):
            x1, y1, x2, y2 = map(int, box)

            # أول مرة نشوف الشخص ده؟ سجل وقت بداية انتظاره
            if tid not in wait_start:
                wait_start[tid] = time.time()

            elapsed = time.time() - wait_start[tid]

            # نحدد الحالة واللون
            if elapsed < YELLOW_AFTER:
                color = GREEN
                status = "OK"
            elif elapsed < RED_AFTER:
                color = YELLOW
                status = "WAITING"
            else:
                color = RED
                status = "ALERT"

            # نص الوقت بشكل دقايق:ثواني
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)

            # مربع حوالين الشخص
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # الكتابة فوق الراس
            label = f"#{tid} {minutes:02d}:{seconds:02d} {status}"
            cv2.putText(annotated, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        cv2.putText(annotated, f"Customers: {len(ids)}", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
    else:
        # مفيش حد في الكادر
        cv2.putText(annotated, "Customers: 0", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

    cv2.imshow("Cafe Vision - Step 4 (Waiting Timer)", annotated)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()