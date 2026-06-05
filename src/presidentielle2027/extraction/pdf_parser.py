from __future__ import annotations

from pathlib import Path

import pdfplumber


def extract_pdf_text(pdf_path: Path) -> str:
    chunks: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                chunks.append(text)
    return "\n\n".join(chunks)

