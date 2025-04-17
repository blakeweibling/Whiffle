import cv2
import time

# Try different camera indices (0, 1, etc.) and backends if needed
# Common backends: cv2.CAP_DSHOW (Windows), cv2.CAP_MSMF (Windows),
#                 cv2.CAP_V4L2 (Linux), cv2.CAP_AVFOUNDATION (macOS)
# If you don't specify a backend, OpenCV tries to pick one automatically.
# cap = cv2.VideoCapture(0)
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) # Explicitly try DirectShow on Windows

if not cap.isOpened():
    print("Error: Could not open video device.")
    exit()

print("Press 's' to open settings, 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Can't receive frame (stream end?). Exiting ...")
        break

    # Display the resulting frame
    cv2.imshow('Camera Feed', frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('s'):
        print("Attempting to open camera settings dialog...")
        # This is the call that tries to open the settings window
        # Note: We call get(), but we don't really use the return value.
        # The action happens as a side effect of the get() call for this specific property.
        cap.get(cv2.CAP_PROP_SETTINGS)
        print("Settings dialog call made (check if a window appeared).")
        # Add a small pause sometimes helps ensure the dialog interaction completes
        time.sleep(0.5)


    elif key == ord('q'):
        print("Quitting...")
        break

# When everything done, release the capture
cap.release()
cv2.destroyAllWindows()
print("Resources released.")