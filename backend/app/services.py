from __future__ import annotations

import base64
import html
import os
import re
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import fitz
import pandas as pd
from fastapi import HTTPException, UploadFile

from .models import (
    FontInfo,
    GeneratedFile,
    GuestImportResult,
    JobInfo,
    PageInfo,
    TemplateConfig,
    TemplateInfo,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PROJECT_ROOT / ".runtime"
SESSIONS_ROOT = RUNTIME_ROOT / "sessions"
OUTPUT_ROOT = PROJECT_ROOT / "output"
SESSION_TTL = timedelta(hours=4)
SUPPORTED_FONT_EXTENSIONS = {".ttf", ".otf"}


@dataclass
class SessionState:
    session_id: str
    root: Path
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    template_path: Path | None = None
    template_filename: str | None = None
    template_info: TemplateInfo | None = None
    guests_path: Path | None = None
    guests_filename: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, str]] = field(default_factory=list)
    uploaded_fonts: dict[str, Path] = field(default_factory=dict)


@dataclass
class JobState:
    job_id: str
    session_id: str
    status: str = "queued"
    progress: int = 0
    total: int = 0
    output_folder: Path | None = None
    error: str | None = None
    files: list[GeneratedFile] = field(default_factory=list)

    def to_info(self) -> JobInfo:
        return JobInfo(
            jobId=self.job_id,
            sessionId=self.session_id,
            status=self.status,  # type: ignore[arg-type]
            progress=self.progress,
            total=self.total,
            outputFolder=str(self.output_folder) if self.output_folder else None,
            error=self.error,
            files=self.files,
        )


class AppState:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionState] = {}
        self.jobs: dict[str, JobState] = {}
        self.lock = threading.Lock()

    def create_session(self) -> SessionState:
        session_id = uuid.uuid4().hex
        root = SESSIONS_ROOT / session_id
        root.mkdir(parents=True, exist_ok=True)
        (root / "uploads").mkdir(exist_ok=True)
        (root / "fonts").mkdir(exist_ok=True)
        session = SessionState(session_id=session_id, root=root)
        with self.lock:
            self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> SessionState:
        with self.lock:
            session = self.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        session.updated_at = datetime.now()
        return session

    def create_job(self, session_id: str) -> JobState:
        job_id = uuid.uuid4().hex
        job = JobState(job_id=job_id, session_id=session_id)
        with self.lock:
            self.jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> JobState:
        with self.lock:
            job = self.jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        return job

    def cleanup_expired_sessions(self) -> None:
        cutoff = datetime.now() - SESSION_TTL
        expired: list[SessionState] = []
        with self.lock:
            for session_id, session in list(self.sessions.items()):
                if session.updated_at < cutoff:
                    expired.append(session)
                    del self.sessions[session_id]
        for session in expired:
            shutil.rmtree(session.root, ignore_errors=True)

    def shutdown(self) -> None:
        shutil.rmtree(SESSIONS_ROOT, ignore_errors=True)


app_state = AppState()


def ensure_runtime_dirs() -> None:
    SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def list_builtin_fonts() -> list[FontInfo]:
    candidates = [
        ("builtin:NotoSansGujarati-Regular.ttf", "Noto Sans Gujarati", PROJECT_ROOT / "NotoSansGujarati-Regular.ttf"),
        ("builtin:Gujrati-Saral.ttf", "Gujrati Saral", PROJECT_ROOT / "Gujrati-Saral.ttf"),
        ("builtin:Shruti.ttf", "Shruti", PROJECT_ROOT / "Shruti.ttf"),
    ]
    return [FontInfo(id=font_id, name=name, source="builtin") for font_id, name, path in candidates if path.exists()]


def list_fonts(session: SessionState | None = None) -> list[FontInfo]:
    fonts = list_builtin_fonts()
    if session:
        fonts.extend(
            FontInfo(id=font_id, name=path.stem, source="uploaded")
            for font_id, path in sorted(session.uploaded_fonts.items())
        )
    return fonts


def resolve_font_path(session: SessionState, font_id: str) -> Path:
    builtin_map = {
        "builtin:NotoSansGujarati-Regular.ttf": PROJECT_ROOT / "NotoSansGujarati-Regular.ttf",
        "builtin:Gujrati-Saral.ttf": PROJECT_ROOT / "Gujrati-Saral.ttf",
        "builtin:Shruti.ttf": PROJECT_ROOT / "Shruti.ttf",
    }
    if font_id in builtin_map and builtin_map[font_id].exists():
        return builtin_map[font_id]
    if font_id in session.uploaded_fonts and session.uploaded_fonts[font_id].exists():
        return session.uploaded_fonts[font_id]
    raise HTTPException(status_code=400, detail=f"Font not found: {font_id}")


def sanitize_filename(filename: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", filename.strip())
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" .")
    return cleaned or "invitation.pdf"


