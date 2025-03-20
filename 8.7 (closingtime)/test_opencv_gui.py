import cv2
import numpy as np

# Create a blank image
img = np.zeros((300, 300, 3), dtype=np.uint8)

# Display the image in a window
cv2.namedWindow("Test Window", cv2.WINDOW_NORMAL)
cv2.imshow("Test Window", img)
cv2.waitKey(0)
cv2.destroyAllWindows()