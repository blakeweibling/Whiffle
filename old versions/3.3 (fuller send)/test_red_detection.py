import cv2
import numpy as np

def test_webcam_indices():
    for index in range(5):  # Test indices 0 through 4
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            print(f"Webcam found at index {index}")
            return cap, index
        cap.release()
    print("No webcam found on any index.")
    return None, None

# Open the first available webcam
cap, webcam_index = test_webcam_indices()
if cap is None:
    print("Error: Could not open any webcam. Exiting.")
    exit()

# Adjusted red range for better detection
lower_red = np.array([0, 120, 120])  # Lowered saturation and value, kept hue at 0
upper_red = np.array([5, 255, 255])  # Widened hue range slightly

print(f"Using webcam at index {webcam_index}. Press 'q' to quit, adjust lower_red and upper_red in the script to calibrate.")
while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture frame. Exiting.")
        break

    # Convert to HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Create mask for red color
    mask = cv2.inRange(hsv, lower_red, upper_red)
    # Apply dilation to fill small holes in the mask
    mask = cv2.dilate(mask, None, iterations=2)
    result = cv2.bitwise_and(frame, frame, mask=mask)

    # Display the original frame, mask, and result
    cv2.imshow("Original Frame", frame)
    cv2.imshow("Red Mask", mask)
    cv2.imshow("Red Detection", result)

    # Exit on 'q' key
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

# After calibration, update these values in whiffle_fuller_send.py
print(f"Calibrated red range: lower_red = {lower_red}, upper_red = {upper_red}")