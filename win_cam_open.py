import cv2

def test_camera(index):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)  # CAP_DSHOW works well on Windows
    if not cap.isOpened():
        print(f"❌ Cannot open camera index {index}")
        return
    
    print(f"✅ Opened camera {index}. Press 'q' to quit.")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Failed to grab frame")
            break
        cv2.imshow(f"Camera {index}", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

# Try with different indexes until your USB webcam shows up
test_camera(0)   # start with 1
