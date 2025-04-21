import cv2
import numpy as np

# Create a blank image
img = np.zeros((300, 300, 3), dtype=np.uint8)

# Display the image in a window
print("Creating window")
cv2.namedWindow("Test Window", cv2.WINDOW_NORMAL)
cv2.moveWindow("Test Window", 0, 0)
cv2.setWindowProperty("Test Window", cv2.WND_PROP_VISIBLE, 1)
print("Displaying image")
cv2.imshow("Test Window", img)
print("Waiting for key press")
cv2.waitKey(0)
cv2.destroyAllWindows()