"""Extract readable text from the document formats accepted by the UI."""

from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import re
from typing import Iterable

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader


class DocumentExtractionError(ValueError):
    """A user-correctable upload or text-extraction problem."""


SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".txt", ".md"}
MAX_DOCX_ARCHIVE_ENTRIES = 1000
MAX_DOCX_EXPANDED_BYTES = 50 * 1024 * 1024
MAX_DOCX_SINGLE_ENTRY_BYTES = 20 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 1000
MAX_PDF_PAGES = 250
MAX_EXTRACTED_CHARACTERS = 2_000_000


def _validate_docx_archive(content: bytes) -> None:
    """Reject zip amplification before python-docx expands the archive."""
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ARCHIVE_ENTRIES:
                raise DocumentExtractionError("Word document contains too many archive entries.")
            total_size = 0
            for entry in entries:
                total_size += entry.file_size
                if (entry.file_size > MAX_DOCX_SINGLE_ENTRY_BYTES or
                        total_size > MAX_DOCX_EXPANDED_BYTES or
                        (entry.file_size and entry.file_size / max(entry.compress_size, 1) >
                         MAX_DOCX_COMPRESSION_RATIO)):
                    raise DocumentExtractionError(
                        "Word document exceeds safe decompression limits. Upload a smaller document."
                    )
    except (BadZipFile, OSError) as exc:
        raise DocumentExtractionError(
            "The Word document could not be opened. Please re-save it as a valid .docx file and upload it again."
        ) from exc



def _clean_text(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _docx_blocks(document: Document) -> Iterable[str]:
    """Yield paragraphs and tables in document order, preserving table text."""
    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            text = Paragraph(child, document).text.strip()
            if text:
                yield text
        elif isinstance(child, CT_Tbl):
            table = Table(child, document)
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    yield " | ".join(cells)


def _extract_docx(content: bytes) -> str:
    _validate_docx_archive(content)
    try:
        document = Document(BytesIO(content))
    except Exception as exc:
        raise DocumentExtractionError(
            "The Word document could not be opened. Please re-save it as a valid .docx file and upload it again."
        ) from exc

    blocks = list(_docx_blocks(document))
    # Include section headers and footers when they contain substantive text.
    for section in document.sections:
        for part in (section.header, section.footer):
            blocks.extend(p.text.strip() for p in part.paragraphs if p.text.strip())
    return _clean_text("\n".join(blocks))


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception as exc:
                raise DocumentExtractionError(
                    "This PDF is password-protected. Upload an unlocked copy so Gilberto can read it."
                ) from exc
            if not unlocked:
                raise DocumentExtractionError(
                    "This PDF is password-protected. Upload an unlocked copy so Gilberto can read it."
                )
        if len(reader.pages) > MAX_PDF_PAGES:
            raise DocumentExtractionError(
                "The PDF has too many pages for one review. Split it into smaller documents."
            )
        pages = []
        total_characters = 0
        for page in reader.pages:
            extracted = page.extract_text() or ""
            total_characters += len(extracted)
            if total_characters > MAX_EXTRACTED_CHARACTERS:
                raise DocumentExtractionError(
                    "The extracted document text is too large for one review. Split it into smaller documents."
                )
            pages.append(extracted)
    except DocumentExtractionError:
        raise
    except Exception as exc:
        raise DocumentExtractionError(
            "The PDF could not be opened. Please upload a valid, unlocked PDF."
        ) from exc

    text = _clean_text("\n\n".join(pages))
    if len(text) < 50:
        raise DocumentExtractionError(
            "No selectable text was found in this PDF. It may be scanned or image-only; run OCR and upload a searchable PDF."
        )
    return text


def _extract_plain_text(content: bytes) -> str:
    try:
        return _clean_text(content.decode("utf-8-sig"))
    except UnicodeDecodeError:
        try:
            return _clean_text(content.decode("cp1252"))
        except UnicodeDecodeError as exc:
            raise DocumentExtractionError(
                "The text file is not valid UTF-8 or Windows-1252 text. Save it as UTF-8 and upload it again."
            ) from exc


def extract_document_text(filename: str, content: bytes) -> str:
    """Extract searchable text based on the uploaded filename extension."""
    extension = Path(filename or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise DocumentExtractionError(
            f"Unsupported file type. Upload one of these formats: {supported}."
        )

    if extension == ".docx":
        text = _extract_docx(content)
    elif extension == ".pdf":
        text = _extract_pdf(content)
    else:
        text = _extract_plain_text(content)

    if len(text) < 50:
        raise DocumentExtractionError(
            "The extracted document text is too short to analyze. Check the file and upload it again."
        )
    if len(text) > MAX_EXTRACTED_CHARACTERS:
        raise DocumentExtractionError(
            "The extracted document text is too large for one review. Split it into smaller documents."
        )
    return text
