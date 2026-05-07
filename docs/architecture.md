# Architecture

This project is a local-first web app with a React frontend and FastAPI backend.

## Runtime

- Frontend runs on `http://127.0.0.1:5173`.
- Backend runs on `http://127.0.0.1:8000`.
- Uploaded templates, guest lists, and preview state live in `.runtime/sessions/`.
- Generated PDFs are written directly to `output/<timestamp>-<template-name>/`.

## PDF Flow

1. The browser uploads a PDF template.
2. The backend stores it in a session temp folder and returns page sizes.
3. The frontend renders backend-provided page images and stores field positions in PDF points.
4. On preview/generate, the backend copies the template and inserts HTML text boxes with embedded font data.
5. PyMuPDF handles final PDF writing and font subsetting.

## Scope

V1 has no accounts, saved projects, WhatsApp delivery, CRM, QR codes, or ZIP output.
