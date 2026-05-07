# PDF Invitation Batch Creator

A local-first web app for generating personalized PDF invitations from a PDF template and an Excel/CSV guest list.

The app is designed for invitation workflows where each guest needs an individual PDF. It supports Gujarati and English text, multiple mapped fields, drag-and-drop placement on PDF pages, accurate preview, and direct output of separate PDF files.

## Features

- Upload a multi-page PDF invitation template.
- Upload guest data from `.xlsx` or `.csv`.
- Add multiple personalized text fields on any PDF page.
- Drag and resize fields directly on the PDF preview.
- Map each field to a guest-list column.
- Configure font, size, color, alignment, and bold styling.
- Use bundled Gujarati-capable fonts or upload a custom `.ttf`/`.otf` font.
- Preview output before generating files.
- Generate one individual PDF per guest into a local `output/` folder.

## Tech Stack

- Frontend: React, TypeScript, Vite, `react-rnd`
- Backend: FastAPI, PyMuPDF, pandas, openpyxl
- Runtime: local Windows-friendly PowerShell workflow

## Requirements

- Windows PowerShell
- Python 3.11 or newer
- Node.js 20 or newer
- npm

The current project has been tested with Python 3.13 and Node.js 22.

## Quick Start

From the project root, run:

```powershell
.\run.ps1
```

The script will:

- create `.venv` if needed
- install backend dependencies
- install frontend dependencies if needed
- start the backend at `http://127.0.0.1:8000`
- start the frontend at `http://127.0.0.1:5173`
- open the app in your browser

Keep the PowerShell window open while using the app. Press `Ctrl+C` in that window to stop both servers.

## How To Use

1. Open `http://127.0.0.1:5173`.
2. Upload a PDF invitation template.
3. Upload a guest list as `.xlsx` or `.csv`.
4. Go to the Design step.
5. Click `Add field`.
6. Drag the field to the desired location on the PDF page.
7. Map the field to a guest-list column.
8. Adjust font, size, color, alignment, and bold styling.
9. Use Preview to verify placement.
10. Generate PDFs.

Generated files are written to:

```text
output/<timestamp>-<template-name>/
```

Each guest gets an individual PDF file. The app does not create ZIP files.

## Guest List Format

The first row must contain column names.

Example:

```csv
Name,Village,Family
Divya Patel,Ramgadh,Patel Family
Asha Shah,Surat,Shah Family
```

Any column can be mapped to a field in the PDF designer. The default output filename pattern uses the first detected column:

```text
{Name}_invitation.pdf
```

Invalid filename characters are removed automatically. Duplicate filenames are renamed with suffixes such as `(2)`.

## Fonts

The app ships with these built-in fonts:

- `NotoSansGujarati-Regular.ttf`
- `Gujrati-Saral.ttf`
- `Shruti.ttf`

You can also upload custom `.ttf` or `.otf` fonts from the Fonts panel.

Gujarati text rendering is handled on the backend with PyMuPDF HTML insertion and embedded font data.

## Project Structure

```text
backend/                 FastAPI backend
backend/app/             API, models, PDF/session services
backend/tests/           Backend unit and integration tests
frontend/                React + Vite frontend
frontend/src/            UI, API client, types, utilities
docs/                    Architecture notes
legacy/                  Original prototype scripts kept for reference
output/                  Generated PDFs, ignored by git
.runtime/                Temporary session files, ignored by git
run.ps1                  One-command local runner
```

## Development

Install backend development dependencies:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
```

Run the backend:

```powershell
.\.venv\Scripts\python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Install frontend dependencies:

```powershell
npm --prefix frontend install
```

Run the frontend:

```powershell
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173
```

## Tests

Backend:

```powershell
.\.venv\Scripts\python -m pytest backend\tests -q
```

Frontend:

```powershell
npm --prefix frontend test
```

Production frontend build:

```powershell
npm --prefix frontend run build
```

Security audit:

```powershell
npm --prefix frontend audit --audit-level=moderate
```

## API Overview

The frontend talks to the FastAPI backend through local REST endpoints:

- `POST /api/sessions`
- `POST /api/sessions/{id}/template`
- `GET /api/sessions/{id}/template/pages/{pageIndex}/image`
- `POST /api/sessions/{id}/guests`
- `GET /api/fonts`
- `POST /api/sessions/{id}/fonts`
- `POST /api/sessions/{id}/preview`
- `POST /api/sessions/{id}/generate`
- `GET /api/jobs/{jobId}`
- `GET /api/jobs/{jobId}/files`
- `GET /api/jobs/{jobId}/files/{fileId}`

See `docs/architecture.md` for more details.

## Troubleshooting

If the browser cannot connect to `127.0.0.1:5173`, make sure `.\run.ps1` is still running.

If ports are already in use, stop old local app processes or rerun:

```powershell
.\run.ps1
```

The runner attempts to clear existing app processes on ports `8000` and `5173` before starting.

If generated text placement looks off, use the Preview step first and regenerate after adjusting the field. Existing PDFs in `output/` are not updated automatically.

## Scope

V1 is local-only and session-only for editing.

Out of scope for this version:

- WhatsApp sending
- saved projects
- user accounts
- CRM or campaign tracking
- QR codes
- cloud hosting
- ZIP export

## Legacy Scripts

The original prototype scripts are preserved in `legacy/` for reference only. The current app does not import or execute them.

## License

MIT. See `LICENSE`.
