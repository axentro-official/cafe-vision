# الخطوة 2 - العين الذكية: كشف الأشخاص
import cv2
from ultralytics import YOLO

print("بنحمّل نموذج الذكاء الاصطناعي... (أول مرة بس)")
model = YOLO("yolo11n.pt")

print("الكاميرا بتفتح... اضغط Q عشان تقفل")

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        print("مفيش صورة!")
        break

    results = model(frame, verbose=False)

    annotated = results[0].plot()

    persons = 0
    for box in results[0].boxes:
        cls = int(box.cls[0])
        if model.names[cls] == "person":
            persons += 1

    cv2.putText(annotated, f"Persons: {persons}", (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

    cv2.imshow("Cafe Vision - Step 2 (AI)", annotated)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()