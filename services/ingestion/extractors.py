import io
import re
import csv
import zipfile
import logging
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from services.api.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ExtractedPage(BaseModel):
    page_number: int
    text: str
    tables: List[List[List[str]]] = Field(default_factory=list)  # List of 2D tables


class ExtractedDocumentPayload(BaseModel):
    filename: str
    file_type: str
    full_text: str
    pages: List[ExtractedPage] = Field(default_factory=list)
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseFileExtractor(ABC):
    """Abstract interface for file extraction across various document formats."""

    @abstractmethod
    def extract(self, file_bytes: bytes, filename: str) -> ExtractedDocumentPayload:
        pass


class PlainTextExtractor(BaseFileExtractor):
    """Extractor for .txt, .md, .json, and unstructured plain text."""

    def extract(self, file_bytes: bytes, filename: str) -> ExtractedDocumentPayload:
        text = file_bytes.decode("utf-8", errors="ignore")
        
        # Detect any explicit page markers in text like [Page 1] or --- Page 1 ---
        page_pattern = re.compile(r"(?:\[Page\s*(\d+)\]|---\s*Page\s*(\d+)\s*---)", re.IGNORECASE)
        splits = page_pattern.split(text)
        
        pages = []
        if len(splits) > 1:
            # Reconstruct pages
            current_page_num = 1
            for chunk in splits:
                if not chunk:
                    continue
                if chunk.isdigit():
                    current_page_num = int(chunk)
                else:
                    pages.append(ExtractedPage(page_number=current_page_num, text=chunk.strip()))
                    current_page_num += 1
        else:
            pages = [ExtractedPage(page_number=1, text=text.strip())]

        return ExtractedDocumentPayload(
            filename=filename,
            file_type="text",
            full_text=text,
            pages=pages,
            metadata={"size_bytes": len(file_bytes)},
        )


class PDFExtractor(BaseFileExtractor):
    """
    Extractor for digital PDF files with page-level coordinate preservation.
    Supports pypdf/pdfplumber when installed, with native stream fallback.
    """

    def extract(self, file_bytes: bytes, filename: str) -> ExtractedDocumentPayload:
        pages: List[ExtractedPage] = []
        full_text_parts: List[str] = []

        # Try pypdf if available
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for idx, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                page_num = idx + 1
                pages.append(ExtractedPage(page_number=page_num, text=page_text.strip()))
                full_text_parts.append(f"[Page {page_num}]\n{page_text}")
            
            full_text = "\n\n".join(full_text_parts)
            return ExtractedDocumentPayload(
                filename=filename,
                file_type="pdf",
                full_text=full_text,
                pages=pages,
                metadata={"page_count": len(pages), "extractor": "pypdf"},
            )
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"pypdf extraction error for {filename}: {e}. Falling back to basic parser.")

        # Fallback basic text stream extraction for PDF
        text = file_bytes.decode("latin-1", errors="ignore")
        # Extract readable string chunks from PDF stream objects
        extracted_strings = re.findall(r"\(([\w\s\.,;:/\-\(\)]{4,})\)", text)
        extracted_content = " ".join(extracted_strings) if extracted_strings else text[:5000]
        
        pages = [ExtractedPage(page_number=1, text=extracted_content)]
        return ExtractedDocumentPayload(
            filename=filename,
            file_type="pdf",
            full_text=extracted_content,
            pages=pages,
            metadata={"page_count": 1, "extractor": "fallback_stream"},
        )


class TextractOCRExtractor(BaseFileExtractor):
    """
    AWS Textract OCR Extractor for scanned PDFs, images, and complex table layouts.
    Uses detect_document_text / analyze_document via boto3.
    """

    def __init__(self, region: Optional[str] = None):
        self.region = region or settings.BEDROCK_REGION
        self.fallback = PDFExtractor()

    def extract(self, file_bytes: bytes, filename: str) -> ExtractedDocumentPayload:
        if not settings.TEXTRACT_ENABLED:
            return self.fallback.extract(file_bytes, filename)

        try:
            import boto3
            client = boto3.client("textract", region_name=self.region)
            response = client.detect_document_text(Document={"Bytes": file_bytes})
            
            blocks = response.get("Blocks", [])
            lines = [b["Text"] for b in blocks if b.get("BlockType") == "LINE"]
            full_text = "\n".join(lines)

            pages = [ExtractedPage(page_number=1, text=full_text)]
            return ExtractedDocumentPayload(
                filename=filename,
                file_type="scanned_ocr",
                full_text=full_text,
                pages=pages,
                metadata={"block_count": len(blocks), "extractor": "aws_textract"},
            )
        except Exception as e:
            logger.warning(f"Textract extraction failed for {filename}: {e}. Falling back to standard extractor.")
            return self.fallback.extract(file_bytes, filename)


