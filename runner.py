from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

# Global variable to keep track of the subprocess
process = None
process2 = None

@app.route('/runner', methods=['POST'])
def runner():
    global process
    global process2

    # Accept JSON input with a "command" key
    data = request.get_json(force=True)
    command = data.get('command')

    if command == 'start':
        # Only start if there is no process running
        if process is not None and process.poll() is None:
            return jsonify({"status": "error", "message": "Process already running."}), 400
        
        # Replace the command below with your desired command to run.
        try:
            process = subprocess.Popen(["echo", "Running command..."])
            process2 = subprocess.Popen(["echo", "Running command2..."])
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

        return jsonify({"status": "started"}), 200

    elif command == 'stop':
        if process is None or process.poll() is not None:
            return jsonify({"status": "error", "message": "No running process."}), 400
        
        try:
            process.terminate()
            process2.terminate()
            process.wait(timeout=5)  # Optionally wait for the process to finish
            process2.wait(timeout=5)  # Optionally wait for the process to finish
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
        finally:
            process = None

        return jsonify({"status": "stopped"}), 200

    else:
        return jsonify({"status": "error", "message": "Invalid command."}), 400

if __name__ == '__main__':
    app.run(debug=True)
