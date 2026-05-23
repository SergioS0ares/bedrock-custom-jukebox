from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import re
import anyio
import shutil
import collections
import threading
from datetime import datetime
from typing import Optional, List

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
ADDON_NAME = "Bedrock_Custom_Jukebox.mcaddon"
ADDON_PATH = os.path.join(BASE_DIR, ADDON_NAME)
USER_MUSIC_DIR = os.path.join(BASE_DIR, "user_music")
PLAYLISTS_INPUT_FILE = os.path.join(BASE_DIR, "_playlists_input.json")

# --- Live build log (consumed by the frontend modal) -------------
# We only ever run one build at a time, so a single global buffer is enough.
_LOG_LOCK = threading.Lock()
_LOG_BUFFER: "collections.deque[dict]" = collections.deque(maxlen=400)
_BUILD_STATE = {"active": False, "phase": "idle", "progress": None}


def log(msg: str, phase: Optional[str] = None):
    """Append to the live log AND print to the uvicorn terminal."""
    line = {
        "ts": datetime.now().strftime("%H:%M:%S"),
        "msg": msg,
    }
    with _LOG_LOCK:
        _LOG_BUFFER.append(line)
        if phase is not None:
            _BUILD_STATE["phase"] = phase
    print(f"[build-addon] {msg}", flush=True)


def reset_log():
    with _LOG_LOCK:
        _LOG_BUFFER.clear()
        _BUILD_STATE["active"] = True
        _BUILD_STATE["phase"] = "starting"
        _BUILD_STATE["progress"] = None


def finish_log(success: bool):
    with _LOG_LOCK:
        _BUILD_STATE["active"] = False
        _BUILD_STATE["phase"] = "done" if success else "error"
        _BUILD_STATE["progress"] = None


def set_progress(pct: Optional[float], label: Optional[str] = None):
    with _LOG_LOCK:
        _BUILD_STATE["progress"] = {"pct": pct, "label": label} if pct is not None else None


def playlist_slug(name: str) -> str:
    """Match builder.py's slugging: lowercase, spaces → underscores,
    drop everything not alnum/underscore."""
    s = (name or "Geral").strip().lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", s) or "geral"


def reset_user_music():
    """Wipe user_music so old uploads don't end up in the next .mcaddon."""
    if os.path.exists(USER_MUSIC_DIR):
        shutil.rmtree(USER_MUSIC_DIR, ignore_errors=True)
    os.makedirs(USER_MUSIC_DIR, exist_ok=True)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/build-log")
async def build_log():
    """Polled by the frontend modal once per second to show live progress."""
    with _LOG_LOCK:
        return {
            "active": _BUILD_STATE["active"],
            "phase": _BUILD_STATE["phase"],
            "progress": _BUILD_STATE["progress"],
            "lines": list(_LOG_BUFFER),
        }