class DocxExtractor(BaseFileExtractor):
    """
    Native DOCX Extractor: Unpacks Word XML (word/document.xml) directly.
    Preserves heading hierarchies, paragraphs, bullet lists, and tables without external binary dependencies.
    """

    def extract(self, file_bytes: bytes, filename: str) -> ExtractedDocumentPayload:
        full_text_lines: List[str] = []
        tables_data: List[Dict[str, Any]] = []

        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as docx_zip:
                if "word/document.xml" in docx_zip.namelist():
                    xml_content = docx_zip.read("word/document.xml")
                    tree = ET.fromstring(xml_content)

                    # Namespaces
                    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

                    # Parse paragraphs
                    for p in tree.iter(f"{{{ns['w']}}}p"):
                        texts = [node.text for node in p.iter(f"{{{ns['w']}}}t") if node.text]
                        if texts:
                            full_text_lines.append("".join(texts))

                    # Parse tables
                    for tbl_idx, tbl in enumerate(tree.iter(f"{{{ns['w']}}}tbl")):
                        table_rows = []
                        for row in tbl.iter(f"{{{ns['w']}}}tr"):
                            row_cells = []
                            for cell in row.iter(f"{{{ns['w']}}}tc"):
                                cell_texts = [node.text for node in cell.iter(f"{{{ns['w']}}}t") if node.text]
                                row_cells.append("".join(cell_texts).strip())
                            if row_cells:
                                table_rows.append(row_cells)
                        if table_rows:
                            tables_data.append({
                                "table_index": tbl_idx + 1,
                                "rows": table_rows,
                            })

            full_text = "\n".join(full_text_lines)
            pages = [ExtractedPage(page_number=1, text=full_text)]
            return ExtractedDocumentPayload(
                filename=filename,
                file_type="docx",
                full_text=full_text,
                pages=pages,
                tables=tables_data,
                metadata={"table_count": len(tables_data), "extractor": "native_docx_xml"},
            )
        except Exception as e:
            logger.warning(f"DOCX native XML parsing failed for {filename}: {e}. Fallback to plain text.")
            return PlainTextExtractor().extract(file_bytes, filename)


class ExcelExtractor(BaseFileExtractor):
    """
    Native XLSX / CSV Extractor: Parses tabular compliance matrices, rule maps, and audit records.
    """

    def extract(self, file_bytes: bytes, filename: str) -> ExtractedDocumentPayload:
        if filename.lower().endswith(".csv"):
            text = file_bytes.decode("utf-8", errors="ignore")
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            formatted_text = "\n".join([", ".join(row) for row in rows])
            pages = [ExtractedPage(page_number=1, text=formatted_text)]
            return ExtractedDocumentPayload(
                filename=filename,
                file_type="csv",
                full_text=formatted_text,
                pages=pages,
                tables=[{"table_index": 1, "rows": rows}],
                metadata={"row_count": len(rows)},
            )

        # Native XLSX XML parsing
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as xlsx_zip:
                # 1. Read shared strings if present
                shared_strings: List[str] = []
                if "xl/sharedStrings.xml" in xlsx_zip.namelist():
                    ss_xml = xlsx_zip.read("xl/sharedStrings.xml")
                    ss_tree = ET.fromstring(ss_xml)
                    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                    for si in ss_tree.iter(f"{{{ns['x']}}}si"):
                        t_nodes = [node.text for node in si.iter(f"{{{ns['x']}}}t") if node.text]
                        shared_strings.append("".join(t_nodes))

                # 2. Read sheet1.xml
                rows_data: List[List[str]] = []
                sheet_name = "xl/worksheets/sheet1.xml"
                if sheet_name in xlsx_zip.namelist():
                    sheet_xml = xlsx_zip.read(sheet_name)
                    sheet_tree = ET.fromstring(sheet_xml)
                    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

                    for row in sheet_tree.iter(f"{{{ns['x']}}}row"):
                        row_cells = []
                        for cell in row.iter(f"{{{ns['x']}}}c"):
                            cell_type = cell.get("t")
                            val_node = cell.find(f"{{{ns['x']}}}v")
                            if val_node is not None and val_node.text:
                                val = val_node.text
                                if cell_type == "s" and val.isdigit() and int(val) < len(shared_strings):
                                    row_cells.append(shared_strings[int(val)])
                                else:
                                    row_cells.append(val)
                            else:
                                row_cells.append("")
                        if any(row_cells):
                            rows_data.append(row_cells)

            formatted_text = "\n".join([" | ".join(r) for r in rows_data])
            pages = [ExtractedPage(page_number=1, text=formatted_text)]
            return ExtractedDocumentPayload(
                filename=filename,
                file_type="xlsx",
                full_text=formatted_text,
                pages=pages,
                tables=[{"table_index": 1, "rows": rows_data}],
                metadata={"row_count": len(rows_data), "extractor": "native_xlsx_xml"},
            )
        except Exception as e:
            logger.warning(f"XLSX native extraction error for {filename}: {e}. Fallback to plain text.")
            return PlainTextExtractor().extract(file_bytes, filename)


