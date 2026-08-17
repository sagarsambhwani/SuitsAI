import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from services.ingestion.extractors import FileExtractorRouter, ExtractedDocumentPayload


class ParsedSection(BaseModel):
    section_number: str
    heading: str
    content: str
    page_number: int = 1
    paragraph_index: int = 0
    order_index: int = 0


class ExtractedRequirement(BaseModel):
    req_code: str
    section_number: str
    obligation_text: str
    obligation_type: str = "MANDATORY"  # MANDATORY, CONDITIONAL, RECOMMENDED, PROHIBITED
    conditions: List[str] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)
    applies_to: List[str] = Field(default_factory=list)
    risk_category: str = "Operational & Compliance Risk"
    penalties_mentioned: bool = False
    page_number: int = 1


class HierarchicalChunk(BaseModel):
    """
    Semantic + Structural chunk preserving hierarchy:
    document -> chapter -> section -> clause
    """
    chunk_id: str
    document_code: str
    text: str
    section_number: str
    heading: str
    page_number: int
    obligation_type: str = "INFORMATIONAL"
    conditions: List[str] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)
    risk_category: str = "Compliance & Governance"
    jurisdiction: str = "GLOBAL"
    regulator: str = "Central Bank"
    effective_date: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    title: str
    code: str
    doc_type: str
    regulator: str
    jurisdiction: str
    publication_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    sections: List[ParsedSection] = Field(default_factory=list)
    extracted_requirements: List[ExtractedRequirement] = Field(default_factory=list)
    chunks: List[HierarchicalChunk] = Field(default_factory=list)
    raw_text: str


