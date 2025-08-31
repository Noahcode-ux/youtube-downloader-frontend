from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import json
import asyncio
import uuid
import os

app = FastAPI()

# Allow your GitHub Pages frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://noahcode-ux.github.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Queue system
download_queue = []

class DownloadRequest(BaseModel):
    url: str
    format: str  # 'mp3' or 'mp4'

async def download_video(url, fmt, progress_callback):
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
        'format': 'bestaudio/best' if fmt == 'mp3' else 'bestvideo+bestaudio/best',
        'progress_hooks': [progress_callback],
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}] if fmt == 'mp3' else []
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if fmt == 'mp3':
            filename = os.path.splitext(filename)[0] + ".mp3"
        return filename

@app.post("/download")
async def start_download(request: DownloadRequest):
    download_id = str(uuid.uuid4())
    download_queue.append(download_id)

    async def event_stream():
        async def progress_hook(d):
            if d['status'] == 'downloading':
                percent = d.get('_percent_str', '0.0%').strip()
                yield f"data: {json.dumps({'queue': download_queue.index(download_id)+1, 'progress': percent, 'status': 'downloading'})}\n\n"
            elif d['status'] == 'finished':
                yield f"data: {json.dumps({'queue': 0, 'progress': '100%', 'status': 'complete'})}\n\n"

        try:
            filename = await asyncio.to_thread(download_video, request.url, request.format, progress_hook)
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
        finally:
            download_queue.remove(download_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

