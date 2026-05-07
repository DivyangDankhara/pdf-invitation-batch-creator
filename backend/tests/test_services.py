from pathlib import Path

import fitz
import pandas as pd

from backend.app.models import TemplateConfig, TemplateField
from backend.app.services import (
    SessionState,
    dedupe_filename,
    normalize_dataframe,
    render_filename,
    sanitize_filename,
    validate_config,
)


def test_sanitize_filename_removes_invalid_characters() -> None:
    assert sanitize_filename(' A<>:"/\\|?* name .pdf ') == "A name .pdf"


def test_render_filename_replaces_tokens_and_dedupes() -> None:
    seen: dict[str, int] = {}
    row = {"Name": "Divya/Patel", "Village": "Ramgadh"}
    assert render_filename("{Name}_{Village}.pdf", row, seen) == "DivyaPatel_Ramgadh.pdf"
    assert render_filename("{Name}_{Village}.pdf", row, seen) == "DivyaPatel_Ramgadh (2).pdf"


def test_normalize_dataframe_drops_empty_rows() -> None:
    df = pd.DataFrame({"Name": ["A", None], "Village": ["", None]})
    columns, rows = normalize_dataframe(df)
    assert columns == ["Name", "Village"]
    assert rows == [{"Name": "A", "Village": ""}]


def test_dedupe_filename() -> None:
    seen: dict[str, int] = {}
    assert dedupe_filename("a.pdf", seen) == "a.pdf"
    assert dedupe_filename("a.pdf", seen) == "a (2).pdf"


def test_validate_config_accepts_known_columns_and_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "template.pdf"
    doc = fitz.open()
    doc.new_page(width=300, height=300)
    doc.save(pdf_path)
    doc.close()

    session = SessionState(session_id="test", root=tmp_path)
    session.template_path = pdf_path
    session.template_filename = "template.pdf"
    session.columns = ["Name"]
    session.rows = [{"Name": "અશ્વીન"}]
    session.template_info = type(
        "TemplateInfoStub",
        (),
        {"pageCount": 1},
    )()

    config = TemplateConfig(
        filenamePattern="{Name}.pdf",
        fields=[
            TemplateField(
                id="field",
                pageIndex=0,
                x=10,
                y=10,
                width=100,
                height=40,
                column="Name",
                fontId="builtin:NotoSansGujarati-Regular.ttf",
                fontSizePt=16,
                colorHex="#ff0000",
                align="left",
                bold=False,
            )
        ],
    )

    validate_config(session, config)
