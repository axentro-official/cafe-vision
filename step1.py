# أول برنامج - تجربة الكاميرا
import cv2

print("OpenCV شغال! النسخة:", cv2.__version__)
print("الكاميرا بتفتح... اضغط حرف Q عشان تقفل")

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        print("مفيش كاميرا!")
        break
    cv2.imshow("Cafe Vision - Step 1", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()