class DocumentParser:
    """Intelligent layout-aware document parser and semantic/structural chunker."""

    @classmethod
    def parse_file_bytes(
        cls,
        file_bytes: bytes,
        filename: str,
        default_code: str = "REG-2026",
        default_regulator: str = "Central Bank",
        default_jurisdiction: str = "GLOBAL",
        publication_date: Optional[datetime] = None,
        effective_date: Optional[datetime] = None,
    ) -> ParsedDocument:
        """Extracts text, pages, and tables using FileExtractorRouter, then performs structural compliance parsing."""
        extracted: ExtractedDocumentPayload = FileExtractorRouter.extract(file_bytes, filename)
        
        parsed = cls.parse_regulatory_text(
            text=extracted.full_text,
            default_code=default_code,
            default_regulator=default_regulator,
            default_jurisdiction=default_jurisdiction,
            publication_date=publication_date,
            effective_date=effective_date,
        )
        return parsed

    @classmethod
    def parse_regulatory_text(
        cls,
        text: str,
        default_code: str = "REG-2026",
        default_regulator: str = "Central Bank",
        default_jurisdiction: str = "GLOBAL",
        publication_date: Optional[datetime] = None,
        effective_date: Optional[datetime] = None,
    ) -> ParsedDocument:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        # 1. Detect Document Metadata
        title = lines[0] if lines else "Regulatory Notice"
        doc_type = "Circular"
        if "Master Direction" in text:
            doc_type = "Master Direction"
        elif "Guidance" in text:
            doc_type = "Guidance"
        elif "Act" in text or "Statute" in text:
            doc_type = "Law"

        # 2. Extract Sections with Page & Paragraph Tracking
        section_pattern = re.compile(r"^(?:Section\s+|Article\s+|Clause\s+)?(\d+(?:\.\d+)*)[:\.\-\s]+(.*)$", re.IGNORECASE)
        
        sections: List[ParsedSection] = []
        current_sec_num = "1.0"
        current_heading = "General Overview"
        current_content = []
        order = 0
        current_page = 1

        for line_idx, line in enumerate(lines):
            # Check for page markers like "[Page 2]" or "-- Page 2 --" or "[Slide 2]"
            page_match = re.search(r"\[(?:Page|Slide)\s*(\d+)\]", line, re.IGNORECASE)
            if page_match:
                current_page = int(page_match.group(1))

            match = section_pattern.match(line)
            if match and len(line) < 120 and ("." in match.group(1) or line.startswith(("Section", "Article", "Clause"))):
                if current_content:
                    sections.append(
                        ParsedSection(
                            section_number=current_sec_num,
                            heading=current_heading,
                            content="\n".join(current_content),
                            page_number=current_page,
                            paragraph_index=order,
                            order_index=order,
                        )
                    )
                    order += 1
                current_sec_num = match.group(1)
                current_heading = match.group(2) if match.group(2) else f"Section {current_sec_num}"
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections.append(
                ParsedSection(
                    section_number=current_sec_num,
                    heading=current_heading,
                    content="\n".join(current_content),
                    page_number=current_page,
                    paragraph_index=order,
                    order_index=order,
                )
            )

        # 3. Extract Structured Requirements with Conditions & Exceptions
        requirements: List[ExtractedRequirement] = []
        req_counter = 1

        for sec in sections:
            sentences = re.split(r"(?<=[.!?])\s+", sec.content)
            for sentence in sentences:
                s_lower = sentence.lower()
                if any(kw in s_lower for kw in ["shall", "must", "mandatory", "required to", "is prohibited", "ensure that", "may not"]):
                    # Determine obligation type
                    if "prohibited" in s_lower or "shall not" in s_lower or "must not" in s_lower or "may not" in s_lower:
                        ob_type = "PROHIBITED"
                    elif "if " in s_lower or "in the event of" in s_lower or "where applicable" in s_lower:
                        ob_type = "CONDITIONAL"
                    else:
                        ob_type = "MANDATORY"

                    # Extract Conditions
                    conditions = []
                    if "if " in s_lower:
                        cond_part = re.findall(r"if\s+([^,.;]+)", s_lower)
                        conditions.extend([c.strip() for c in cond_part])
                    if "in the event of" in s_lower:
                        cond_part = re.findall(r"in the event of\s+([^,.;]+)", s_lower)
                        conditions.extend([c.strip() for c in cond_part])

                    # Extract Exceptions
                    exceptions = []
                    if "except" in s_lower or "unless" in s_lower or "exempted from" in s_lower:
                        exc_part = re.findall(r"(?:except|unless|exempted from)\s+([^,.;]+)", s_lower)
                        exceptions.extend([e.strip() for e in exc_part])

                    # Determine risk category
                    risk = "Operational Risk"
                    if "aml" in s_lower or "sanction" in s_lower or "money laundering" in s_lower or "kyc" in s_lower:
                        risk = "Financial Crime / AML Risk"
                    elif "cyber" in s_lower or "security" in s_lower or "encryption" in s_lower or "key" in s_lower or "token" in s_lower:
                        risk = "Cybersecurity & IT Infrastructure"
                    elif "capital" in s_lower or "liquidity" in s_lower or "credit" in s_lower:
                        risk = "Prudential / Financial Risk"

                    req_code = f"REQ-{default_code.replace('/', '-')}-{sec.section_number}-{req_counter:02d}"
                    requirements.append(
                        ExtractedRequirement(
                            req_code=req_code,
                            section_number=sec.section_number,
                            obligation_text=sentence.strip(),
                            obligation_type=ob_type,
                            conditions=conditions,
                            exceptions=exceptions,
                            applies_to=["Commercial Banks", "Digital Lending Entities", "Payment Processors"],
                            risk_category=risk,
                            page_number=sec.page_number,
                        )
                    )
                    req_counter += 1

        # 4. Generate Semantic + Structural Hierarchical Chunks (400-700 tokens windowing)
        chunks = cls.create_hierarchical_chunks(
            sections=sections,
            requirements=requirements,
            doc_code=default_code,
            regulator=default_regulator,
            jurisdiction=default_jurisdiction,
            effective_date=effective_date or datetime.utcnow(),
        )

        return ParsedDocument(
            title=title,
            code=default_code,
            doc_type=doc_type,
            regulator=default_regulator,
            jurisdiction=default_jurisdiction,
            publication_date=publication_date or datetime.utcnow(),
            effective_date=effective_date or datetime.utcnow(),
            sections=sections,
            extracted_requirements=requirements,
            chunks=chunks,
            raw_text=text,
        )

    @classmethod
    def create_hierarchical_chunks(
        cls,
        sections: List[ParsedSection],
        requirements: List[ExtractedRequirement],
        doc_code: str,
        regulator: str,
        jurisdiction: str,
        effective_date: datetime,
        target_words_per_chunk: int = 350,  # ~450-600 tokens
        overlap_words: int = 40,            # ~10-12% overlap
    ) -> List[HierarchicalChunk]:
        """Creates semantic and structural chunks preserving clause and chapter hierarchy."""
        chunks: List[HierarchicalChunk] = []
        chunk_idx = 1

        # Map requirements by section
        reqs_by_sec: Dict[str, List[ExtractedRequirement]] = {}
        for req in requirements:
            reqs_by_sec.setdefault(req.section_number, []).append(req)

        for sec in sections:
            words = sec.content.split()
            sec_reqs = reqs_by_sec.get(sec.section_number, [])
            
            ob_type = sec_reqs[0].obligation_type if sec_reqs else "INFORMATIONAL"
            conditions = [c for r in sec_reqs for c in r.conditions]
            exceptions = [e for r in sec_reqs for e in r.exceptions]
            risk = sec_reqs[0].risk_category if sec_reqs else "Compliance & Governance"

            if len(words) <= target_words_per_chunk:
                # Keep whole section together
                chunk_text = f"[{doc_code}] Section {sec.section_number} - {sec.heading} (Page {sec.page_number}):\n{sec.content}"
                chunks.append(
                    HierarchicalChunk(
                        chunk_id=f"CHK-{doc_code.replace('/', '-')}-{sec.section_number}-{chunk_idx:02d}",
                        document_code=doc_code,
                        text=chunk_text,
                        section_number=sec.section_number,
                        heading=sec.heading,
                        page_number=sec.page_number,
                        obligation_type=ob_type,
                        conditions=conditions,
                        exceptions=exceptions,
                        risk_category=risk,
                        jurisdiction=jurisdiction,
                        regulator=regulator,
                        effective_date=effective_date,
                        metadata={
                            "section_number": sec.section_number,
                            "heading": sec.heading,
                            "page_number": sec.page_number,
                        },
                    )
                )
                chunk_idx += 1
            else:
                # Sliding window with overlap
                start = 0
                part = 1
                while start < len(words):
                    end = min(start + target_words_per_chunk, len(words))
                    window_words = words[start:end]
                    chunk_text = f"[{doc_code}] Section {sec.section_number} (Part {part}) - {sec.heading} (Page {sec.page_number}):\n{' '.join(window_words)}"
                    
                    chunks.append(
                        HierarchicalChunk(
                            chunk_id=f"CHK-{doc_code.replace('/', '-')}-{sec.section_number}-P{part}-{chunk_idx:02d}",
                            document_code=doc_code,
                            text=chunk_text,
                            section_number=sec.section_number,
                            heading=sec.heading,
                            page_number=sec.page_number,
                            obligation_type=ob_type,
                            conditions=conditions,
                            exceptions=exceptions,
                            risk_category=risk,
                            jurisdiction=jurisdiction,
                            regulator=regulator,
                            effective_date=effective_date,
                            metadata={
                                "section_number": sec.section_number,
                                "part": part,
                                "page_number": sec.page_number,
                            },
                        )
                    )
                    chunk_idx += 1
                    part += 1
                    if end == len(words):
                        break
                    start += (target_words_per_chunk - overlap_words)

        return chunks
