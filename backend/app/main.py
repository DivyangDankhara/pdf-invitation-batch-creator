from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from .models import (
    FontInfo,
    GenerateRequest,
    GeneratedFile,
    GuestImportResult,
    JobInfo,
    PreviewRequest,
    SessionCreateResponse,
    TemplateInfo,
)
from .services import (
    app_state,
    ensure_runtime_dirs,
    generated_file_path,
    list_fonts,
    render_page_png,
    render_preview_png,
    save_font,
    save_guests,
    save_template,
    start_generation_job,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_runtime_dirs()
    yield
    app_state.shutdown()


app = FastAPI(title="PDF Invitation Batch Creator", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/sessions", response_model=SessionCreateResponse)
def create_session(background_tasks: BackgroundTasks) -> SessionCreateResponse:
    background_tasks.add_task(app_state.cleanup_expired_sessions)
    session = app_state.create_session()
    return SessionCreateResponse(sessionId=session.session_id)


@app.post("/api/sessions/{session_id}/template", response_model=TemplateInfo)
async def upload_template(session_id: str, file: UploadFile = File(...)) -> TemplateInfo:
    session = app_state.get_session(session_id)
    return await save_template(session, file)


@app.get("/api/sessions/{session_id}/template/pages/{page_index}/image")
def page_image(session_id: str, page_index: int) -> Response:
    session = app_state.get_session(session_id)
    if not session.template_path:
        return Response(status_code=404)
    return Response(content=render_page_png(session.template_path, page_index), media_type="image/png")


@app.post("/api/sessions/{session_id}/guests", response_model=GuestImportResult)
async def upload_guests(session_id: str, file: UploadFile = File(...)) -> GuestImportResult:
    session = app_state.get_session(session_id)
    return await save_guests(session, file)


@app.get("/api/fonts", response_model=list[FontInfo])
def fonts() -> list[FontInfo]:
    return list_fonts()


@app.get("/api/sessions/{session_id}/fonts", response_model=list[FontInfo])
def session_fonts(session_id: str) -> list[FontInfo]:
    session = app_state.get_session(session_id)
    return list_fonts(session)


@app.post("/api/sessions/{session_id}/fonts", response_model=FontInfo)
async def upload_font(session_id: str, file: UploadFile = File(...)) -> FontInfo:
    session = app_state.get_session(session_id)
    return await save_font(session, file)


@app.post("/api/sessions/{session_id}/preview")
def preview(session_id: str, request: PreviewRequest) -> Response:
    session = app_state.get_session(session_id)
    png = render_preview_png(session, request.config, request.rowIndex, request.pageIndex)
    return Response(content=png, media_type="image/png")


@app.post("/api/sessions/{session_id}/generate", response_model=JobInfo)
def generate(session_id: str, request: GenerateRequest) -> JobInfo:
    session = app_state.get_session(session_id)
    return start_generation_job(session, request.config)


@app.get("/api/jobs/{job_id}", response_model=JobInfo)
def job_info(job_id: str) -> JobInfo:
    return app_state.get_job(job_id).to_info()


@app.get("/api/jobs/{job_id}/files", response_model=list[GeneratedFile])
def job_files(job_id: str) -> list[GeneratedFile]:
    return app_state.get_job(job_id).files


@app.get("/api/jobs/{job_id}/files/{file_id}")
def download_file(job_id: str, file_id: str) -> FileResponse:
    job = app_state.get_job(job_id)
    path = generated_file_path(job, file_id)
    return FileResponse(path, media_type="application/pdf", filename=path.name)
