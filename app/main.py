import logging
import time
from pathlib import Path
from typing import Annotated, Union, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import Response

from app.config import get_settings
from app.schemas import (
    ErrorResponse,

    GenerateMetaRequest,
    GenerateMetaSuccessResponse,

    GenerateSectionsRequest,
    GenerateSectionsSuccessResponse,
    ImproveSectionRequest,
    ImproveSectionSuccessResponse,

    GenerateReferencesRequest,
    GenerateReferencesSuccessResponse,

    GenerateTasksPlanRequest,
    GenerateTasksPlanSuccessResponse,

    GenerateTasksRequest,
    GenerateTasksSuccessResponse,

    GenerateAudioRequest,
    GenerateAudioSuccessResponse,
    GenerateImageRequest,
    GenerateImageSuccessResponse,
)
from app.services.meta_generator import generate_meta
from app.services.sections_generator import generate_new_sections, improve_sections
from app.services.reference_generator import generate_references
from app.services.tasks_plan_generator import generate_tasks_plan
from app.services.tasks_generator import generate_tasks
from app.services.media_generator import generate_audio_file, generate_image_file

app = FastAPI(
    title="Lesson Generator API",
    version="0.1.0",
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


@app.get("/health/")
def health() -> dict[str, str]:
    return {
        "status": "ok",
    }


@app.post(
    "/generate/meta/",
    response_model=Union[GenerateMetaSuccessResponse, ErrorResponse],
    dependencies=[Depends(verify_api_key)],
)
async def generate_meta_endpoint(request_data: GenerateMetaRequest):
    return await generate_meta(request_data)


@app.post(
    "/generate/sections/new/",
    response_model=Union[GenerateSectionsSuccessResponse, ErrorResponse],
    dependencies=[Depends(verify_api_key)],
)
async def generate_sections_new_endpoint(request_data: GenerateSectionsRequest):
    return await generate_new_sections(request_data)


@app.post(
    "/generate/sections/improve/",
    response_model=Union[ImproveSectionSuccessResponse, ErrorResponse],
    dependencies=[Depends(verify_api_key)],
)
async def improve_sections_endpoint(request_data: ImproveSectionRequest):
    return await improve_sections(request_data)


@app.post(
    "/generate/references/",
    response_model=Union[GenerateReferencesSuccessResponse, ErrorResponse],
    dependencies=[Depends(verify_api_key)],
)
async def generate_references_endpoint(request_data: GenerateReferencesRequest):
    return await generate_references(request_data)


@app.post(
    "/generate/tasks-plan/",
    response_model=Union[GenerateTasksPlanSuccessResponse, ErrorResponse],
    dependencies=[Depends(verify_api_key)],
)
async def generate_tasks_plan_endpoint(request_data: GenerateTasksPlanRequest):
    return await generate_tasks_plan(request_data)


@app.post(
    "/generate/tasks/",
    response_model=Union[GenerateTasksSuccessResponse, ErrorResponse],
    dependencies=[Depends(verify_api_key)],
)
async def generate_tasks_endpoint(request_data: GenerateTasksRequest):
    return await generate_tasks(request_data)


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
