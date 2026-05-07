from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PageInfo(BaseModel):
    pageIndex: int
    width: float
    height: float


class TemplateInfo(BaseModel):
    filename: str
    pageCount: int
    pages: list[PageInfo]


class GuestImportResult(BaseModel):
    filename: str
    columns: list[str]
    rowCount: int
    sampleRows: list[dict[str, str]]


class FontInfo(BaseModel):
    id: str
    name: str
    source: Literal["builtin", "uploaded"]


class TemplateField(BaseModel):
    id: str
    pageIndex: int = Field(ge=0)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    column: str = Field(min_length=1)
    fontId: str = Field(min_length=1)
    fontSizePt: float = Field(gt=0, le=200)
    colorHex: str
    align: Literal["left", "center", "right"] = "left"
    bold: bool = False

    @field_validator("colorHex")
    @classmethod
    def validate_color(cls, value: str) -> str:
        if not value.startswith("#") or len(value) != 7:
            raise ValueError("Color must be a #RRGGBB value.")
        int(value[1:], 16)
        return value


class TemplateConfig(BaseModel):
    filenamePattern: str = Field(min_length=1)
    fields: list[TemplateField] = Field(min_length=1)


class PreviewRequest(BaseModel):
    config: TemplateConfig
    rowIndex: int = Field(ge=0)
    pageIndex: int = Field(ge=0)


class GenerateRequest(BaseModel):
    config: TemplateConfig


class SessionCreateResponse(BaseModel):
    sessionId: str


class GeneratedFile(BaseModel):
    fileId: str
    filename: str
    size: int


class JobInfo(BaseModel):
    jobId: str
    sessionId: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int
    total: int
    outputFolder: str | None = None
    error: str | None = None
    files: list[GeneratedFile] = []
