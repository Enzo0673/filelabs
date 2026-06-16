"""Outils PDF : compression, fusion, découpe, conversion, watermark, etc."""
from compressors.pdf.compress import compress_pdf
from compressors.pdf.tools import (
    merge_pdfs, split_pdf, pdf_to_jpg, jpg_to_pdf,
    rotate_pdf, rotate_pdf_map, watermark_pdf, add_page_numbers,
    delete_pages, unlock_pdf, protect_pdf, repair_pdf, extract_pdf_text,
)

__all__ = [
    "compress_pdf",
    "merge_pdfs", "split_pdf", "pdf_to_jpg", "jpg_to_pdf",
    "rotate_pdf", "rotate_pdf_map", "watermark_pdf", "add_page_numbers",
    "delete_pages", "unlock_pdf", "protect_pdf", "repair_pdf", "extract_pdf_text",
]
