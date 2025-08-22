#!/usr/bin/env python3
import os, csv
import pdfplumber
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

def is_scanned_pdf(pdf_path, sample_pages=2):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:sample_pages]:
                txt = page.extract_text() or ""
                if txt.strip():
                    return False
        return True
    except Exception:
        return True

def extract_tables_native(pdf_path, out_csv):
    rows = []
    headers_seen = False
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables or []:
                for row in table:
                    clean = [(c.strip() if isinstance(c, str) else "") for c in row]
                    rows.append(clean)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for r in rows:
            writer.writerow(r)
    return out_csv, len(rows)

def extract_scanned_ocr(pdf_path, out_csv):
    rows = []
    images = convert_from_path(pdf_path, dpi=200)
    for img in images:
        text = pytesseract.image_to_string(img)
        for line in text.splitlines():
            line = line.strip()
            if line:
                rows.append([line])
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["raw_text"])
        for r in rows:
            writer.writerow(r)
    return out_csv, len(rows)

def pdf_to_csv(pdf_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    out_csv = os.path.join(output_dir, base + ".csv")
    if not is_scanned_pdf(pdf_path):
        return extract_tables_native(pdf_path, out_csv)
    else:
        return extract_scanned_ocr(pdf_path, out_csv)
