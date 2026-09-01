# الخطوة 3 - التتبع: كل شخص له رقم ثابت
import cv2
from ultralytics import YOLO

model = YOLO("yolo11n.pt")

print("الكاميرا بتفتح... اضغط Q عشان تقفل")

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model.track(frame, persist=True, verbose=False, classes=[0])

    annotated = results[0].plot()

    if results[0].boxes.id is not None:
        ids = results[0].boxes.id.int().tolist()
        cv2.putText(annotated, f"Tracked: {len(ids)}", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

    cv2.imshow("Cafe Vision - Step 3 (Tracking)", annotated)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()