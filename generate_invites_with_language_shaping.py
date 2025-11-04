import os
import re
import base64
import pandas as pd
import fitz  # PyMuPDF

# =======================
# USER SETTINGS
# =======================
TEMPLATE_PDF = "invitation_template_Two.pdf"
EXCEL_FILE   = "Two Ramgadh.xlsx"         # uses first column unless NAME_COLUMN set
NAME_COLUMN  = None                 # e.g. "Full Name" or None

# Placement & style (values you provided; measured from BOTTOM-LEFT like before)
X_BL = 202                          # x in points
Y_BL = 383                          # y in points (bottom-left origin from old script)
FONT_SIZE_PT = 16
FONT_COLOR_HEX = "#FF0000"

# Gujarati font to embed (must exist in same folder)
FONT_TTF_PATH = "NotoSansGujarati-Regular.ttf"

# Output
OUTPUT_DIR = "output\Two Ramgadh"
FILE_NAME_FORMAT = "{name} From અશ્વીનભાઇ ડાંખરા પરિવાર.pdf"

# Text placement behavior
CENTER_TEXT = False   # you asked for LEFT-ALIGNED at (x,y); keep this False
BOX_WIDTH   = 2000    # width of the HTML box in points (big so no wrap)
BOX_HEIGHT  = 200     # height of the HTML box in points
# =======================


def sanitize_filename(filename: str) -> str:
    filename = filename.strip()
    filename = re.sub(r'[<>:\"/\\\\|?*\\x00-\\x1F]', "", filename)
    return re.sub(r"\\s{2,}", " ", filename)


def read_names_from_excel(path: str, col_name=None):
    df = pd.read_excel(path)
    series = df[col_name] if (col_name and col_name in df.columns) else df[df.columns[0]]
    return [str(x).strip() for x in series.dropna().tolist() if str(x).strip()]


def hex_color_to_rgb_tuple(hex_str: str):
    s = hex_str.strip().lstrip("#")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return (r, g, b)


def load_font_as_data_url(ttf_path: str, family_name: str = "InviteGujarati"):
    with open(ttf_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    # Embed the font via data URL for @font-face so insert_htmlbox uses exactly this font
    return f"""
    @font-face {{
        font-family: '{family_name}';
        src: url(data:font/ttf;base64,{b64}) format('truetype');
        font-weight: normal;
        font-style: normal;
    }}
    """


def build_html(name_text: str, font_family: str, font_size_pt: int, hex_color: str, left_align: bool = True):
    align = "left" if left_align else "center"
    # Minimal HTML; we rely on HarfBuzz shaping inside insert_htmlbox
    return f"""
    <div style="font-family:'{font_family}'; font-size:{font_size_pt}pt; color:{hex_color}; text-align:{align};">
        {name_text}
    </div>
    """


def main():
    if not os.path.isfile(TEMPLATE_PDF):
        raise SystemExit(f"Template not found: {TEMPLATE_PDF}")
    if not os.path.isfile(EXCEL_FILE):
        raise SystemExit(f"Excel file not found: {EXCEL_FILE}")
    if not os.path.isfile(FONT_TTF_PATH):
        raise SystemExit(f"Font file not found: {FONT_TTF_PATH}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Read template once to get size & page count
    template_doc = fitz.open(TEMPLATE_PDF)
    if template_doc.page_count == 0:
        raise SystemExit("Template PDF has no pages.")
    page0 = template_doc[0]
    # PyMuPDF coordinates: origin top-left; y increases downward.
    page_width  = page0.rect.width
    page_height = page0.rect.height

    # Convert your bottom-left (ReportLab-style) target to PyMuPDF top-left rect
    # We want left-aligned text starting at (X_BL, Y_BL) in bottom-left coords.
    # For an HTML box, top-left (x0, y0) must be in top-left coords:
    x0 = X_BL
    y0 = page_height - Y_BL  # convert BL->TL
    rect = fitz.Rect(x0, y0, x0 + BOX_WIDTH, y0 + BOX_HEIGHT)

    # Prepare CSS with embedded Gujarati font
    css_font_face = load_font_as_data_url(FONT_TTF_PATH, family_name="InviteGujarati")
    font_family = "InviteGujarati"

    names = read_names_from_excel(EXCEL_FILE, NAME_COLUMN)
    if not names:
        raise SystemExit("No names found in Excel file.")

    seen = {}

    print(f"Template pages: {template_doc.page_count}")
    print(f"Writing names at BL({X_BL},{Y_BL}) -> TL rect {rect} using {FONT_TTF_PATH}\n")
    print(f"Generating {len(names)} invitations...\n")

    for name in names:
        # Make a fresh copy of the template for this guest
        out_doc = fitz.open()
        out_doc.insert_pdf(template_doc)  # copy all pages
        p = out_doc[0]  # first page only gets the overlay

        # Build the HTML (with shaping) and insert at rectangle
        html = build_html(name, font_family, FONT_SIZE_PT, FONT_COLOR_HEX, left_align=(not CENTER_TEXT))
        # Combine CSS + HTML
        html_full = f"<style>{css_font_face}</style>{html}"

        # Draw above existing content (overlay=True)
        p.insert_htmlbox(rect, html_full)

        # Save with requested filename format
        out_name = sanitize_filename(FILE_NAME_FORMAT.format(name=name))
        out_path = os.path.join(OUTPUT_DIR, out_name)

        # De-duplicate filenames if needed
        if out_path in seen:
            seen[out_path] += 1
            root, ext = os.path.splitext(out_path)
            out_path = f"{root} ({seen[out_path]}){ext}"
        else:
            seen[out_path] = 1

        # Subset fonts for smaller files
        out_doc.subset_fonts()
        out_doc.save(out_path)
        out_doc.close()

        print(f"✓ {out_path}")

    template_doc.close()
    print("\n✅ Done! All files saved in:", os.path.abspath(OUTPUT_DIR))


if __name__ == "__main__":
    main()
