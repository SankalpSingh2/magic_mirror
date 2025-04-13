# Run this on the pi
# Dunno if this works with the realsense

from flask import Flask, Response, render_template_string
import cv2
import threading
import time

app = Flask(__name__)

# Global variable to store the latest frame (as JPEG bytes)
output_frame = None
frame_lock = threading.Lock()

# Function that continuously capture frames from the camera
def capture_frames():
    global output_frame
    cap = cv2.VideoCapture(0)  # open the primary camera
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # Encode frame as JPEG
        ret, jpeg = cv2.imencode('.jpg', frame)
        if ret:
            with frame_lock:
                # Overwrite the previous frame so old frames are not stored
                output_frame = jpeg.tobytes()
        # Slight delay to allow other threads to run
        time.sleep(0.03)

# Start the background thread for capturing frames
capture_thread = threading.Thread(target=capture_frames, daemon=True)
capture_thread.start()

# Endpoint that serves the current JPEG frame
@app.route('/frames.jpg')
def frames():
    global output_frame
    with frame_lock:
        if output_frame is None:
            # Return a dummy response until a frame is ready
            return Response(status=503)
        frame = output_frame
    return Response(frame, mimetype='image/jpeg')

# Simple index page to test the video stream
@app.route('/')
def index():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Camera Stream</title>
        <script>
            function refreshImage() {
                var img = document.getElementById("cam");
                img.src = "/frames.jpg?t=" + new Date().getTime();
            }
            setInterval(refreshImage, 50); // refresh every 50ms for smoother video
        </script>
    </head>
    <body>
        <h1>Live Camera Feed</h1>
        <img id="cam" src="/frames.jpg" style="width: 640px; height: 480px;" alt="Camera Stream"/>
    </body>
    </html>
    '''
    return render_template_string(html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)