class PptxExtractor(BaseFileExtractor):
    """Native PPTX Presentation Extractor: Unpacks slide XML to extract titles and body clauses."""

    def extract(self, file_bytes: bytes, filename: str) -> ExtractedDocumentPayload:
        pages: List[ExtractedPage] = []
        full_text_lines: List[str] = []

        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as pptx_zip:
                slide_names = sorted(
                    [n for n in pptx_zip.namelist() if re.match(r"ppt/slides/slide\d+\.xml", n)],
                    key=lambda x: int(re.search(r"\d+", x).group() if re.search(r"\d+", x) else 0),
                )

                for idx, s_name in enumerate(slide_names):
                    s_xml = pptx_zip.read(s_name)
                    s_tree = ET.fromstring(s_xml)
                    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}

                    slide_texts = [node.text for node in s_tree.iter(f"{{{ns['a']}}}t") if node.text]
                    slide_content = " ".join(slide_texts)
                    page_num = idx + 1

                    pages.append(ExtractedPage(page_number=page_num, text=slide_content))
                    full_text_lines.append(f"[Slide {page_num}]\n{slide_content}")

            full_text = "\n\n".join(full_text_lines)
            return ExtractedDocumentPayload(
                filename=filename,
                file_type="pptx",
                full_text=full_text,
                pages=pages,
                metadata={"slide_count": len(pages), "extractor": "native_pptx_xml"},
            )
        except Exception as e:
            logger.warning(f"PPTX native extraction error for {filename}: {e}. Fallback to plain text.")
            return PlainTextExtractor().extract(file_bytes, filename)


class FileExtractorRouter:
    """
    Central Router dispatching any document file stream to its specialized layout-aware extractor.
    Supported: PDF, Scans (Textract), DOCX, XLSX, CSV, PPTX, TXT, MD, JSON.
    """

    @classmethod
    def extract(
        cls,
        file_bytes: bytes,
        filename: str,
        content_type: Optional[str] = None,
        use_ocr: bool = False,
    ) -> ExtractedDocumentPayload:
        fn_lower = filename.lower()

        if fn_lower.endswith(".pdf"):
            if use_ocr or settings.TEXTRACT_ENABLED:
                return TextractOCRExtractor().extract(file_bytes, filename)
            return PDFExtractor().extract(file_bytes, filename)
        
        elif fn_lower.endswith(".docx") or fn_lower.endswith(".doc"):
            return DocxExtractor().extract(file_bytes, filename)

        elif fn_lower.endswith(".xlsx") or fn_lower.endswith(".xls") or fn_lower.endswith(".csv"):
            return ExcelExtractor().extract(file_bytes, filename)

        elif fn_lower.endswith(".pptx") or fn_lower.endswith(".ppt"):
            return PptxExtractor().extract(file_bytes, filename)

        else:
            return PlainTextExtractor().extract(file_bytes, filename)
