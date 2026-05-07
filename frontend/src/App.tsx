import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  CheckCircle2,
  Download,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
  Type,
  Upload,
} from "lucide-react";
import { Rnd } from "react-rnd";

import {
  fileUrl,
  generatePdfs,
  getFonts,
  getJob,
  pageImageUrl,
  previewPage,
  uploadFont,
  uploadGuests,
  uploadTemplate,
  createSession,
} from "./api";
import type {
  Align,
  FontInfo,
  GeneratedFile,
  GuestImportResult,
  JobInfo,
  PageInfo,
  TemplateConfig,
  TemplateField,
  TemplateInfo,
} from "./types";
import { createField, defaultFilenamePattern, formatBytes, validateConfig } from "./utils";

const steps = ["Template", "Guests", "Design", "Preview", "Generate"] as const;

type Step = (typeof steps)[number];

function App() {
  const [sessionId, setSessionId] = useState("");
  const [activeStep, setActiveStep] = useState<Step>("Template");
  const [template, setTemplate] = useState<TemplateInfo | null>(null);
  const [guests, setGuests] = useState<GuestImportResult | null>(null);
  const [fonts, setFonts] = useState<FontInfo[]>([]);
  const [fields, setFields] = useState<TemplateField[]>([]);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [selectedPageIndex, setSelectedPageIndex] = useState(0);
  const [selectedRowIndex, setSelectedRowIndex] = useState(0);
  const [filenamePattern, setFilenamePattern] = useState("{Name}_invitation.pdf");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [job, setJob] = useState<JobInfo | null>(null);
  const [jobFiles, setJobFiles] = useState<GeneratedFile[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    createSession()
      .then(async (id) => {
        setSessionId(id);
        setFonts(await getFonts(id));
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const timer = window.setInterval(async () => {
      const latest = await getJob(job.jobId);
      setJob(latest);
      if (latest.status === "completed") {
        setJobFiles(latest.files);
      }
    }, 900);
    return () => window.clearInterval(timer);
  }, [job]);

  const config: TemplateConfig = useMemo(
    () => ({ filenamePattern, fields }),
    [fields, filenamePattern],
  );

  const activePage = template?.pages[selectedPageIndex] ?? null;
  const selectedField = fields.find((field) => field.id === selectedFieldId) ?? null;
  const validationError = guests ? validateConfig(config, guests.columns) : "Upload a guest list.";
  const currentSampleRow = guests?.sampleRows[selectedRowIndex] ?? guests?.sampleRows[0] ?? {};

  async function handleTemplate(file: File) {
    setBusy(true);
    setError(null);
    try {
      const info = await uploadTemplate(sessionId, file);
      setTemplate(info);
      setSelectedPageIndex(0);
      setActiveStep("Guests");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleGuests(file: File) {
    setBusy(true);
    setError(null);
    try {
      const info = await uploadGuests(sessionId, file);
      setGuests(info);
      setFilenamePattern(defaultFilenamePattern(info.columns));
      setSelectedRowIndex(0);
      setActiveStep("Design");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleFont(file: File) {
    setBusy(true);
    setError(null);
    try {
      const font = await uploadFont(sessionId, file);
      setFonts((existing) => [...existing, font]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function addField() {
    if (!guests || !fonts.length) return;
    const field = createField(selectedPageIndex, guests.columns[0], fonts[0].id);
    setFields((existing) => [...existing, field]);
    setSelectedFieldId(field.id);
  }

  function updateField(id: string, patch: Partial<TemplateField>) {
    setFields((existing) => existing.map((field) => (field.id === id ? { ...field, ...patch } : field)));
  }

  function deleteField(id: string) {
    setFields((existing) => existing.filter((field) => field.id !== id));
    setSelectedFieldId(null);
  }

  async function renderPreview() {
    if (!sessionId || !template || !guests || validationError) return;
    setBusy(true);
    setError(null);
    try {
      const blob = await previewPage(sessionId, config, selectedRowIndex, selectedPageIndex);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(URL.createObjectURL(blob));
      setActiveStep("Preview");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function runGeneration() {
    if (!sessionId || validationError) return;
    setBusy(true);
    setError(null);
    setJobFiles([]);
    try {
      const started = await generatePdfs(sessionId, config);
      setJob(started);
      setActiveStep("Generate");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>PDF Invitation Batch Creator</h1>
          <p>{template?.filename ?? "Local invitation generator"}</p>
        </div>
        <div className="status-pill">{sessionId ? "Local session ready" : "Starting session"}</div>
      </header>

      <nav className="stepper" aria-label="Workflow">
        {steps.map((step) => (
          <button
            key={step}
            className={step === activeStep ? "step active" : "step"}
            onClick={() => setActiveStep(step)}
            type="button"
          >
            {step}
          </button>
        ))}
      </nav>

      {error ? <div className="alert">{error}</div> : null}

      <section className="workspace">
        <aside className="sidebar">
          <TemplatePanel
            template={template}
            busy={busy || !sessionId}
            onUpload={handleTemplate}
          />
          <GuestsPanel guests={guests} busy={busy || !sessionId} onUpload={handleGuests} />
          <FontPanel fonts={fonts} busy={busy || !sessionId} onUpload={handleFont} />
          <OutputPanel
            filenamePattern={filenamePattern}
            setFilenamePattern={setFilenamePattern}
            guests={guests}
          />
        </aside>

        <section className="main-panel">
          {activeStep === "Template" ? (
            template && sessionId ? (
              <TemplateOverview
                sessionId={sessionId}
                template={template}
                selectedPageIndex={selectedPageIndex}
                setSelectedPageIndex={setSelectedPageIndex}
                openDesign={() => setActiveStep("Design")}
              />
            ) : (
              <EmptyState icon={<FileText />} title="Upload a PDF template" />
            )
          ) : null}

          {activeStep === "Guests" ? (
            <GuestTable guests={guests} selectedRowIndex={selectedRowIndex} setSelectedRowIndex={setSelectedRowIndex} />
          ) : null}

          {activeStep === "Design" ? (
            <Designer
              sessionId={sessionId}
              template={template}
              activePage={activePage}
              selectedPageIndex={selectedPageIndex}
              setSelectedPageIndex={setSelectedPageIndex}
              fields={fields}
              fonts={fonts}
              guests={guests}
              sampleRow={currentSampleRow}
              selectedFieldId={selectedFieldId}
              setSelectedFieldId={setSelectedFieldId}
              selectedField={selectedField}
              addField={addField}
              updateField={updateField}
              deleteField={deleteField}
              renderPreview={renderPreview}
              validationError={validationError}
              busy={busy}
            />
          ) : null}

          {activeStep === "Preview" ? (
            <PreviewPanel
              template={template}
              guests={guests}
              selectedPageIndex={selectedPageIndex}
              setSelectedPageIndex={setSelectedPageIndex}
              selectedRowIndex={selectedRowIndex}
              setSelectedRowIndex={setSelectedRowIndex}
              previewUrl={previewUrl}
              renderPreview={renderPreview}
              runGeneration={runGeneration}
              validationError={validationError}
              busy={busy}
            />
          ) : null}

          {activeStep === "Generate" ? (
            <GeneratePanel job={job} files={jobFiles.length ? jobFiles : job?.files ?? []} />
          ) : null}
        </section>
      </section>
    </main>
  );
}

function FileInput({
  label,
  accept,
  disabled,
  onFile,
}: {
  label: string;
  accept: string;
  disabled: boolean;
  onFile: (file: File) => void;
}) {
  return (
    <label className={disabled ? "upload-button disabled" : "upload-button"}>
      <Upload size={16} />
      {label}
      <input
        disabled={disabled}
        type="file"
        accept={accept}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
          event.currentTarget.value = "";
        }}
      />
    </label>
  );
}

function TemplatePanel({
  template,
  busy,
  onUpload,
}: {
  template: TemplateInfo | null;
  busy: boolean;
  onUpload: (file: File) => void;
}) {
  return (
    <section className="control-section">
      <h2><FileText size={17} /> Template</h2>
      <FileInput label="Upload PDF" accept="application/pdf,.pdf" disabled={busy} onFile={onUpload} />
      {template ? (
        <dl className="compact-list">
          <div><dt>File</dt><dd>{template.filename}</dd></div>
          <div><dt>Pages</dt><dd>{template.pageCount}</dd></div>
        </dl>
      ) : null}
    </section>
  );
}

function GuestsPanel({
  guests,
  busy,
  onUpload,
}: {
  guests: GuestImportResult | null;
  busy: boolean;
  onUpload: (file: File) => void;
}) {
  return (
    <section className="control-section">
      <h2><FileSpreadsheet size={17} /> Guests</h2>
      <FileInput label="Upload Excel/CSV" accept=".xlsx,.csv" disabled={busy} onFile={onUpload} />
      {guests ? (
        <dl className="compact-list">
          <div><dt>Rows</dt><dd>{guests.rowCount}</dd></div>
          <div><dt>Columns</dt><dd>{guests.columns.join(", ")}</dd></div>
        </dl>
      ) : null}
    </section>
  );
}

function FontPanel({
  fonts,
  busy,
  onUpload,
}: {
  fonts: FontInfo[];
  busy: boolean;
  onUpload: (file: File) => void;
}) {
  return (
    <section className="control-section">
      <h2><Type size={17} /> Fonts</h2>
      <FileInput label="Upload TTF/OTF" accept=".ttf,.otf" disabled={busy} onFile={onUpload} />
      <div className="font-list">
        {fonts.map((font) => (
          <span key={font.id}>{font.name}</span>
        ))}
      </div>
    </section>
  );
}

function OutputPanel({
  filenamePattern,
  setFilenamePattern,
  guests,
}: {
  filenamePattern: string;
  setFilenamePattern: (value: string) => void;
  guests: GuestImportResult | null;
}) {
  return (
    <section className="control-section">
      <h2><FolderOpen size={17} /> Output</h2>
      <label className="field-label">
        Filename pattern
        <input value={filenamePattern} onChange={(event) => setFilenamePattern(event.target.value)} />
      </label>
      {guests ? <div className="token-row">{guests.columns.map((column) => <code key={column}>{`{${column}}`}</code>)}</div> : null}
    </section>
  );
}

function TemplateOverview({
  sessionId,
  template,
  selectedPageIndex,
  setSelectedPageIndex,
  openDesign,
}: {
  sessionId: string;
  template: TemplateInfo;
  selectedPageIndex: number;
  setSelectedPageIndex: (index: number) => void;
  openDesign: () => void;
}) {
  return (
    <div className="template-overview">
      <div className="panel-heading">
        <div>
          <h2>Template Pages</h2>
          <p>{template.filename}</p>
        </div>
        <button className="primary-button" onClick={openDesign} type="button">
          <Type size={17} /> Design fields
        </button>
      </div>
      <div className="thumbnail-grid">
        {template.pages.map((page) => (
          <button
            key={page.pageIndex}
            className={page.pageIndex === selectedPageIndex ? "page-thumb active" : "page-thumb"}
            onClick={() => setSelectedPageIndex(page.pageIndex)}
            type="button"
          >
            <img src={pageImageUrl(sessionId, page.pageIndex)} alt={`Template page ${page.pageIndex + 1}`} />
            <span>Page {page.pageIndex + 1}</span>
            <small>
              {Math.round(page.width)} x {Math.round(page.height)} pt
            </small>
          </button>
        ))}
      </div>
    </div>
  );
}

function GuestTable({
  guests,
  selectedRowIndex,
  setSelectedRowIndex,
}: {
  guests: GuestImportResult | null;
  selectedRowIndex: number;
  setSelectedRowIndex: (row: number) => void;
}) {
  if (!guests) return <EmptyState icon={<FileSpreadsheet />} title="Upload a guest list" />;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Preview</th>
            {guests.columns.map((column) => <th key={column}>{column}</th>)}
          </tr>
        </thead>
        <tbody>
          {guests.sampleRows.map((row, index) => (
            <tr key={index} className={index === selectedRowIndex ? "selected-row" : ""}>
              <td>
                <button className="icon-button" onClick={() => setSelectedRowIndex(index)} type="button">
                  <CheckCircle2 size={16} />
                </button>
              </td>
              {guests.columns.map((column) => <td key={column}>{row[column]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Designer(props: {
  sessionId: string;
  template: TemplateInfo | null;
  activePage: PageInfo | null;
  selectedPageIndex: number;
  setSelectedPageIndex: (index: number) => void;
  fields: TemplateField[];
  fonts: FontInfo[];
  guests: GuestImportResult | null;
  sampleRow: Record<string, string>;
  selectedFieldId: string | null;
  setSelectedFieldId: (id: string | null) => void;
  selectedField: TemplateField | null;
  addField: () => void;
  updateField: (id: string, patch: Partial<TemplateField>) => void;
  deleteField: (id: string) => void;
  renderPreview: () => void;
  validationError: string | null;
  busy: boolean;
}) {
  if (!props.template || !props.activePage) return <EmptyState icon={<FileText />} title="Upload a PDF template" />;
  if (!props.guests) return <EmptyState icon={<FileSpreadsheet />} title="Upload a guest list" />;

  return (
    <div className="designer-grid">
      <div className="designer-surface">
        <PageTabs
          pages={props.template.pages}
          selectedPageIndex={props.selectedPageIndex}
          setSelectedPageIndex={props.setSelectedPageIndex}
        />
        <PdfCanvas
          sessionId={props.sessionId}
          page={props.activePage}
          fields={props.fields.filter((field) => field.pageIndex === props.selectedPageIndex)}
          sampleRow={props.sampleRow}
          selectedFieldId={props.selectedFieldId}
          setSelectedFieldId={props.setSelectedFieldId}
          updateField={props.updateField}
        />
      </div>
      <aside className="field-editor">
        <div className="editor-actions">
          <button className="primary-button" onClick={props.addField} type="button">
            <Plus size={17} /> Add field
          </button>
          <button
            className="secondary-button"
            onClick={props.renderPreview}
            disabled={!!props.validationError || props.busy}
            type="button"
          >
            {props.busy ? <Loader2 className="spin" size={17} /> : <RefreshCw size={17} />}
            Preview
          </button>
        </div>
        {props.selectedField ? (
          <FieldEditor
            field={props.selectedField}
            guests={props.guests}
            fonts={props.fonts}
            updateField={props.updateField}
            deleteField={props.deleteField}
          />
        ) : (
          <div className="muted-panel">Select a field from the page or list.</div>
        )}
        <FieldList
          fields={props.fields}
          selectedFieldId={props.selectedFieldId}
          setSelectedFieldId={props.setSelectedFieldId}
          setSelectedPageIndex={props.setSelectedPageIndex}
        />
        {props.validationError ? <div className="soft-error">{props.validationError}</div> : null}
      </aside>
    </div>
  );
}

function PageTabs({
  pages,
  selectedPageIndex,
  setSelectedPageIndex,
}: {
  pages: PageInfo[];
  selectedPageIndex: number;
  setSelectedPageIndex: (index: number) => void;
}) {
  return (
    <div className="page-tabs">
      {pages.map((page) => (
        <button
          key={page.pageIndex}
          className={page.pageIndex === selectedPageIndex ? "active" : ""}
          onClick={() => setSelectedPageIndex(page.pageIndex)}
          type="button"
        >
          Page {page.pageIndex + 1}
        </button>
      ))}
    </div>
  );
}

function PdfCanvas({
  sessionId,
  page,
  fields,
  sampleRow,
  selectedFieldId,
  setSelectedFieldId,
  updateField,
}: {
  sessionId: string;
  page: PageInfo;
  fields: TemplateField[];
  sampleRow: Record<string, string>;
  selectedFieldId: string | null;
  setSelectedFieldId: (id: string | null) => void;
  updateField: (id: string, patch: Partial<TemplateField>) => void;
}) {
  const outerRef = useRef<HTMLDivElement | null>(null);
  const [outerSize, setOuterSize] = useState({ width: 0, height: 0 });
  const canvasPadding = 28;
  const availableWidth = Math.max(1, outerSize.width - canvasPadding);
  const availableHeight = Math.max(1, outerSize.height - canvasPadding);
  const scale = Math.min(availableWidth / page.width, availableHeight / page.height, 1.35);
  const displayWidth = page.width * scale;
  const displayHeight = page.height * scale;

  useEffect(() => {
    if (!outerRef.current) return undefined;
    const element = outerRef.current;
    const updateSize = () => {
      setOuterSize({
        width: element.clientWidth,
        height: element.clientHeight,
      });
    };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="canvas-outer" ref={outerRef}>
      <div
        className="pdf-canvas"
        style={{ width: displayWidth, height: displayHeight }}
        onPointerDown={() => setSelectedFieldId(null)}
      >
        <img src={pageImageUrl(sessionId, page.pageIndex)} alt={`Page ${page.pageIndex + 1}`} />
        {fields.map((field) => (
          <Rnd
            key={field.id}
            bounds="parent"
            position={{ x: field.x * scale, y: field.y * scale }}
            size={{ width: field.width * scale, height: field.height * scale }}
            minWidth={40}
            minHeight={18}
            onMouseDown={(event) => {
              event.stopPropagation();
              setSelectedFieldId(field.id);
            }}
            onDragStop={(_, data) => {
              setSelectedFieldId(field.id);
              updateField(field.id, { x: data.x / scale, y: data.y / scale });
            }}
            onDragStart={() => setSelectedFieldId(field.id)}
            onResizeStart={() => setSelectedFieldId(field.id)}
            onResizeStop={(_, __, ref, ___, position) => {
              setSelectedFieldId(field.id);
              updateField(field.id, {
                x: position.x / scale,
                y: position.y / scale,
                width: ref.offsetWidth / scale,
                height: ref.offsetHeight / scale,
              });
            }}
          >
            <div
              role="button"
              tabIndex={0}
              className={field.id === selectedFieldId ? "field-box selected" : "field-box"}
              style={{
                fontSize: Math.max(10, field.fontSizePt * scale),
                color: field.colorHex,
                textAlign: field.align,
                fontWeight: field.bold ? 700 : 400,
              }}
              onPointerDown={(event) => {
                event.stopPropagation();
                setSelectedFieldId(field.id);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  setSelectedFieldId(field.id);
                }
              }}
            >
              {sampleRow[field.column] || field.column}
            </div>
          </Rnd>
        ))}
      </div>
    </div>
  );
}

function FieldEditor({
  field,
  guests,
  fonts,
  updateField,
  deleteField,
}: {
  field: TemplateField;
  guests: GuestImportResult;
  fonts: FontInfo[];
  updateField: (id: string, patch: Partial<TemplateField>) => void;
  deleteField: (id: string) => void;
}) {
  return (
    <div className="editor-form">
      <div className="selected-field-card">
        <span>Selected field</span>
        <strong>{field.column}</strong>
        <small>Page {field.pageIndex + 1}</small>
      </div>
      <label className="field-label">
        Column
        <select value={field.column} onChange={(event) => updateField(field.id, { column: event.target.value })}>
          {guests.columns.map((column) => <option key={column}>{column}</option>)}
        </select>
      </label>
      <label className="field-label">
        Font
        <select value={field.fontId} onChange={(event) => updateField(field.id, { fontId: event.target.value })}>
          {fonts.map((font) => <option key={font.id} value={font.id}>{font.name}</option>)}
        </select>
      </label>
      <div className="two-col">
        <label className="field-label">
          Size
          <input
            type="number"
            value={field.fontSizePt}
            min={1}
            max={200}
            onChange={(event) => updateField(field.id, { fontSizePt: Number(event.target.value) })}
          />
        </label>
        <label className="field-label">
          Color
          <input type="color" value={field.colorHex} onChange={(event) => updateField(field.id, { colorHex: event.target.value })} />
        </label>
      </div>
      <label className="field-label">
        Align
        <select value={field.align} onChange={(event) => updateField(field.id, { align: event.target.value as Align })}>
          <option value="left">Left</option>
          <option value="center">Center</option>
          <option value="right">Right</option>
        </select>
      </label>
      <label className="toggle-row">
        <input
          type="checkbox"
          checked={field.bold}
          onChange={(event) => updateField(field.id, { bold: event.target.checked })}
        />
        Bold
      </label>
      <button className="danger-button" onClick={() => deleteField(field.id)} type="button">
        <Trash2 size={17} /> Delete field
      </button>
    </div>
  );
}

function FieldList({
  fields,
  selectedFieldId,
  setSelectedFieldId,
  setSelectedPageIndex,
}: {
  fields: TemplateField[];
  selectedFieldId: string | null;
  setSelectedFieldId: (id: string | null) => void;
  setSelectedPageIndex: (index: number) => void;
}) {
  if (!fields.length) {
    return <div className="muted-panel">Added fields will show here.</div>;
  }

  return (
    <section className="field-list-panel">
      <h3>Added fields</h3>
      <div className="field-list">
        {fields.map((field, index) => (
          <button
            key={field.id}
            className={field.id === selectedFieldId ? "field-list-item active" : "field-list-item"}
            onClick={() => {
              setSelectedPageIndex(field.pageIndex);
              setSelectedFieldId(field.id);
            }}
            type="button"
          >
            <span>{index + 1}. {field.column}</span>
            <small>Page {field.pageIndex + 1}</small>
          </button>
        ))}
      </div>
    </section>
  );
}

function PreviewPanel(props: {
  template: TemplateInfo | null;
  guests: GuestImportResult | null;
  selectedPageIndex: number;
  setSelectedPageIndex: (index: number) => void;
  selectedRowIndex: number;
  setSelectedRowIndex: (index: number) => void;
  previewUrl: string | null;
  renderPreview: () => void;
  runGeneration: () => void;
  validationError: string | null;
  busy: boolean;
}) {
  if (!props.template || !props.guests) return <EmptyState icon={<FileText />} title="Upload files first" />;
  return (
    <div className="preview-grid">
      <aside className="preview-controls">
        <PageTabs pages={props.template.pages} selectedPageIndex={props.selectedPageIndex} setSelectedPageIndex={props.setSelectedPageIndex} />
        <label className="field-label">
          Guest row
          <select value={props.selectedRowIndex} onChange={(event) => props.setSelectedRowIndex(Number(event.target.value))}>
            {props.guests.sampleRows.map((row, index) => (
              <option key={index} value={index}>
                {index + 1}. {Object.values(row).filter(Boolean).slice(0, 2).join(" - ")}
              </option>
            ))}
          </select>
        </label>
        <button className="secondary-button" onClick={props.renderPreview} disabled={props.busy || !!props.validationError} type="button">
          {props.busy ? <Loader2 className="spin" size={17} /> : <RefreshCw size={17} />} Refresh
        </button>
        <button className="primary-button" onClick={props.runGeneration} disabled={props.busy || !!props.validationError} type="button">
          <Download size={17} /> Generate PDFs
        </button>
        {props.validationError ? <div className="soft-error">{props.validationError}</div> : null}
      </aside>
      <div className="preview-image-wrap">
        {props.previewUrl ? <img src={props.previewUrl} alt="Preview" /> : <EmptyState icon={<RefreshCw />} title="Render preview" />}
      </div>
    </div>
  );
}

function GeneratePanel({ job, files }: { job: JobInfo | null; files: GeneratedFile[] }) {
  if (!job) return <EmptyState icon={<Download />} title="Generate PDFs" />;
  const percent = job.total ? Math.round((job.progress / job.total) * 100) : 0;
  return (
    <div className="generate-panel">
      <div className="job-summary">
        <div>
          <h2>{job.status === "completed" ? "Generated PDFs" : "Generating"}</h2>
          <p>{job.outputFolder ?? "Preparing output folder"}</p>
        </div>
        <strong>{percent}%</strong>
      </div>
      <div className="progress-track"><div style={{ width: `${percent}%` }} /></div>
      {job.error ? <div className="alert">{job.error}</div> : null}
      <div className="file-list">
        {files.map((file) => (
          <a key={file.fileId} href={fileUrl(job.jobId, file.fileId)} target="_blank" rel="noreferrer">
            <FileText size={17} />
            <span>{file.filename}</span>
            <small>{formatBytes(file.size)}</small>
          </a>
        ))}
      </div>
    </div>
  );
}

function EmptyState({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="empty-state">
      {icon}
      <h2>{title}</h2>
    </div>
  );
}

export default App;
