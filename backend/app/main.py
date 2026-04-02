import os

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.logfire_setup import configure_logfire
from app.ws import router as ws_router

configure_logfire(instrument_pydantic_ai=True)


def _frontend_origins() -> list[str]:
    frontend_origin = os.getenv("FRONTEND_ORIGIN")
    if frontend_origin:
        return [frontend_origin]

    frontend_port = os.getenv("FRONTEND_PORT", "5173")
    return [
        f"http://localhost:{frontend_port}",
        f"http://127.0.0.1:{frontend_port}",
    ]


app = FastAPI()
logfire.instrument_fastapi(app)

app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]  # Starlette typing gap
    allow_origins=_frontend_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
