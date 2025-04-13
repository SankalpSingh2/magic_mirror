import os
from flask import Flask, send_from_directory, abort, request, jsonify
from werkzeug.utils import secure_filename

# Create the Flask app and specify the static folder
app = Flask(__name__, static_folder='www')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['UPLOAD_FILE'] = 'upload.mp4'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['OUTPUT_FILE'] = 'output.glb'

goingForward = False
goingBack = False
goingLeft = False
goingRight = False

# Route for the root URL
@app.route('/')
def serve_index():
    # Attempt to serve 'index.html' from the www folder
    index_path = os.path.join(app.static_folder, 'index.html')
    if os.path.exists(index_path):
        return send_from_directory(app.static_folder, 'index.html')
    else:
        return "No index.html found in the www directory.", 404

# Generic route to serve any file in the www directory
@app.route('/<path:filename>')
def serve_file(filename):
    # Verify that the file exists to prevent directory traversal
    file_path = os.path.join(app.static_folder, filename)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return send_from_directory(app.static_folder, filename)
    else:
        abort(404)

# POST endpoint for file uploads
@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request.'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected for uploading.'}), 400

    # Check file extension (accept only .mp4)
    if not file.filename.lower().endswith('.mp4'):
        return jsonify({'error': 'Unsupported file type. Please upload an MP4 file.'}), 400

    # Save the file with a fixed name "upload.mp4" so that it overwrites any existing file
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], app.config['UPLOAD_FILE'])
    file.save(save_path)
    
    return jsonify({'message': 'Upload successful', 'filename': app.config['UPLOAD_FILE']}), 200

# GET endpoint to serve output.glb from the output directory
@app.route('/output', methods=['GET'])
def get_output():
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], app.config['OUTPUT_FILE'])
    
    if not os.path.exists(output_path):
        return "no output yet", 200
    
    return send_from_directory(app.config['OUTPUT_FOLDER'], app.config['OUTPUT_FILE'])

# Additional control endpoints. Now they accept both GET and POST.
@app.route('/forward', methods=['POST'])
def forward():
    action = request.json.get('action')
    global goingForward
    if action == 'pressed' and not goingForward:
        goingForward = True
        print("going forward")
    elif action == 'released' and goingForward:
        goingForward = False
        print("stopped going forward")
    return jsonify({'command': 'forward', 'action': action, 'status': 'received'}), 200

@app.route('/back', methods=['POST'])
def back():
    action = request.json.get('action')
    global goingBack
    if action == 'pressed' and not goingBack:
        goingBack = True
        print("going back")
    elif action == 'released' and goingBack:
        goingBack = False
        print("stopped going back")
    return jsonify({'command': 'back', 'action': action, 'status': 'received'}), 200

@app.route('/left', methods=['POST'])
def left():
    action = request.json.get('action')
    global goingLeft
    if action == 'pressed' and not goingLeft:
        goingLeft = True
        print("going left")
    elif action == 'released' and goingLeft:
        goingLeft = False
        print("stopped going left")
    return jsonify({'command': 'left', 'action': action, 'status': 'received'}), 200

@app.route('/right', methods=['POST'])
def right():
    action = request.json.get('action')
    global goingRight
    if action == 'pressed' and not goingRight:
        goingRight = True
        print("going right")
    elif action == 'released' and goingRight:
        goingRight = False
        print("stopped going right")
    return jsonify({'command': 'right', 'action': action, 'status': 'received'}), 200

if __name__ == '__main__':
    # Run the server on all available interfaces and port 5000.
    app.run(debug=True, port=5000)
