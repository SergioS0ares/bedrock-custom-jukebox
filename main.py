from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import anyio

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
async def build_addon():
    # Run builder.main() synchronously in a thread
    try:
        import builder
    except Exception as e:
        return JSONResponse({"error": f"builder module import failed: {e}"}, status_code=500)

    try:
        await anyio.to_thread.run_sync(builder.main)
    except Exception as e:
        return JSONResponse({"error": f"builder failed: {e}"}, status_code=500)

    if os.path.exists(ADDON_PATH):
        return FileResponse(ADDON_PATH, media_type='application/octet-stream', filename=ADDON_NAME)
    return JSONResponse({"error": "output not found"}, status_code=500)
