import os
import re
import textwrap
from datetime import datetime
from typing import Dict, List, Tuple
import fitz  # PyMuPDF
from sqlalchemy.orm import Session, joinedload
from .. import models
from ..core.config import settings

EMPTY_SECTION_MESSAGE = "No verified information available in the reviewed evidence."

INCOMPLETE_ENDINGS = (
    ",", ";", ":", "-", "—", "and", "or", "of", "to", "for", "with", "in", "on", "by", "from", "the", "a", "an", "schema"
)


def _is_incomplete_fragment(text: str) -> bool:
    s = (text or "").strip()
    if len(s) < 30:
        return True
    # Starts lowercase -> mid-sentence fragment
    if s[0].islower():
        return True
    # Ends with trailing punctuation or hanging word
    lower = s.lower()
    if lower.endswith((",", ";", ":", "-")):
        return True
    last_word = re.sub(r"[^a-zA-Z]+$", "", lower.split()[-1]) if lower.split() else ""
    if last_word in {"and", "or", "of", "to", "for", "with", "in", "on", "by", "from", "the", "a", "an", "schema"}:
        return True
    # All-uppercase short heading fragment
    if s.isupper() and len(s) < 60:
        return True
    return False


def _format_readable_claim(text: str) -> Tuple[str, bool]:
    """
    Improve readability without altering meaning or inventing information.
    Returns (display_text, is_incomplete).
    """
    s = (text or "").strip()
    incomplete = _is_incomplete_fragment(s)
    # Strip trailing comma/semicolon for cleaner presentation while keeping original meaning
    display = re.sub(r"[,;:\s]+$", "", s).strip()
    if not display:
        display = s
    return display, incomplete


def _determine_implementation_status(claim: models.Claim, is_incomplete: bool) -> str:
    """
    Accurately classify implementation status without assuming proposals are implemented.
    Categories:
      - Proposed in source documents
      - Implemented and verified in current application
      - Pending implementation
      - Not verified
    """
    text_lower = (claim.claim_text or "").lower()
    src_lower = (claim.source_filename or "").lower()

    if claim.insufficient_evidence or is_incomplete:
        if any(kw in text_lower for kw in ("pending", "planned", "todo", "fixme")):
            return "Pending implementation"
        if any(kw in src_lower for kw in ("submission", "proposal", "plan", "spec")):
            return "Proposed in source documents (Not verified)"
        return "Not verified"

    if claim.claim_type in (
        models.ClaimType.pending_feature,
        models.ClaimType.todo_fixme,
        models.ClaimType.blocker_risk,
    ):
        return "Pending implementation"

    if claim.claim_type == models.ClaimType.completed_feature:
        # Only mark implemented & verified if not phrased as a future/proposed concept
        if any(kw in text_lower for kw in ("planned", "will ", "would ", "proposal", "proposed")):
            return "Proposed in source documents"
        return "Implemented and verified in current application"

    if claim.claim_type in (
        models.ClaimType.architecture_decision,
        models.ClaimType.technology,
        models.ClaimType.project_decision,
        models.ClaimType.dependency,
    ):
        if any(kw in text_lower for kw in ("verified in", "currently running", "deployed to production")):
            return "Implemented and verified in current application"
        return "Proposed in source documents"

    return "Not verified"


def _format_citation(cit: models.Citation) -> str:
    loc_parts = [f"chunk #{cit.evidence_chunk_id}"]
    if cit.page_number is not None:
        loc_parts.append(f"Page {cit.page_number}")
    if cit.line_number is not None:
        loc_parts.append(f"Line {cit.line_number}")
    if cit.json_path:
        loc_parts.append(f"Path {cit.json_path}")
    return f"{cit.filename} ({', '.join(loc_parts)})"