def dedupe_filename(filename: str, seen: dict[str, int]) -> str:
    if filename not in seen:
        seen[filename] = 1
        return filename
    seen[filename] += 1
    root, ext = os.path.splitext(filename)
    return f"{root} ({seen[filename]}){ext}"


def extract_pattern_tokens(pattern: str) -> list[str]:
    return re.findall(r"{([^{}]+)}", pattern)


def render_filename(pattern: str, row: dict[str, str], seen: dict[str, int]) -> str:
    def replace_token(match: re.Match[str]) -> str:
        return row.get(match.group(1), "")

    filename = re.sub(r"{([^{}]+)}", replace_token, pattern)
    filename = sanitize_filename(filename)
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    return dedupe_filename(filename, seen)


def safe_stem(filename: str) -> str:
    return sanitize_filename(Path(filename).stem).replace(" ", "-") or "template"


async def save_upload(upload: UploadFile, destination: Path, allowed_extensions: set[str]) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Expected: {allowed}.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    return destination


async def save_template(session: SessionState, upload: UploadFile) -> TemplateInfo:
    filename = sanitize_filename(upload.filename or "template.pdf")
    template_path = session.root / "uploads" / filename
    await save_upload(upload, template_path, {".pdf"})
    try:
        doc = fitz.open(template_path)
    except Exception as exc:  # pragma: no cover - PyMuPDF messages vary
        template_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not open PDF: {exc}") from exc
    try:
        if doc.page_count == 0:
            raise HTTPException(status_code=400, detail="PDF has no pages.")
        pages = [
            PageInfo(pageIndex=index, width=float(page.rect.width), height=float(page.rect.height))
            for index, page in enumerate(doc)
        ]
    finally:
        doc.close()
    info = TemplateInfo(filename=filename, pageCount=len(pages), pages=pages)
    session.template_path = template_path
    session.template_filename = filename
    session.template_info = info
    return info


def normalize_dataframe(df: pd.DataFrame) -> tuple[list[str], list[dict[str, str]]]:
    df = df.dropna(how="all")
    df = df.fillna("")
    columns = [str(column).strip() or f"Column {index + 1}" for index, column in enumerate(df.columns)]
    df.columns = columns
    rows = [
        {column: str(value).strip() for column, value in row.items()}
        for row in df.to_dict(orient="records")
    ]
    rows = [row for row in rows if any(value for value in row.values())]
    return columns, rows


async def save_guests(session: SessionState, upload: UploadFile) -> GuestImportResult:
    suffix = Path(upload.filename or "").suffix.lower()
    filename = sanitize_filename(upload.filename or f"guests{suffix}")
    guests_path = session.root / "uploads" / filename
    await save_upload(upload, guests_path, {".xlsx", ".csv"})
    try:
        if suffix == ".csv":
            try:
                df = pd.read_csv(guests_path, dtype=str, encoding="utf-8-sig")
            except UnicodeDecodeError:
                df = pd.read_csv(guests_path, dtype=str, encoding="cp1252")
        else:
            df = pd.read_excel(guests_path, dtype=str)
    except Exception as exc:
        guests_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not read guest list: {exc}") from exc
    columns, rows = normalize_dataframe(df)
    if not columns or not rows:
        raise HTTPException(status_code=400, detail="Guest list must contain at least one non-empty row.")
    session.guests_path = guests_path
    session.guests_filename = filename
    session.columns = columns
    session.rows = rows
    return GuestImportResult(filename=filename, columns=columns, rowCount=len(rows), sampleRows=rows[:20])


async def save_font(session: SessionState, upload: UploadFile) -> FontInfo:
    filename = sanitize_filename(upload.filename or "font.ttf")
    font_path = session.root / "fonts" / filename
    await save_upload(upload, font_path, SUPPORTED_FONT_EXTENSIONS)
    font_id = f"uploaded:{uuid.uuid4().hex}:{filename}"
    session.uploaded_fonts[font_id] = font_path
    return FontInfo(id=font_id, name=font_path.stem, source="uploaded")


def validate_config(session: SessionState, config: TemplateConfig) -> None:
    if not session.template_path or not session.template_info:
        raise HTTPException(status_code=400, detail="Upload a PDF template first.")
    if not session.rows:
        raise HTTPException(status_code=400, detail="Upload a guest list first.")
    unknown_tokens = [token for token in extract_pattern_tokens(config.filenamePattern) if token not in session.columns]
    if unknown_tokens:
        raise HTTPException(status_code=400, detail=f"Unknown filename column: {unknown_tokens[0]}")
    for field in config.fields:
        if field.column not in session.columns:
            raise HTTPException(status_code=400, detail=f"Unknown field column: {field.column}")
        if field.pageIndex >= session.template_info.pageCount:
            raise HTTPException(status_code=400, detail=f"Field page does not exist: {field.pageIndex + 1}")
        resolve_font_path(session, field.fontId)


