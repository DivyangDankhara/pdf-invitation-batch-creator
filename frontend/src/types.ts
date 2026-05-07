export type Align = "left" | "center" | "right";

export type PageInfo = {
  pageIndex: number;
  width: number;
  height: number;
};

export type TemplateInfo = {
  filename: string;
  pageCount: number;
  pages: PageInfo[];
};

export type GuestImportResult = {
  filename: string;
  columns: string[];
  rowCount: number;
  sampleRows: Record<string, string>[];
};

export type FontInfo = {
  id: string;
  name: string;
  source: "builtin" | "uploaded";
};

export type TemplateField = {
  id: string;
  pageIndex: number;
  x: number;
  y: number;
  width: number;
  height: number;
  column: string;
  fontId: string;
  fontSizePt: number;
  colorHex: string;
  align: Align;
  bold: boolean;
};

export type TemplateConfig = {
  filenamePattern: string;
  fields: TemplateField[];
};

export type GeneratedFile = {
  fileId: string;
  filename: string;
  size: number;
};

export type JobInfo = {
  jobId: string;
  sessionId: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  total: number;
  outputFolder: string | null;
  error: string | null;
  files: GeneratedFile[];
};