def _sanitize_pdf_text(text: str) -> str:
    """Normalize characters so built-in PDF Base14 fonts render cleanly."""
    replacements = {
        "\u2014": "--",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "*",
        "\u00a0": " ",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _render_claim_entries(
    claims: List[models.Claim],
    md_lines: List[str],
    pdf_items: List[dict],
) -> None:
    if not claims:
        md_lines.append(f"*{EMPTY_SECTION_MESSAGE}*")
        md_lines.append("")
        pdf_items.append({"text": EMPTY_SECTION_MESSAGE, "citations": [], "muted": True})
        return

    for c in claims:
        display_text, incomplete = _format_readable_claim(c.claim_text)
        impl_status = _determine_implementation_status(c, incomplete)
        review_status = c.status.value.capitalize() if hasattr(c.status, "value") else str(c.status).capitalize()

        context_note = " [Requires additional context]" if (incomplete or c.insufficient_evidence) else ""
        md_lines.append(f"- **Claim #{c.id}**{context_note}: {display_text}")
        md_lines.append(
            f"  - *Review Status:* {review_status} | *Implementation Status:* {impl_status}"
        )

        cits = [_format_citation(cit) for cit in c.citations]
        for cit_str in cits:
            md_lines.append(f"  - *Citation:* `{cit_str}`")

        pdf_cits = [
            f"Review Status: {review_status} | Implementation Status: {impl_status}"
        ] + [f"Citation: {cs}" for cs in cits]

        pdf_items.append(
            {
                "text": f"Claim #{c.id}{context_note}: {display_text}",
                "citations": pdf_cits,
            }
        )
    md_lines.append("")


def _build_structured_sections(
    approved_claims: List[models.Claim],
    unresolved_conflicts: List[models.ConflictFlag],
    parsed_files: List[models.UploadedFile],
    total_claims: int,
    pending_count: int,
    rejected_count: int,
    recent_reviews: List[models.ReviewHistory],
    generated_at: datetime,
    title: str,
) -> Tuple[str, List[dict]]:
    by_type: Dict[models.ClaimType, List[models.Claim]] = {}
    for claim in approved_claims:
        by_type.setdefault(claim.claim_type, []).append(claim)

    tech_claims = by_type.get(models.ClaimType.technology, [])
    arch_claims = by_type.get(models.ClaimType.architecture_decision, [])
    decision_claims = by_type.get(models.ClaimType.project_decision, [])
    implemented_claims = by_type.get(models.ClaimType.completed_feature, [])
    planned_claims = (
        by_type.get(models.ClaimType.pending_feature, [])
        + by_type.get(models.ClaimType.todo_fixme, [])
    )
    risk_dep_claims = (
        by_type.get(models.ClaimType.blocker_risk, [])
        + by_type.get(models.ClaimType.dependency, [])
    )

    incomplete_approved = [
        c for c in approved_claims if _is_incomplete_fragment(c.claim_text) or c.insufficient_evidence
    ]

    md_lines: List[str] = [
        f"# {title}",
        "",
        f"- **Generated:** {generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"- **Source Documents Parsed:** {len(parsed_files)}",
        f"- **Approved Claims Included:** {len(approved_claims)} of {total_claims} total extracted claims",
        f"- **Excluded Claims:** {pending_count} pending review, {rejected_count} rejected",
        f"- **Unresolved Evidence & Conflict Flags:** {len(unresolved_conflicts)}",
        "",
    ]

    pdf_sections: List[dict] = []

    # 1. Executive Summary
    md_lines.extend(["## 1. Executive Summary", ""])
    if not approved_claims:
        exec_summary = (
            "No human-approved claims are currently available to include as confirmed handover knowledge. "
            f"{pending_count} candidate claim(s) remain pending human review and {rejected_count} were rejected."
        )
    else:
        exec_summary = (
            f"This report consolidates {len(approved_claims)} human-approved claim(s) extracted from "
            f"{len(parsed_files)} verified source document(s). "
            f"To prevent unverified assumptions, {pending_count} pending claim(s) and {rejected_count} rejected claim(s) "
            f"are excluded from confirmed sections. "
            f"Note: {len(incomplete_approved)} approved claim(s) are extracted fragments requiring additional context, "
            f"and {len(unresolved_conflicts)} unresolved evidence/conflict flag(s) remain open for reviewer attention."
        )
    md_lines.extend([exec_summary, ""])
    pdf_sections.append(
        {
            "heading": "1. Executive Summary",
            "items": [{"text": exec_summary, "citations": []}],
        }
    )

    # 2. Project Overview
    md_lines.extend(["## 2. Project Overview", ""])
    overview_points = [
        f"Source Corpus: {len(parsed_files)} parsed document(s) indexed into traceable evidence chunks.",
        f"Extraction & Grounding Policy: Every claim is anchored to an existing SQLite EvidenceChunk (filename, chunk ID, and page/line reference).",
        f"Category Breakdown of Approved Claims: {len(tech_claims)} Technologies, {len(arch_claims)} Architecture Decisions, {len(decision_claims)} Project Decisions, {len(implemented_claims)} Implemented Features, {len(planned_claims)} Planned Features, {len(risk_dep_claims)} Risks/Dependencies.",
    ]
    for pt in overview_points:
        md_lines.append(f"- {pt}")
    md_lines.append("")
    pdf_sections.append(
        {
            "heading": "2. Project Overview",
            "items": [{"text": pt, "citations": []} for pt in overview_points],
        }
    )

    # 3. Technologies & Frameworks
    md_lines.extend(["## 3. Technologies & Frameworks", ""])
    tech_pdf: List[dict] = []
    _render_claim_entries(tech_claims, md_lines, tech_pdf)
    pdf_sections.append({"heading": "3. Technologies & Frameworks", "items": tech_pdf})

    # 4. Architecture & Design (Architecture Decisions + Project Decisions)
    md_lines.extend(["## 4. Architecture & Design", ""])
    arch_combined = arch_claims + decision_claims
    arch_pdf: List[dict] = []
    if arch_claims:
        md_lines.extend(["### Architecture & Design Decisions", ""])
        _render_claim_entries(arch_claims, md_lines, arch_pdf)
    if decision_claims:
        md_lines.extend(["### Project Decisions", ""])
        _render_claim_entries(decision_claims, md_lines, arch_pdf)
    if not arch_combined:
        _render_claim_entries([], md_lines, arch_pdf)
    pdf_sections.append({"heading": "4. Architecture & Design", "items": arch_pdf})

    # 5. Implemented Features
    md_lines.extend(["## 5. Implemented Features", ""])
    impl_pdf: List[dict] = []
    _render_claim_entries(implemented_claims, md_lines, impl_pdf)
    pdf_sections.append({"heading": "5. Implemented Features", "items": impl_pdf})

    # 6. Planned Features
    md_lines.extend(["## 6. Planned Features", ""])
    planned_pdf: List[dict] = []
    _render_claim_entries(planned_claims, md_lines, planned_pdf)
    pdf_sections.append({"heading": "6. Planned Features", "items": planned_pdf})

    # 7. Risks, Dependencies & Open Issues
    md_lines.extend(["## 7. Risks, Dependencies & Open Issues", ""])
    risk_pdf: List[dict] = []
    _render_claim_entries(risk_dep_claims, md_lines, risk_pdf)
    pdf_sections.append({"heading": "7. Risks, Dependencies & Open Issues", "items": risk_pdf})

    # 8. Unresolved Evidence and Conflicts
    md_lines.extend(["## 8. Unresolved Evidence and Conflicts", ""])
    conflict_pdf: List[dict] = []

    if not unresolved_conflicts and not incomplete_approved:
        md_lines.extend([f"*{EMPTY_SECTION_MESSAGE}*", ""])
        conflict_pdf.append({"text": EMPTY_SECTION_MESSAGE, "citations": [], "muted": True})
    else:
        for flag in unresolved_conflicts:
            if flag.conflict_type == "contradiction":
                label = "Potential Contradiction"
                explanation = (
                    "Two source statements appear to conflict on implementation or technical state. "
                    "Human review is required to confirm which statement reflects current reality."
                )
            elif flag.conflict_type == "review_warning":
                label = "Review Warning"
                explanation = (
                    "Two source statements exhibit potential status divergence or partial topic overlap. "
                    "Human review is recommended to verify whether these describe distinct work items."
                )
            else:
                label = "Insufficient Supporting Evidence"
                explanation = (
                    "The extracted statement is brief, ambiguous, or lacks complete surrounding context "
                    "and should be verified against the original source page before relying on it."
                )

            md_lines.append(f"- **[{label}]** {flag.description}")
            md_lines.append(f"  - *Why Flagged:* {explanation}")
            sub_cits = [f"Why Flagged: {explanation}"]
            if flag.claim_a:
                ca_line = f"Claim #{flag.claim_a.id} ({flag.claim_a.source_filename}, status: {flag.claim_a.status.value}): {flag.claim_a.claim_text}"
                md_lines.append(f"  - {ca_line}")
                sub_cits.append(ca_line)
            if flag.claim_b:
                cb_line = f"Claim #{flag.claim_b.id} ({flag.claim_b.source_filename}, status: {flag.claim_b.status.value}): {flag.claim_b.claim_text}"
                md_lines.append(f"  - {cb_line}")
                sub_cits.append(cb_line)
            conflict_pdf.append({"text": f"[{label}] {flag.description}", "citations": sub_cits})

        if incomplete_approved:
            md_lines.append("")
            md_lines.append("### Approved Claims Flagged as Fragmented / Requiring Context")
            md_lines.append("")
            for c in incomplete_approved:
                cit_summary = _format_citation(c.citations[0]) if c.citations else c.source_filename
                note = (
                    f"Claim #{c.id} was approved by the reviewer but is an incomplete sentence fragment "
                    f"from `{cit_summary}`. Consult the source chunk for full context."
                )
                md_lines.append(f"- {note}")
                conflict_pdf.append({"text": note, "citations": []})
        md_lines.append("")

    pdf_sections.append({"heading": "8. Unresolved Evidence and Conflicts", "items": conflict_pdf})

    # 9. Source Documents
    md_lines.extend(["## 9. Source Documents", ""])
    source_pdf: List[dict] = []
    if not parsed_files:
        md_lines.extend([f"*{EMPTY_SECTION_MESSAGE}*", ""])
        source_pdf.append({"text": EMPTY_SECTION_MESSAGE, "citations": [], "muted": True})
    else:
        for f in parsed_files:
            line = (
                f"{f.filename} ({f.size_bytes} bytes, parsed status: {f.status.value}, "
                f"uploaded {f.uploaded_at.strftime('%Y-%m-%d %H:%M UTC')})"
            )
            md_lines.append(f"- {line}")
            source_pdf.append({"text": line, "citations": []})
        md_lines.append("")
    pdf_sections.append({"heading": "9. Source Documents", "items": source_pdf})

    # 10. Reviewer Approval Summary
    md_lines.extend(["## 10. Reviewer Approval Summary", ""])
    review_pdf: List[dict] = []
    summary_bullets = [
        f"Total Candidate Claims Extracted: {total_claims}",
        f"Approved (Included in Confirmed Knowledge): {len(approved_claims)}",
        f"Pending Human Review (Excluded): {pending_count}",
        f"Rejected by Reviewer (Excluded): {rejected_count}",
    ]
    for b in summary_bullets:
        md_lines.append(f"- {b}")
        review_pdf.append({"text": b, "citations": []})

    if recent_reviews:
        md_lines.append("")
        md_lines.append("### Recent Reviewer Decisions")
        md_lines.append("")
        for rh in recent_reviews[:10]:
            comment_str = f" -- Comment: \"{rh.comment}\"" if rh.comment else ""
            rline = (
                f"Claim #{rh.claim_id}: {rh.action} ({rh.previous_status} -> {rh.new_status}) "
                f"at {rh.reviewed_at.strftime('%Y-%m-%d %H:%M UTC')}{comment_str}"
            )
            md_lines.append(f"- {rline}")
            review_pdf.append({"text": rline, "citations": []})
    md_lines.append("")
    pdf_sections.append({"heading": "10. Reviewer Approval Summary", "items": review_pdf})

    return "\n".join(md_lines), pdf_sections


def _render_pdf(
    pdf_path: str,
    title: str,
    generated_at: datetime,
    stats_line: str,
    sections: List[dict],
) -> None:
    doc = fitz.open()
    page_w, page_h = 595, 842  # A4
    margin_x = 48
    bottom_limit = page_h - 54

    page = doc.new_page(width=page_w, height=page_h)

    # Top Navy Banner on Page 1
    banner_rect = fitz.Rect(0, 0, page_w, 86)
    page.draw_rect(banner_rect, color=(0.06, 0.09, 0.16), fill=(0.06, 0.09, 0.16))
    page.insert_text(
        (margin_x, 38),
        _sanitize_pdf_text(title),
        fontsize=17,
        fontname="helv",
        color=(1, 1, 1),
    )
    page.insert_text(
        (margin_x, 58),
        _sanitize_pdf_text(
            f"Generated {generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}  |  {stats_line}"
        ),
        fontsize=9,
        fontname="helv",
        color=(0.78, 0.82, 0.90),
    )

    y = 112

    def ensure_space(needed: float):
        nonlocal page, y
        if y + needed > bottom_limit:
            page = doc.new_page(width=page_w, height=page_h)
            y = 52

    for section in sections:
        ensure_space(42)
        page.insert_text(
            (margin_x, y),
            _sanitize_pdf_text(section["heading"]),
            fontsize=12.5,
            fontname="helv",
            color=(0.06, 0.09, 0.16),
        )
        y += 5
        page.draw_line(
            fitz.Point(margin_x, y),
            fitz.Point(page_w - margin_x, y),
            color=(0.82, 0.85, 0.90),
            width=0.8,
        )
        y += 16

        for item in section["items"]:
            wrapped_main = textwrap.wrap(
                _sanitize_pdf_text(item["text"]),
                width=84,
                break_long_words=True,
            ) or [""]
            ensure_space(len(wrapped_main) * 14 + 10)
            text_color = (0.45, 0.50, 0.58) if item.get("muted") else (0.12, 0.16, 0.23)

            for idx, line in enumerate(wrapped_main):
                prefix = "- " if idx == 0 and not item.get("muted") else ("  " if not item.get("muted") else "")
                page.insert_text(
                    (margin_x, y),
                    prefix + line,
                    fontsize=10,
                    fontname="helv",
                    color=text_color,
                )
                y += 13.5

            for cit in item.get("citations", []):
                wrapped_cit = textwrap.wrap(
                    _sanitize_pdf_text(cit),
                    width=86,
                    break_long_words=True,
                )
                ensure_space(len(wrapped_cit) * 12 + 4)
                for cline in wrapped_cit:
                    page.insert_text(
                        (margin_x + 14, y),
                        cline,
                        fontsize=8.5,
                        fontname="helv",
                        color=(0.38, 0.44, 0.53),
                    )
                    y += 11.5
            y += 5

        y += 8

    total_pages = doc.page_count
    for idx, p in enumerate(doc, start=1):
        footer = f"CogniTrace Handover Report  --  Page {idx} of {total_pages}"
        p.insert_text(
            (margin_x, page_h - 26),
            footer,
            fontsize=8,
            fontname="helv",
            color=(0.50, 0.55, 0.62),
        )

    doc.save(pdf_path)
    doc.close()


def generate_handover_report(db: Session, title: str = "CogniTrace Project Handover Report") -> models.HandoverReport:
    clean_title = (title or "").strip() or "CogniTrace Project Handover Report"
    generated_at = datetime.utcnow()

    approved_claims = (
        db.query(models.Claim)
        .filter(models.Claim.status == models.ClaimStatus.approved)
        .options(joinedload(models.Claim.citations))
        .order_by(models.Claim.id.asc())
        .all()
    )

    total_claims = db.query(models.Claim).count()
    pending_count = (
        db.query(models.Claim)
        .filter(models.Claim.status == models.ClaimStatus.pending)
        .count()
    )
    rejected_count = (
        db.query(models.Claim)
        .filter(models.Claim.status == models.ClaimStatus.rejected)
        .count()
    )

    unresolved_conflicts = (
        db.query(models.ConflictFlag)
        .filter(models.ConflictFlag.resolved == False)  # noqa: E712
        .options(
            joinedload(models.ConflictFlag.claim_a),
            joinedload(models.ConflictFlag.claim_b),
        )
        .order_by(models.ConflictFlag.id.asc())
        .all()
    )

    parsed_files = (
        db.query(models.UploadedFile)
        .filter(models.UploadedFile.status == models.ParsingStatus.completed)
        .order_by(models.UploadedFile.uploaded_at.asc())
        .all()
    )

    recent_reviews = (
        db.query(models.ReviewHistory)
        .order_by(models.ReviewHistory.reviewed_at.desc())
        .limit(10)
        .all()
    )

    markdown_content, pdf_sections = _build_structured_sections(
        approved_claims=approved_claims,
        unresolved_conflicts=unresolved_conflicts,
        parsed_files=parsed_files,
        total_claims=total_claims,
        pending_count=pending_count,
        rejected_count=rejected_count,
        recent_reviews=recent_reviews,
        generated_at=generated_at,
        title=clean_title,
    )

    os.makedirs(settings.REPORTS_DIR, exist_ok=True)
    stamp = generated_at.strftime("%Y%m%d_%H%M%S_%f")
    md_path = os.path.join(settings.REPORTS_DIR, f"handover_report_{stamp}.md")
    pdf_path = os.path.join(settings.REPORTS_DIR, f"handover_report_{stamp}.pdf")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    stats_line = (
        f"{len(approved_claims)} Approved Claims  |  "
        f"{len(parsed_files)} Source Docs  |  "
        f"{len(unresolved_conflicts)} Open Flags"
    )
    _render_pdf(
        pdf_path=pdf_path,
        title=clean_title,
        generated_at=generated_at,
        stats_line=stats_line,
        sections=pdf_sections,
    )

    report = models.HandoverReport(
        title=clean_title,
        approved_claims_count=len(approved_claims),
        conflicts_count=len(unresolved_conflicts),
        source_files_count=len(parsed_files),
        markdown_content=markdown_content,
        markdown_path=md_path,
        pdf_path=pdf_path,
        created_at=generated_at,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
