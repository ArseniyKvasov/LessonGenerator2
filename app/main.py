from typing import Annotated, Union, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status

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
from app.services.sections_generator import generate_new_sections, improve_section
from app.services.reference_generator import generate_references
from app.services.tasks_plan_generator import generate_tasks_plan
from app.services.tasks_generator import generate_tasks
from app.services.media_generator import generate_audio_file, generate_image_file

app = FastAPI(
    title="Lesson Generator API",
    version="0.1.0",
)


def verify_api_key(
        x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
) -> None:
    settings = get_settings()

    if not x_api_key or x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
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
    "/generate/section/improve/",
    response_model=Union[ImproveSectionSuccessResponse, ErrorResponse],
    dependencies=[Depends(verify_api_key)],
)
async def improve_section_endpoint(request_data: ImproveSectionRequest):
    return await improve_section(request_data)


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
