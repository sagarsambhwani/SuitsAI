# Ingestion Pipeline & Document Processing Guide

> **Layout-Aware Multi-Format Parsing & Hierarchical Semantic Chunking**

---

## 1. Multi-Format Extraction Architecture

SuitsAI handles heterogeneous banking and regulatory document formats through a specialized layout-aware extractor framework located in [services/ingestion/extractors.py](file:///e:/Downloads/VoyagerAI/services/ingestion/extractors.py).

```text
Uploaded File (PDF / Scans / DOCX / XLSX / PPTX / TXT)
                         │
                         ▼
             [FileExtractorRouter]
                         │
      ┌──────────────────┼──────────────────┬──────────────────┐
      ▼                  ▼                  ▼                  ▼
[PDFExtractor]    [DocxExtractor]    [ExcelExtractor]    [PptxExtractor]
 digital text      native Word XML     tabular rows /     slide decks &
 & page bounds     headings & tables   matrices / CSV     body frames
      │
      ├── (If Scanned / Image)
      ▼
[TextractOCRExtractor]
 AWS Textract layout & table OCR
```

---

## 2. Supported Formats & Extraction Mechanics

### 1. Digital PDF (`.pdf`)
* **Extractor**: `PDFExtractor`
* **Mechanisms**: Extracts text page-by-page, preserving page numbering, section headings, and paragraph coordinates. Fallback stream parser handles non-standard or compressed streams.

### 2. Scanned Circulars & Physical Documents (`.pdf`, `.png`, `.jpg`)
* **Extractor**: `TextractOCRExtractor`
* **Mechanisms**: Invokes AWS Textract (`detect_document_text` / `analyze_document`) to extract textual blocks, table geometry, and structured form fields.

### 3. Microsoft Word Documents (`.docx`, `.doc`)
* **Extractor**: `DocxExtractor`
* **Mechanisms**: Unpacks `word/document.xml` directly using native Python XML parsing. Preserves Word heading styles (`Heading 1`, `Heading 2`), paragraph structure, bulleted obligation lists, and table grid cells without requiring external binary dependencies (e.g. LibreOffice or pandoc).

### 4. Spreadsheets & Compliance Matrices (`.xlsx`, `.csv`)
* **Extractor**: `ExcelExtractor`
* **Mechanisms**: Reads shared strings and worksheet XML directly from `.xlsx` archives or parses comma-separated `.csv` files into structured 2D table representations.

### 5. Slide Presentations (`.pptx`)
* **Extractor**: `PptxExtractor`
* **Mechanisms**: Iterates through slide XML nodes (`ppt/slides/slide*.xml`), capturing slide headers, bullet hierarchies, and note frames.

### 6. Plain Text & Markdown (`.txt`, `.md`, `.json`)
* **Extractor**: `PlainTextExtractor`
* **Mechanisms**: Decodes UTF-8 text and detects explicit page boundary markers (e.g. `[Page 2]` or `--- Page 2 ---`).

---

## 3. Structural & Semantic Chunking Strategy

Standard naive chunking (e.g., slicing fixed 500 characters) destroys legal clauses, separating conditions from their obligations and losing critical statutory exceptions.

SuitsAI enforces **Structural + Semantic Chunking** in [services/ingestion/parser.py](file:///e:/Downloads/VoyagerAI/services/ingestion/parser.py):

```text
Document
  └── Chapter / Section
        └── Heading
              └── Obligation Sentence
                    ├── Conditions ("if transaction > 50,000")
                    └── Exceptions ("except when customer is central government entity")
```

### Chunk Parameters

| Parameter | Value | Rationale |
| :--- | :--- | :--- |
| **Target Chunk Size** | **350–500 words** (~400–700 tokens) | Optimal context size for Cohere Embed v4 and Claude 3.5 Sonnet attention windows |
| **Sliding Window Overlap** | **40 words** (~10–12%) | Prevents boundary loss across long legal paragraphs |
| **Atomic Clause Preservation** | Enabled | Short clauses $\le 350$ words remain intact in a single chunk |

### Normalized Hierarchical Chunk Schema (`HierarchicalChunk`)

```json
{
  "chunk_id": "CHK-RBI-2026-04-01-01",
  "document_code": "RBI/2026-27/04",
  "text": "[RBI/2026-27/04] Section 4.1 - Enhanced Due Diligence (Page 27):\nRegulated entities shall perform enhanced due diligence for all foreign PEP customers...",
  "section_number": "4.1",
  "heading": "Enhanced Due Diligence",
  "page_number": 27,
  "obligation_type": "MANDATORY",
  "conditions": ["customer_type == 'PEP'"],
  "exceptions": ["except when customer is central government entity"],
  "risk_category": "Financial Crime / AML Risk",
  "jurisdiction": "IN",
  "regulator": "RBI",
  "effective_date": "2026-07-01T00:00:00Z",
  "metadata": {
    "section_number": "4.1",
    "heading": "Enhanced Due Diligence",
    "page_number": 27
  }
}
```

---

## 4. Ingestion API Usage

### Uploading a Document

```http
POST /api/v1/documents/upload HTTP/1.1
Host: localhost:8000
X-Tenant-ID: BANK-TENANT-001
Content-Type: multipart/form-data

file: @circular_rbi_2026.docx
code: RBI/2026-27/04
regulator: Reserve Bank of India
jurisdiction: IN
doc_type: Circular
use_ocr: false
```

### Response

```json
{
  "document_id": "DOC-a1b2c3d4e5f6",
  "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "storage_uri": "s3://compliance-platform-lake/raw/Reserve Bank of India/RBI-2026-27-04/circular_rbi_2026.docx",
  "file_type": "docx",
  "parsed_sections_count": 8,
  "extracted_requirements_count": 14,
  "chunks_count": 18,
  "title": "Master Direction – Know Your Customer (KYC) Direction, 2026"
}
```
