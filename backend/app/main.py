import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.logfire_setup import configure_logfire
from app.ws import router as ws_router

configure_logfire(instrument_pydantic_ai=True)

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
