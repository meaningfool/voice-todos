import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ws import router as ws_router

logfire.configure(
    service_name="voice-todos-backend",
    send_to_logfire="if-token-present",
)
logfire.instrument_pydantic_ai()

app = FastAPI()
logfire.instrument_fastapi(app)

app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]  # Starlette typing gap
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
