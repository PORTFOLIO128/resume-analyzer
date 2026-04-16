"""
Run script for the Resume Analyzer API
Usage: python run.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",   # 0.0.0.0 makes it reachable from mobile devices on the LAN
        port=8000,
        reload=True,       # Hot-reload on file changes
        log_level="info",
    )
