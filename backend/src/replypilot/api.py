from __future__ import annotations

import secrets

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, status

from .config import Settings, get_settings
from .container import create_service
from .models import DecisionRequest, RunSummary, ScanRequest, ScanResponse
from .service import ReplyPilotService


def create_app(settings: Settings | None = None, service: ReplyPilotService | None = None) -> FastAPI:
    settings = settings or get_settings()
    service = service or create_service(settings)

    def authorize(x_replypilot_key: str | None = Header(default=None)) -> None:
        if not x_replypilot_key or not secrets.compare_digest(x_replypilot_key, settings.control_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid control token")

    app = FastAPI(title="ReplyPilot API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": settings.mode}

    @app.post("/api/runs/scan", response_model=ScanResponse, dependencies=[Depends(authorize)])
    def scan(request: ScanRequest) -> ScanResponse:
        return ScanResponse(runs=service.scan(request))

    @app.get("/api/runs/{run_id}", response_model=RunSummary, dependencies=[Depends(authorize)])
    def get_run(run_id: str) -> RunSummary:
        run = service.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.get("/api/review-queue", response_model=list[RunSummary], dependencies=[Depends(authorize)])
    def review_queue() -> list[RunSummary]:
        return service.review_queue()

    @app.post("/api/runs/{run_id}/decision", response_model=RunSummary, dependencies=[Depends(authorize)])
    def decide(run_id: str, request: DecisionRequest) -> RunSummary:
        try:
            return service.decide(run_id, request)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return app


app = create_app()


def main() -> None:
    uvicorn.run("replypilot.api:app", host="127.0.0.1", port=8000, reload=False)

