import time
import fitz
import httpx

BASE = "http://127.0.0.1:8000"


def run_phase2_e2e():
    # 1. Verify no unsupported claims generated on empty DB
    r = httpx.post(f"{BASE}/api/claims/generate", json={"use_gemini": False})
    assert r.status_code == 200, r.text
    gen0 = r.json()
    print("1. Empty DB generate:", gen0)
    assert gen0["generated_count"] == 0

    # 2. Create sample PDF with realistic project handover notes & a contradiction
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text(
        (72, 72),
        "\n".join(
            [
                "Project Architecture & Status Handover",
                "We decided to use FastAPI and SQLite for the backend architecture.",
                "The user authentication module is completed and verified in staging.",
                "The user authentication module is pending final security review.",
                "Blocker: Redis cache cluster is blocked by firewall approval.",
                "The export service depends on python-docx and PyMuPDF libraries.",
                "TODO: Add rate limiting to public endpoints before launch.",
            ]
        ),
        fontsize=11,
    )
    pdf_bytes = doc.tobytes()
    doc.close()

    # Upload PDF
    r = httpx.post(
        f"{BASE}/api/files/upload",
        files={"files": ("handover_notes.pdf", pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    file_id = r.json()["uploaded"][0]["id"]
    print("2. Uploaded PDF file_id:", file_id)

    # Wait for background parsing
    rf = None
    for _ in range(25):
        rf = httpx.get(f"{BASE}/api/files/{file_id}")
        if rf.json()["status"] == "completed":
            break
        time.sleep(0.3)
    assert rf is not None and rf.json()["status"] == "completed", rf.json()

    # Verify Phase 1 Evidence Explorer endpoint still works
    rc = httpx.get(f"{BASE}/api/files/{file_id}/content")
    assert rc.status_code == 200 and len(rc.json()) >= 1
    print("3. Phase 1 Evidence Explorer chunks:", len(rc.json()))

    # 3. Generate claims
    rg = httpx.post(f"{BASE}/api/claims/generate", json={"use_gemini": False})
    assert rg.status_code == 200, rg.text
    print("4. Generated claims response:", rg.json())
    assert rg.json()["generated_count"] >= 5

    # 4. Retrieve claims & verify traceable citations
    claims = httpx.get(f"{BASE}/api/claims").json()
    print("5. Total claims retrieved:", len(claims))
    for c in claims:
        assert len(c["citations"]) >= 1, f"Claim {c['id']} missing citation!"
        cit = c["citations"][0]
        assert cit["filename"] == "handover_notes.pdf"
        assert cit["evidence_chunk_id"] is not None
        assert cit["page_number"] == 1
        assert len(cit["excerpt"]) > 0

    # Check single claim detail
    c0 = httpx.get(f"{BASE}/api/claims/{claims[0]['id']}").json()
    print(
        "6. Sample claim detail citation:",
        c0["citations"][0]["filename"],
        "page",
        c0["citations"][0]["page_number"],
    )

    # Check conflicts
    conflicts = httpx.get(f"{BASE}/api/claims/conflicts").json()
    print("7. Conflicts detected:", len(conflicts))
    assert len(conflicts) >= 1, "Expected contradiction between completed and pending authentication module!"

    # 5. Approve claim 0, Reject claim 1, Edit claim 2
    r_app = httpx.patch(
        f"{BASE}/api/claims/{claims[0]['id']}",
        json={"status": "approved", "comment": "Verified in staging"},
    )
    assert r_app.status_code == 200 and r_app.json()["status"] == "approved"

    r_rej = httpx.patch(
        f"{BASE}/api/claims/{claims[1]['id']}",
        json={"status": "rejected", "comment": "Superseded by newer note"},
    )
    assert r_rej.status_code == 200 and r_rej.json()["status"] == "rejected"

    r_edt = httpx.patch(
        f"{BASE}/api/claims/{claims[2]['id']}",
        json={
            "claim_text": claims[2]["claim_text"] + " (Edited by reviewer)",
            "comment": "Clarified scope",
        },
    )
    assert r_edt.status_code == 200 and "(Edited by reviewer)" in r_edt.json()["claim_text"]

    stats = httpx.get(f"{BASE}/api/claims/stats").json()
    print("8. Stats after review:", stats)
    assert stats["approved_claims"] == 1
    assert stats["rejected_claims"] == 1
    print(
        "PRE_RESTART_OK",
        f"file_id={file_id}",
        f"approved_id={claims[0]['id']}",
        f"rejected_id={claims[1]['id']}",
        f"edited_id={claims[2]['id']}",
    )


if __name__ == "__main__":
    run_phase2_e2e()
