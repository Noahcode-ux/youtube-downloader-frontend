from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import uuid
import threading
import time

app = Flask(__name__)
DOWNLOADS = "downloads"
os.makedirs(DOWNLOADS, exist_ok=True)

# Simple queue system
download_queue = []
queue_lock = threading.Lock()

def process_download(task):
    url = task["url"]
    format_choice = task["format"]
    task_id = task["id"]

    filename = os.path.join(DOWNLOADS, f"{task_id}.%(ext)s")
    ydl_opts = {
        'outtmpl': filename,
        'format': 'bestaudio/best' if format_choice == "mp3" else 'bestvideo+bestaudio/best',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Convert to mp3 if needed
    if format_choice == "mp3":
        mp3_file = os.path.join(DOWNLOADS, f"{task_id}.mp3")
        os.rename(filename.replace("%(ext)s", "webm"), mp3_file)
    task["status"] = "complete"

@app.route("/download", methods=["POST"])
def download():
    data = request.json
    url = data.get("url")
    format_choice = data.get("format")

    task_id = str(uuid.uuid4())
    task = {"id": task_id, "url": url, "format": format_choice, "status": "queued"}
    
    with queue_lock:
        download_queue.append(task)
        position = len(download_queue)

    # Start background thread if first in queue
    def background_task():
        while True:
            with queue_lock:
                if download_queue[0]["id"] != task_id:
                    time.sleep(1)
                    continue
                download_queue.pop(0)
            process_download(task)
            break

    threading.Thread(target=background_task, daemon=True).start()

    return jsonify({"id": task_id, "queue": position, "status": "queued"})

@app.route("/status/<task_id>", methods=["GET"])
def status(task_id):
    for task in download_queue:
        if task["id"] == task_id:
            position = download_queue.index(task)+1
            return jsonify({"queue": position, "status": task["status"], "progress": 0})
    # Check if file exists
    for file in os.listdir(DOWNLOADS):
        if file.startswith(task_id):
            return jsonify({"queue": 0, "status": "complete", "progress": 100})
    return jsonify({"status": "not found"}), 404

if __name__ == "__main__":
    app.run(debug=True)
