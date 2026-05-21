from fastapi import FastAPI, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import anyio
import shutil
import tempfile
from typing import Optional

try:
    import yt_dlp
except Exception:
    yt_dlp = None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ADDON_NAME = "Music_Player_Final_Fixed.mcaddon"
ADDON_PATH = os.path.join(BASE_DIR, ADDON_NAME)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/build-addon")
async def build_addon(youtube_links: Optional[str] = Form(None)):
    """Download any YouTube links (one per line) into `user_music/` then run builder.main().

    Expects form field `youtube_links` as newline- or comma-separated URLs.
    """
    try:
        import builder
    except Exception as e:
        return JSONResponse({"error": f"builder module import failed: {e}"}, status_code=500)

    # If links provided, download them into user_music
    if youtube_links:
        if yt_dlp is None:
            return JSONResponse({"error": "yt_dlp not installed on server"}, status_code=500)

        links = [s.strip() for s in youtube_links.replace(',', '\n').splitlines() if s.strip()]
        if links:
            # ensure user_music exists
            musica_dir = os.path.join(os.path.abspath(os.getcwd()), 'user_music')
            os.makedirs(musica_dir, exist_ok=True)

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(musica_dir, '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    for link in links:
                        ydl.download([link])
            except Exception as e:
                return JSONResponse({"error": f"failed to download links: {e}"}, status_code=500)

    # Run builder in thread
    try:
        await anyio.to_thread.run_sync(builder.main)
    except Exception as e:
        return JSONResponse({"error": f"builder failed: {e}"}, status_code=500)

    if os.path.exists(ADDON_PATH):
        return FileResponse(ADDON_PATH, media_type='application/octet-stream', filename=ADDON_NAME)
    return JSONResponse({"error": "output not found"}, status_code=500)
