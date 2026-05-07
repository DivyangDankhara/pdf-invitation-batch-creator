from pathlib import Path

import fitz
import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import app


def create_fixture_pdf(path: Path, pages: int = 1) -> None:
    doc = fitz.open()
    for index in range(pages):
        page = doc.new_page(width=320, height=420)
        page.insert_text((32, 48), f"Invitation page {index + 1}")
    doc.save(path)
    doc.close()


def test_generate_individual_pdfs(tmp_path: Path) -> None:
    pdf_path = tmp_path / "template.pdf"
    guests_path = tmp_path / "guests.xlsx"
    create_fixture_pdf(pdf_path)
    pd.DataFrame({"Name": ["Divya", "Asha"], "Village": ["Ramgadh", "Surat"]}).to_excel(guests_path, index=False)

    client = TestClient(app)
    session_id = client.post("/api/sessions").json()["sessionId"]
    with pdf_path.open("rb") as file:
      template_response = client.post("/api/sessions/%s/template" % session_id, files={"file": ("template.pdf", file, "application/pdf")})
    assert template_response.status_code == 200

    with guests_path.open("rb") as file:
      guests_response = client.post(
          "/api/sessions/%s/guests" % session_id,
          files={"file": ("guests.xlsx", file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
      )
    assert guests_response.status_code == 200

    config = {
        "filenamePattern": "{Name}_invitation.pdf",
        "fields": [
            {
                "id": "field-1",
                "pageIndex": 0,
                "x": 40,
                "y": 90,
                "width": 180,
                "height": 44,
                "column": "Name",
                "fontId": "builtin:NotoSansGujarati-Regular.ttf",
                "fontSizePt": 16,
                "colorHex": "#ff0000",
                "align": "left",
                "bold": False,
            }
        ],
    }
    preview_response = client.post(
        "/api/sessions/%s/preview" % session_id,
        json={"config": config, "rowIndex": 0, "pageIndex": 0},
    )
    assert preview_response.status_code == 200
    assert preview_response.headers["content-type"] == "image/png"

    generate_response = client.post("/api/sessions/%s/generate" % session_id, json={"config": config})
    assert generate_response.status_code == 200
    job_id = generate_response.json()["jobId"]

    for _ in range(20):
        job = client.get("/api/jobs/%s" % job_id).json()
        if job["status"] == "completed":
            break
    assert job["status"] == "completed"
    assert len(job["files"]) == 2
    assert job["files"][0]["filename"] == "Divya_invitation.pdf"

    download_response = client.get("/api/jobs/%s/files/0" % job_id)
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/pdf"


def test_preview_supports_fields_on_later_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "template.pdf"
    guests_path = tmp_path / "guests.csv"
    create_fixture_pdf(pdf_path, pages=2)
    guests_path.write_text("Name\nDivya\n", encoding="utf-8")

    client = TestClient(app)
    session_id = client.post("/api/sessions").json()["sessionId"]
    with pdf_path.open("rb") as file:
        template_response = client.post(
            "/api/sessions/%s/template" % session_id,
            files={"file": ("template.pdf", file, "application/pdf")},
        )
    assert template_response.status_code == 200

    with guests_path.open("rb") as file:
        guests_response = client.post(
            "/api/sessions/%s/guests" % session_id,
            files={"file": ("guests.csv", file, "text/csv")},
        )
    assert guests_response.status_code == 200

    config = {
        "filenamePattern": "{Name}_invitation.pdf",
        "fields": [
            {
                "id": "field-page-2",
                "pageIndex": 1,
                "x": 40,
                "y": 120,
                "width": 180,
                "height": 44,
                "column": "Name",
                "fontId": "builtin:NotoSansGujarati-Regular.ttf",
                "fontSizePt": 16,
                "colorHex": "#ff0000",
                "align": "left",
                "bold": False,
            }
        ],
    }
    preview_response = client.post(
        "/api/sessions/%s/preview" % session_id,
        json={"config": config, "rowIndex": 0, "pageIndex": 1},
    )

    assert preview_response.status_code == 200
    assert preview_response.headers["content-type"] == "image/png"
