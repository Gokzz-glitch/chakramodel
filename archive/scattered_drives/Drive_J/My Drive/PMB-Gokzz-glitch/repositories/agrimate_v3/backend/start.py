"""
Agrimate V3 - Backend startup script.
Runs as a single lightweight process.
"""
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8080,
        workers=1,
        log_level="warning"  # Quiet mode - only show errors, save CPU
    )
