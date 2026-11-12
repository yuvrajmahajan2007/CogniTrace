import fitz
import httpx

BASE = "http://127.0.0.1:8000"


def run_phase3_e2e():
    # Inspect current claims so we know which are approved vs rejected
    claims = httpx.get(f"{BASE}/api/claims").json()
    approved = [c for c in claims if c["status"] == "approved"]
    rejected = [c for c in claims if c["status"] == "rejected"]
    assert len(approved) >= 1, "Expected at least 1 approved claim from Phase 2"
    assert len(rejected) >= 1, "Expected at least 1 rejected claim from Phase 2"

    # 1. Generate report
    r_gen = httpx.post(
        f"{BASE}/api/reports/generate",
        json={"title": "CogniTrace E2E Handover Report"},
    )
    assert r_gen.status_code == 200, r_gen.text
    report = r_gen.json()
    report_id = report["id"]
    print(f"1. Generated report id={report_id}, approved_count={report['approved_claims_count']}")
    assert report["approved_claims_count"] == len(approved)

    md = report["markdown_content"]
    # 2. Verify approved claim text and citation appear in report
    for c in approved:
        assert c["claim_text"] in md, f"Approved claim #{c['id']} missing from report!"
        cit = c["citations"][0]
        assert cit["filename"] in md
        assert f"chunk #{cit['evidence_chunk_id']}" in md

    # Verify rejected claim is NOT in confirmed knowledge sections
    for c in rejected:
        assert f"**#{c['id']}**" not in md, f"Rejected claim #{c['id']} leaked into confirmed report!"

    print("2. Verified approved claims + citations included & rejected claims excluded")

    # 3. List & Get report
    r_list = httpx.get(f"{BASE}/api/reports")
    assert r_list.status_code == 200 and any(r["id"] == report_id for r in r_list.json())
    r_get = httpx.get(f"{BASE}/api/reports/{report_id}")
    assert r_get.status_code == 200 and r_get.json()["title"] == "CogniTrace E2E Handover Report"
    print("3. Verified GET /api/reports and GET /api/reports/{id}")

    # 4. Download Markdown
    r_md = httpx.get(f"{BASE}/api/reports/{report_id}/download?format=markdown")
    assert r_md.status_code == 200
    assert "CogniTrace E2E Handover Report" in r_md.text
    print("4. Downloaded Markdown length:", len(r_md.text))

    # 5. Download PDF and open with PyMuPDF to verify readability
    r_pdf = httpx.get(f"{BASE}/api/reports/{report_id}/download?format=pdf")
    assert r_pdf.status_code == 200
    assert r_pdf.headers.get("content-type", "").startswith("application/pdf")
    pdf_doc = fitz.open(stream=r_pdf.content, filetype="pdf")
    assert pdf_doc.page_count >= 1
    pdf_text = "\n".join(page.get_text() for page in pdf_doc)
    pdf_doc.close()
    assert "CogniTrace E2E Handover Report" in pdf_text
    assert approved[0]["citations"][0]["filename"] in pdf_text
    print(f"5. Downloaded & parsed PDF ({len(r_pdf.content)} bytes, {pdf_text.splitlines()[0]})")
    print(f"PRE_RESTART_REPORT_OK report_id={report_id}")


if __name__ == "__main__":
    run_phase3_e2e()
