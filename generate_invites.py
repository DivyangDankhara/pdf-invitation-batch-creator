import os
import re
from io import BytesIO

import pandas as pd
from pypdf import PdfReader, PdfWriter
from pypdf._page import PageObject
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# =======================
# USER SETTINGS
# =======================
TEMPLATE_PDF = "invitation_template_Two.pdf"
EXCEL_FILE   = "Two Ramgadh.xlsx"       # uses 1st column unless NAME_COLUMN set
NAME_COLUMN  = None               # e.g. "Full Name" or None

# Placement & style
X = 202
Y = 367
FONT_SIZE = 15
FONT_COLOR_HEX = "#FF0000"        # red

# For Gujarati, use Unicode TTF font (you said you already downloaded it)
#FONT_TTF_PATH = "NotoSansGujarati-Regular.ttf"   # or any .ttf file you placed
#FONT_TTF_PATH = "Gujrati-Saral.ttf"   # or any .ttf file you placed

OUTPUT_DIR = "output\\Gujarati-Saral\Two Ramgadh"
FILE_NAME_FORMAT = "{name} From અશ્વીનભાઇ ડાંખરા પરિવાર.pdf"

# No centering (as requested)
CENTER_TEXT = False
# =======================


def hex_to_rgb01(hex_str: str):
    s = hex_str.strip().lstrip("#")
    return (int(s[0:2], 16)/255.0, int(s[2:4], 16)/255.0, int(s[4:6], 16)/255.0)


def sanitize_filename(filename: str) -> str:
    filename = filename.strip()
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", filename)
    return re.sub(r"\s{2,}", " ", filename)


def read_names_from_excel(path: str, col_name=None):
    df = pd.read_excel(path)
    series = df[col_name] if (col_name and col_name in df.columns) else df[df.columns[0]]
    return [str(x).strip() for x in series.dropna().tolist() if str(x).strip()]


def build_overlay_pdf(page_width, page_height, text, x, y, font_size, rgb, font_name):
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))
    c.setFont(font_name, font_size)
    c.setFillColor(Color(*rgb))

    draw_x = x
    if CENTER_TEXT:
        text_width = pdfmetrics.stringWidth(text, font_name, font_size)
        draw_x = x - (text_width / 2.0)

    c.drawString(draw_x, y, text)
    c.save()
    packet.seek(0)
    return packet


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.isfile(TEMPLATE_PDF):
        raise SystemExit(f"Template not found: {TEMPLATE_PDF}")
    if not os.path.isfile(EXCEL_FILE):
        raise SystemExit(f"Excel file not found: {EXCEL_FILE}")

    # Load template
    template_reader = PdfReader(TEMPLATE_PDF)
    total_pages = len(template_reader.pages)
    if total_pages == 0:
        raise SystemExit("Template PDF has no pages.")

    # Page size
    page0 = template_reader.pages[0]
    page_width = float(page0.mediabox.width)
    page_height = float(page0.mediabox.height)

    # # Register Gujarati font (or any Unicode font)
    # if not os.path.isfile(FONT_TTF_PATH):
    #     raise SystemExit(f"Font file not found: {FONT_TTF_PATH}")
    # font_name = os.path.splitext(os.path.basename(FONT_TTF_PATH))[0]
    # pdfmetrics.registerFont(TTFont(font_name, FONT_TTF_PATH))

    rgb = hex_to_rgb01(FONT_COLOR_HEX)
    names = read_names_from_excel(EXCEL_FILE, NAME_COLUMN)
    if not names:
        raise SystemExit("No names found in Excel file.")

    print(f"Template pages: {total_pages}")
    print(f"Generating {len(names)} invitations...\n")

    seen = {}

    for name in names:
        text_to_draw = name

        writer = PdfWriter()

        for page_index in range(total_pages):
            src_page = template_reader.pages[page_index]

            if page_index == 0:  # only overlay page 1
                overlay_stream = build_overlay_pdf(
                    page_width, page_height, text_to_draw, X, Y, FONT_SIZE, rgb, font_name
                )
                overlay_reader = PdfReader(overlay_stream)
                overlay_page = overlay_reader.pages[0]

                final_page = PageObject.create_blank_page(width=page_width, height=page_height)
                final_page.merge_page(src_page)
                final_page.merge_page(overlay_page)

                writer.add_page(final_page)
            else:
                writer.add_page(src_page)

        filename = sanitize_filename(FILE_NAME_FORMAT.format(name=name))
        output_path = os.path.join(OUTPUT_DIR, filename)

        if output_path in seen:
            seen[output_path] += 1
            root, ext = os.path.splitext(output_path)
            output_path = f"{root} ({seen[output_path]}){ext}"
        else:
            seen[output_path] = 1

        with open(output_path, "wb") as f:
            writer.write(f)

        print(f"✓ {output_path}")

    print("\n✅ Done! All files saved in:", os.path.abspath(OUTPUT_DIR))


if __name__ == "__main__":
    main()