@app.post("/api/build-addon")
async def build_addon(
    arquivos: Optional[List[UploadFile]] = File(None),
    metadados_json: Optional[str] = Form(None),
    youtube_items_json: Optional[str] = Form(None),
    playlists_json: Optional[str] = Form(None),
    youtube_links: Optional[str] = Form(None),     # legacy
    link_playlist: Optional[str] = Form(None),     # legacy
    nome_addon: Optional[str] = Form(None),
):
    """Receive uploaded MP3s + YouTube links, lay them out under
    user_music/<playlist>/, then run builder.main() which converts every
    file to .ogg (Vorbis) via ffmpeg and zips the .mcaddon."""
    reset_log()
    try:
        import builder
    except Exception as e:
        finish_log(False)
        return JSONResponse({"error": f"builder module import failed: {e}"}, status_code=500)

    # Fresh slate every build — otherwise stale files leak into the addon.
    reset_user_music()
    log("============== NEW BUILD ==============", phase="starting")

    # Persist the user's full playlist list to a sidecar file. The builder
    # picks this up so even empty playlists (e.g. an unused "Geral") show
    # up in the in-game picker.
    if playlists_json:
        try:
            pls = json.loads(playlists_json)
            if isinstance(pls, list):
                with open(PLAYLISTS_INPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(pls, f)
                log(f"playlists declared by user: {pls}")
        except Exception as e:
            log(f"WARN: could not parse playlists_json: {e}")
    else:
        # No declaration -> remove any stale file from a previous build.
        if os.path.exists(PLAYLISTS_INPUT_FILE):
            os.remove(PLAYLISTS_INPUT_FILE)

    # --- Parse per-file metadata (filename -> playlist) -------------
    meta_by_name = {}
    if metadados_json:
        try:
            for entry in json.loads(metadados_json):
                fn = entry.get("filename")
                pl = entry.get("playlist") or "Geral"
                if fn:
                    meta_by_name[fn] = pl
        except Exception as e:
            finish_log(False)
            return JSONResponse({"error": f"metadados_json inválido: {e}"}, status_code=400)

    # --- Save uploaded files under user_music/<playlist_slug>/ -----
    if arquivos:
        log(f"saving {len(arquivos)} uploaded file(s)...", phase="uploading")
        for uf in arquivos:
            playlist = meta_by_name.get(uf.filename, "Geral")
            slug = playlist_slug(playlist)
            target_dir = USER_MUSIC_DIR if slug == "geral" else os.path.join(USER_MUSIC_DIR, slug)
            os.makedirs(target_dir, exist_ok=True)
            safe_name = os.path.basename(uf.filename or "audio.mp3")
            dst = os.path.join(target_dir, safe_name)
            try:
                content = await uf.read()
                with open(dst, "wb") as f:
                    f.write(content)
                log(f"  saved {safe_name} ({len(content) // 1024} KB) -> {playlist}")
            except Exception as e:
                finish_log(False)
                return JSONResponse({"error": f"failed to save {safe_name}: {e}"}, status_code=500)
            finally:
                await uf.close()

    # --- Build the list of YouTube items to download -------------
    # Preferred input is `youtube_items_json` (list of {url, name, playlist}).
    # Fallback is the legacy `youtube_links` + `link_playlist` pair.
    yt_items: List[dict] = []
    if youtube_items_json:
        try:
            for entry in json.loads(youtube_items_json):
                url = (entry.get("url") or "").strip()
                if not url:
                    continue
                yt_items.append({
                    "url": url,
                    "name": (entry.get("name") or "").strip(),
                    "playlist": entry.get("playlist") or "Geral",
                })
        except Exception as e:
            finish_log(False)
            return JSONResponse({"error": f"youtube_items_json inválido: {e}"}, status_code=400)
    elif youtube_links:
        legacy_pl = link_playlist or "Geral"
        for s in youtube_links.replace(",", "\n").splitlines():
            url = s.strip()
            if url:
                yt_items.append({"url": url, "name": "", "playlist": legacy_pl})

    # --- Download YouTube items into the matching playlist folder -
    if yt_items:
        if yt_dlp is None:
            finish_log(False)
            return JSONResponse({"error": "yt_dlp not installed on server"}, status_code=500)

        log(f"downloading {len(yt_items)} YouTube link(s)...", phase="downloading")

        # yt-dlp emits progress dicts; relay them to our buffer so the
        # frontend modal can show download % in real time.
        def make_progress_hook(idx: int, total: int, label: str):
            last_pct = {"v": -1}
            def hook(d):
                status = d.get("status")
                if status == "downloading":
                    tot = d.get("total_bytes") or d.get("total_bytes_estimate")
                    dn = d.get("downloaded_bytes") or 0
                    if tot:
                        pct = round(dn * 100.0 / tot, 1)
                        if pct - last_pct["v"] >= 5 or pct >= 99:
                            last_pct["v"] = pct
                            speed = d.get("speed") or 0
                            mb = tot / 1024 / 1024
                            log(f"  ({idx}/{total}) {label} — {pct}% of {mb:.2f} MB @ {speed/1024/1024:.2f} MB/s")
                            set_progress(pct, f"YouTube {idx}/{total}: {label}")
                elif status == "finished":
                    log(f"  ({idx}/{total}) {label} — download finished, transcoding to mp3...")
                    set_progress(100, f"YouTube {idx}/{total}: post-processing")
            return hook

        for i, item in enumerate(yt_items, 1):
            slug = playlist_slug(item["playlist"])
            target_dir = USER_MUSIC_DIR if slug == "geral" else os.path.join(USER_MUSIC_DIR, slug)
            os.makedirs(target_dir, exist_ok=True)

            # If the user typed a custom name, force the output filename to it.
            # Otherwise fall back to the YouTube video title.
            if item["name"]:
                safe = re.sub(r'[\\/:*?"<>|]', "_", item["name"])
                outtmpl = os.path.join(target_dir, f"{safe}.%(ext)s")
            else:
                outtmpl = os.path.join(target_dir, "%(title)s.%(ext)s")

            label = item["name"] or "(video title)"
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": outtmpl,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "quiet": True,
                "no_warnings": True,
                # Critical: URLs from YouTube radio/playlist pages include
                # `&list=RD...` which makes yt-dlp download the whole auto-
                # generated radio queue. We only ever want the single video
                # the user pasted.
                "noplaylist": True,
                "progress_hooks": [make_progress_hook(i, len(yt_items), label)],
            }
            log(f"  ({i}/{len(yt_items)}) [{item['playlist']}] {label} <- {item['url']}")
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([item["url"]])
            except Exception as e:
                finish_log(False)
                return JSONResponse({"error": f"failed to download {item['url']}: {e}"}, status_code=500)
        log("YouTube downloads done.")
        set_progress(None)

    # --- Run the addon builder (mp3/wav/etc -> .ogg + .mcaddon) ----
    log("running builder (ffmpeg -> .ogg, zipping .mcaddon)...", phase="building")
    try:
        await anyio.to_thread.run_sync(builder.main)
    except Exception as e:
        log(f"builder FAILED: {e}")
        finish_log(False)
        return JSONResponse({"error": f"builder failed: {e}"}, status_code=500)

    if os.path.exists(ADDON_PATH):
        download_name = f"{nome_addon}.mcaddon" if nome_addon else ADDON_NAME
        size_mb = os.path.getsize(ADDON_PATH) / 1024 / 1024
        log(f"DONE -> {download_name} ({size_mb:.2f} MB)", phase="done")
        finish_log(True)
        return FileResponse(ADDON_PATH, media_type="application/octet-stream", filename=download_name)
    log("output not found")
    finish_log(False)
    return JSONResponse({"error": "output not found"}, status_code=500)