def font_face_css(font_path: Path, family_name: str) -> str:
    font_bytes = font_path.read_bytes()
    encoded = base64.b64encode(font_bytes).decode("ascii")
    return (
        "@font-face {"
        f"font-family:'{family_name}';"
        f"src:url(data:font/ttf;base64,{encoded}) format('truetype');"
        "font-weight:normal;font-style:normal;"
        "}"
    )


def field_html(session: SessionState, field: Any, value: str) -> str:
    family = f"InviteFont{uuid.uuid4().hex}"
    font_path = resolve_font_path(session, field.fontId)
    weight = "700" if field.bold else "400"
    return (
        f"<style>{font_face_css(font_path, family)} html, body {{ margin:0; padding:0; }}</style>"
        "<div style=\""
        f"font-family:'{family}';"
        f"font-size:{field.fontSizePt}pt;"
        f"color:{field.colorHex};"
        f"text-align:{field.align};"
        f"font-weight:{weight};"
        "display:block;"
        "line-height:1.12;"
        "margin:0;"
        "padding:0;"
        "white-space:pre-wrap;"
        "\">"
        f"{html.escape(value)}"
        "</div>"
    )


def apply_fields_to_doc(session: SessionState, doc: fitz.Document, config: TemplateConfig, row: dict[str, str]) -> None:
    for field in config.fields:
        page = doc[field.pageIndex]
        rect = fitz.Rect(field.x, field.y, field.x + field.width, field.y + field.height)
        page.insert_htmlbox(rect, field_html(session, field, row.get(field.column, "")), overlay=True)


def render_page_png(template_path: Path, page_index: int, zoom: float = 1.6) -> bytes:
    doc = fitz.open(template_path)
    try:
        if page_index < 0 or page_index >= doc.page_count:
            raise HTTPException(status_code=404, detail="Page not found.")
        pix = doc[page_index].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def render_preview_png(session: SessionState, config: TemplateConfig, row_index: int, page_index: int, zoom: float = 1.6) -> bytes:
    validate_config(session, config)
    if row_index >= len(session.rows):
        raise HTTPException(status_code=400, detail="Guest row does not exist.")
    if not session.template_path:
        raise HTTPException(status_code=400, detail="Upload a PDF template first.")
    source = fitz.open(session.template_path)
    preview = fitz.open()
    try:
        if page_index >= source.page_count:
            raise HTTPException(status_code=404, detail="Page not found.")
        preview.insert_pdf(source, from_page=page_index, to_page=page_index)
        page_config = config.model_copy(
            update={"fields": [field for field in config.fields if field.pageIndex == page_index]}
        )
        if page_config.fields:
            preview_config = page_config.model_copy(
                update={"fields": [field.model_copy(update={"pageIndex": 0}) for field in page_config.fields]}
            )
            apply_fields_to_doc(session, preview, preview_config, session.rows[row_index])
        pix = preview[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")
    finally:
        preview.close()
        source.close()


def generate_output_folder(session: SessionState) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    template_name = safe_stem(session.template_filename or "template")
    output_folder = OUTPUT_ROOT / f"{timestamp}-{template_name}"
    output_folder.mkdir(parents=True, exist_ok=True)
    return output_folder


def generate_pdfs(job: JobState, session: SessionState, config: TemplateConfig) -> None:
    try:
        validate_config(session, config)
        if not session.template_path:
            raise HTTPException(status_code=400, detail="Upload a PDF template first.")
        job.status = "running"
        job.total = len(session.rows)
        job.output_folder = generate_output_folder(session)
        seen: dict[str, int] = {}
        files: list[GeneratedFile] = []
        for index, row in enumerate(session.rows):
            out_doc = fitz.open()
            template_doc = fitz.open(session.template_path)
            try:
                out_doc.insert_pdf(template_doc)
            finally:
                template_doc.close()
            apply_fields_to_doc(session, out_doc, config, row)
            out_doc.subset_fonts()
            filename = render_filename(config.filenamePattern, row, seen)
            output_path = job.output_folder / filename
            out_doc.save(output_path)
            out_doc.close()
            files.append(GeneratedFile(fileId=str(index), filename=filename, size=output_path.stat().st_size))
            job.progress = index + 1
            job.files = files
        job.status = "completed"
    except Exception as exc:
        job.status = "failed"
        job.error = getattr(exc, "detail", str(exc))


def start_generation_job(session: SessionState, config: TemplateConfig) -> JobInfo:
    validate_config(session, config)
    job = app_state.create_job(session.session_id)
    thread = threading.Thread(target=generate_pdfs, args=(job, session, config), daemon=True)
    thread.start()
    return job.to_info()


def generated_file_path(job: JobState, file_id: str) -> Path:
    if not job.output_folder:
        raise HTTPException(status_code=404, detail="Generated files are not ready.")
    try:
        filename = next(file.filename for file in job.files if file.fileId == file_id)
    except StopIteration as exc:
        raise HTTPException(status_code=404, detail="Generated file not found.") from exc
    path = job.output_folder / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Generated file missing from disk.")
    return path
