import subprocess

from fastapi import FastAPI, Request, Response
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app)

PING_TARGET = "77.88.8.8"


@app.post("/")
async def hello(request: Request):
    if request.headers.get("Test") == "Hello":
        return Response(content="Hello, World!", media_type="text/plain")
    return Response(content="Forbidden", media_type="text/plain", status_code=403)


@app.get("/health")
async def health():
    result = subprocess.run(
        ["ping", "-c", "1", "-W", "2", PING_TARGET],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode == 0:
        return Response(content="OK", media_type="text/plain", status_code=200)
    return Response(content="Unavailable", media_type="text/plain", status_code=503)
