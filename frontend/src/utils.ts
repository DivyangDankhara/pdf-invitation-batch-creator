import type { TemplateConfig, TemplateField } from "./types";

export function defaultFilenamePattern(columns: string[]): string {
  const first = columns[0] ?? "Name";
  return `{${first}}_invitation.pdf`;
}

export function createField(pageIndex: number, column: string, fontId: string): TemplateField {
  return {
    id: crypto.randomUUID(),
    pageIndex,
    x: 96,
    y: 96,
    width: 260,
    height: 42,
    column,
    fontId,
    fontSizePt: 18,
    colorHex: "#C82127",
    align: "left",
    bold: false,
  };
}

export function patternTokens(pattern: string): string[] {
  return [...pattern.matchAll(/{([^{}]+)}/g)].map((match) => match[1]);
}

export function validateConfig(config: TemplateConfig, columns: string[]): string | null {
  if (!config.fields.length) {
    return "Add at least one text field.";
  }
  const missingField = config.fields.find((field) => !field.column || !columns.includes(field.column));
  if (missingField) {
    return "Each field must map to a guest column.";
  }
  const unknownToken = patternTokens(config.filenamePattern).find((token) => !columns.includes(token));
  if (unknownToken) {
    return `Filename pattern uses an unknown column: ${unknownToken}`;
  }
  return null;
}

export function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}
