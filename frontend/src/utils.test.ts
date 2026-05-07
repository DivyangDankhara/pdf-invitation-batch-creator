import { describe, expect, it } from "vitest";

import { defaultFilenamePattern, patternTokens, validateConfig } from "./utils";

describe("filename helpers", () => {
  it("uses the first column for the default filename pattern", () => {
    expect(defaultFilenamePattern(["Guest Name", "Village"])).toBe("{Guest Name}_invitation.pdf");
  });

  it("extracts pattern tokens", () => {
    expect(patternTokens("{Name}_{Village}.pdf")).toEqual(["Name", "Village"]);
  });
});

describe("config validation", () => {
  it("rejects unknown filename pattern columns", () => {
    expect(
      validateConfig(
        {
          filenamePattern: "{Missing}.pdf",
          fields: [
            {
              id: "field-1",
              pageIndex: 0,
              x: 0,
              y: 0,
              width: 100,
              height: 30,
              column: "Name",
              fontId: "font",
              fontSizePt: 12,
              colorHex: "#000000",
              align: "left",
              bold: false,
            },
          ],
        },
        ["Name"],
      ),
    ).toContain("Missing");
  });
});
