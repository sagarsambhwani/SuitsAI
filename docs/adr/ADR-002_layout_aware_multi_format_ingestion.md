# ADR-002: Layout-Aware Multi-Format Parsing vs. Flat Text Ingestion

* **Status**: Accepted
* **Date**: 2026-08-17
* **Deciders**: Ingestion Engineering, Document Processing Team

---

## Context & Problem Statement
Banking circulars and internal bank policies are published in heterogeneous formats: digital PDFs, scanned/physical circulars, Word files (`.docx`), Excel spreadsheets (`.xlsx`), and presentation slide decks (`.pptx`). Flattening these files to plain unstructured text strips table headers, destroys paragraph hierarchies, and breaks clause references.

## Decision
We implement a **Layout-Aware Multi-Format Parser framework** via `FileExtractorRouter`:
* **PDF (Digital)**: Native page-by-page coordinate extraction.
* **Scanned PDFs / Images**: AWS Textract OCR integration with table detection.
* **Microsoft Word (`.docx`)**: Native XML unpacking (`word/document.xml`) preserving heading levels, lists, and tables without external binary dependencies.
* **Excel / CSV (`.xlsx`, `.csv`)**: Structured 2D table extraction for compliance matrices and rule thresholds.
* **PowerPoint (`.pptx`)**: Slide-by-slide text frame parsing.

## Consequences
### Positive
* High-fidelity preservation of tables, sections, clauses, and page coordinates.
* Sentence-level claim lineage can accurately point to exact pages and section numbers.
* Zero dependency on heavy external tools (e.g. LibreOffice).

### Negative
* Requires handling format-specific XML schemas and potential schema drift across office formats.
