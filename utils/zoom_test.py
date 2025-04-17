import cv2
import time

# --- Configuration ---
CAMERA_INDEX = 0  # Try 0 for default camera, change if needed (e.g., 1, 2)
ZOOM_STEP = 10    # How much to change the zoom value per key press (adjust as needed)
INITIAL_WAIT_SECONDS = 2 # Small delay to allow camera to initialize
TARGET_WINDOW_WIDTH = 1280 # 720p width
TARGET_WINDOW_HEIGHT = 720 # 720p height

# --- Attempt to open the camera ---
cap = cv2.VideoCapture(CAMERA_INDEX)
# Optional: Try different backends if default doesn't work well
# cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW) # Example for DirectShow on Windows

if not cap.isOpened():
    print(f"Error: Could not open camera at index {CAMERA_INDEX}.")
    print("Check if the camera is connected and not used by another application.")
    print("You might also need to try different CAMERA_INDEX values (e.g., 1, 2).")
    exit()

print(f"Successfully opened camera {CAMERA_INDEX}.")
print(f"Waiting {INITIAL_WAIT_SECONDS} seconds for camera to initialize...")
time.sleep(INITIAL_WAIT_SECONDS) # Give the camera some time

# --- Get initial capture properties (for info) ---
# Store actual capture dimensions
capture_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
capture_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS) # fps can remain float
print(f"Camera Properties: Capture Resolution={capture_width}x{capture_height}, FPS={fps:.2f}")

# --- Test Initial Zoom Value ---
initial_zoom = cap.get(cv2.CAP_PROP_ZOOM)
print("-" * 30)
print(f"Initial value read from cv2.CAP_PROP_ZOOM: {initial_zoom}")
if initial_zoom == 0 or initial_zoom == -1:
    print("NOTE: A value of 0 or -1 often indicates that hardware zoom control is NOT supported by this camera/driver via OpenCV.")
else:
    print("NOTE: A non-zero/non-negative value suggests zoom *might* be supported. Range is camera-specific.")
print("-" * 30)

# --- Initialize Target Zoom ---
# Start with the reported value, or a guess like 100 if the initial seems invalid
target_zoom = initial_zoom if initial_zoom > 0 else 100.0
actual_zoom = initial_zoom # Variable to store the read-back value
set_success = True # Variable to store result of cap.set()

# --- Main Loop ---
print("\nStarting interactive test:")
print("Press '+' to increase target zoom.")
print("Press '-' to decrease target zoom.")
print("Press 'q' to quit.")
print("Observe the image visually and the 'Actual Read' value.")

# --- Create a resizable window ---
WINDOW_NAME = "Zoom Test - Press +/- to change, q to quit"
cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

# --- Set the initial window size to 720p ---
print(f"Setting initial window size to: {TARGET_WINDOW_WIDTH}x{TARGET_WINDOW_HEIGHT}")
cv2.resizeWindow(WINDOW_NAME, TARGET_WINDOW_WIDTH, TARGET_WINDOW_HEIGHT)
# --- End of window size setting ---

while True:
    # --- Read Frame ---
    ret, frame = cap.read()
    if not ret:
        print("Error: Failed to grab frame. Exiting.")
        break

    # --- Store the current frame dimensions (might change if zoom is implemented differently later) ---
    # For putText placement, it's often better to use the original capture height
    # unless the frame is explicitly resized before putText.
    current_frame_h, current_frame_w = frame.shape[:2]


    # --- Attempt to Set Zoom ---
    # Limit target zoom to non-negative values as negative usually makes no sense
    target_zoom = max(0.0, target_zoom)
    set_success = cap.set(cv2.CAP_PROP_ZOOM, target_zoom)

    # --- Read Back Actual Zoom ---
    # Give a tiny moment for the setting to potentially apply
    # time.sleep(0.01) # Optional small delay - uncomment if needed
    actual_zoom = cap.get(cv2.CAP_PROP_ZOOM)

    # --- Display Information on Frame ---
    # Note: Text is added to the original frame (e.g., 640x480).
    # It will appear smaller if the window is much larger (like 1280x720).
    info_text_target = f"Target Zoom : {target_zoom:.1f}"
    info_text_actual = f"Actual Read : {actual_zoom:.1f}"
    info_text_success = f"cap.set success: {set_success}" # Note: This boolean might not always be reliable

    # Use integer coordinates for putText
    cv2.putText(frame, info_text_target, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, info_text_actual, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, info_text_success, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    # Use the original capture height for positioning text at the bottom
    cv2.putText(frame, "Keys: +/- to change, q to quit", (10, int(capture_height - 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    # --- Show Frame ---
    # Display the frame in the window which was pre-sized to 720p
    cv2.imshow(WINDOW_NAME, frame)

    # --- Handle Key Presses ---
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        print("Quit key pressed. Exiting.")
        break
    elif key == ord('+') or key == ord('='):
        target_zoom += ZOOM_STEP
        print(f"Increased target zoom to: {target_zoom:.1f}")
    elif key == ord('-'):
        target_zoom -= ZOOM_STEP
        target_zoom = max(0.0, target_zoom) # Prevent going below zero
        print(f"Decreased target zoom to: {target_zoom:.1f}")

# --- Cleanup ---
print("Releasing camera...")
cap.release()
print("Destroying windows...")
cv2.destroyAllWindows()
print("Script finished.")