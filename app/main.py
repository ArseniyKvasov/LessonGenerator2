import logging
import time
from pathlib import Path
from typing import Annotated, Optional, Union

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import Response

from app.config import get_settings
from app.groq_client import models_available
from app.schemas import (
    ErrorResponse,
    GenerateAudioRequest,
    GenerateAudioSuccessResponse,
    GenerateBriefRequest,
    GenerateBriefSuccessResponse,
    GenerateImageRequest,
    GenerateImageSuccessResponse,
    GenerateSectionsRequest,
    GenerateSectionsSuccessResponse,
    GenerateStyleRequest,
    GenerateStyleSuccessResponse,
    HealthResponse,
    ImproveBriefRequest,
    ImproveBriefSuccessResponse,
)
from app.services.brief_generator import generate_brief, improve_brief
from app.services.media_generator import generate_audio_file, generate_image_file
from app.services.sections_generator import generate_sections
from app.services.style_generator import generate_style

app = FastAPI(
    title="Lesson Generator API",
    version="0.2.0",
)

logger = logging.getLogger(__name__)
api_logger = logging.getLogger("api.requests")


def _configure_api_file_logger() -> None:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "api.log"

    if api_logger.handlers:
        return

    handler = logging.FileHandler(log_file, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s | %(message)s")
    handler.setFormatter(formatter)
    api_logger.addHandler(handler)
    api_logger.setLevel(logging.INFO)
    api_logger.propagate = False


_configure_api_file_logger()


def _mask_key(value: Optional[str]) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def verify_api_key(
    request: Request,
    x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
) -> None:
    settings = get_settings()
    expected_key = settings.API_KEY
    is_valid = bool(x_api_key and x_api_key == expected_key)

    logger.info(
        "API key check: valid=%s, client_host=%s, provided=%s (len=%s), expected=%s (len=%s)",
        is_valid,
        request.client.host if request.client else "<unknown>",
        _mask_key(x_api_key),
        len(x_api_key) if x_api_key else 0,
        _mask_key(expected_key),
        len(expected_key),
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


@app.middleware("http")
async def log_api_calls(request: Request, call_next):
    started_at = time.perf_counter()
    request_body_bytes = await request.body()

    try:
        request_body = request_body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        request_body = "<non-utf8-body>"

    response = await call_next(request)

    response_body_bytes = b""
    async for chunk in response.body_iterator:
        response_body_bytes += chunk

    try:
        response_body = response_body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        response_body = "<non-utf8-body>"

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)

    api_logger.info(
        "method=%s path=%s status=%s duration_ms=%s request=%s response=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_body,
        response_body,
    )

    return Response(
        content=response_body_bytes,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
        background=response.background,
    )


@app.get("/health/", response_model=HealthResponse)
def health() -> dict[str, object]:
    available = models_available()
    return {
        "status": "ok" if available else "degraded",
        "models_available": available,
    }


@app.post(
    "/generate/brief/",
    response_model=Union[GenerateBriefSuccessResponse, ErrorResponse],
    dependencies=[Depends(verify_api_key)],
)
async def generate_brief_endpoint(request_data: GenerateBriefRequest):
    return await generate_brief(request_data)


@app.post(
    "/generate/sections/",
    response_model=Union[GenerateSectionsSuccessResponse, ErrorResponse],
    dependencies=[Depends(verify_api_key)],
)
async def generate_sections_endpoint(request_data: GenerateSectionsRequest):
    return await generate_sections(request_data)


@app.post(
    "/generate/style/",
    response_model=Union[GenerateStyleSuccessResponse, ErrorResponse],
    dependencies=[Depends(verify_api_key)],
)
async def generate_style_endpoint(request_data: GenerateStyleRequest):
    return await generate_style(request_data)


@app.post(
    "/generate/brief/improve/",
    response_model=Union[ImproveBriefSuccessResponse, ErrorResponse],
    dependencies=[Depends(verify_api_key)],
)
async def improve_brief_endpoint(request_data: ImproveBriefRequest):
    return await improve_brief(request_data)


@app.post(
    "/generate/image/",
    response_model=Union[GenerateImageSuccessResponse, ErrorResponse],
    dependencies=[Depends(verify_api_key)],
)
async def generate_image_endpoint(request_data: GenerateImageRequest):
    return await generate_image_file(request_data)


@app.post(
    "/generate/audio/",
    response_model=Union[GenerateAudioSuccessResponse, ErrorResponse],
    dependencies=[Depends(verify_api_key)],
)
async def generate_audio_endpoint(request_data: GenerateAudioRequest):
    return await generate_audio_file(request_data)
