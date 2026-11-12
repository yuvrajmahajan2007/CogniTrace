import json
import httpx

BASE = "http://127.0.0.1:8000"


def run_phase4_e2e():
    # 0. Snapshot existing Phase 1-3 data
    pre_files = httpx.get(f"{BASE}/api/files").json()
    pre_stats = httpx.get(f"{BASE}/api/claims/stats").json()
    pre_reports = httpx.get(f"{BASE}/api/reports").json()
    assert len(pre_files) >= 1 and pre_stats["approved_claims"] == 6 and len(pre_reports) >= 5
    print("0. Existing Phase 1-3 data intact:", pre_stats)

    # 1. Git Activity Import (TXT + JSON + invalid + duplicate file + overlapping commit)
    git_txt = (
        "commit a1b2c3d4e5f6\n"
        "Author: Priya Sharma <priya@example.com>\n"
        "Date: 2026-11-10 14:30:00\n"
        "feat: Implemented JWT authentication middleware for API routes\n"
        "Files: backend/app/auth.py, backend/app/main.py\n\n"
        "commit f6e5d4c3b2a1\n"
        "Author: Rohan Verma <rohan@example.com>\n"
        "Date: 2026-11-11 09:15:00\n"
        "TODO: Add PostgreSQL migration script before production release\n"
    ).encode("utf-8")

    r_git_bad = httpx.post(
        f"{BASE}/api/imports/git",
        files={"file": ("bad_git.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r_git_bad.status_code == 400

    r_git1 = httpx.post(
        f"{BASE}/api/imports/git",
        files={"file": ("git_history.txt", git_txt, "text/plain")},
    )
    assert r_git1.status_code == 200, r_git1.text
    g1 = r_git1.json()
    assert g1["imported_count"] == 2 and g1["skipped_duplicates"] == 0
    print("1a. Git TXT import OK:", g1)

    # Exact duplicate file -> 409
    r_git_dup = httpx.post(
        f"{BASE}/api/imports/git",
        files={"file": ("git_history.txt", git_txt, "text/plain")},
    )
    assert r_git_dup.status_code == 409
    print("1b. Git exact duplicate file rejected (409)")

    # Overlapping commit in JSON -> 1 skipped, 1 new
    git_json = json.dumps(
        [
            {
                "commit_hash": "a1b2c3d4e5f6",
                "author": "Priya Sharma <priya@example.com>",
                "date": "2026-11-10 14:30:00",
                "message": "Implemented JWT authentication middleware for API routes",
                "changed_files": ["backend/app/auth.py", "backend/app/main.py"],
            },
            {
                "commit_hash": "998877665544",
                "author": "Priya Sharma",
                "date": "2026-11-12 11:00:00",
                "message": "We decided to use Redis for session rate limiting",
                "changed_files": ["backend/app/ratelimit.py"],
            },
        ]
    ).encode("utf-8")
    # Note: the first commit text formatting matches if prefix matches; even if different text, let's test overlapping exact JSON re-import
    r_git2 = httpx.post(
        f"{BASE}/api/imports/git",
        files={"file": ("git_extra.json", git_json, "application/json")},
    )
    assert r_git2.status_code == 200, r_git2.text
    print("1c. Git JSON import OK:", r_git2.json())

    # 2. Chat Export Import (TXT + JSON + invalid)
    chat_txt = (
        "[2026-11-11 16:00] Ananya: The billing webhook handler is completed and verified in staging.\n"
        "[2026-11-11 16:05] Vikram: Blocker: Payment gateway sandbox keys are blocked by vendor approval.\n"
    ).encode("utf-8")

    r_chat_bad = httpx.post(
        f"{BASE}/api/imports/chat",
        files={"file": ("bad.json", b"{not valid json", "application/json")},
    )
    assert r_chat_bad.status_code == 400

    r_chat = httpx.post(
        f"{BASE}/api/imports/chat",
        files={"file": ("team_chat.txt", chat_txt, "text/plain")},
    )
    assert r_chat.status_code == 200, r_chat.text
    c_res = r_chat.json()
    assert c_res["imported_count"] == 2
    print("2. Chat TXT import OK:", c_res)

    # Verify chat chunk metadata
    chat_chunks = httpx.get(f"{BASE}/api/files/{c_res['file_id']}/content").json()
    assert chat_chunks[0]["author"] == "Ananya"
    assert chat_chunks[0]["record_timestamp"] == "2026-11-11 16:00"
    assert chat_chunks[0]["source_type"] == "chat"

    # 3. Task Records Import (CSV + cross-source contradiction with Chat!)
    tasks_csv = (
        "task_id,title,description,status,assignee,priority,due_date\n"
        "TASK-101,Billing webhook handler,Complete Stripe webhook signature verification,open,Ananya,high,2026-11-20\n"
        "TASK-102,Database backup automation,Automated nightly SQLite snapshot,done,Rohan,medium,2026-11-10\n"
    ).encode("utf-8")

    r_task = httpx.post(
        f"{BASE}/api/imports/tasks",
        files={"file": ("sprint_tasks.csv", tasks_csv, "text/csv")},
    )
    assert r_task.status_code == 200, r_task.text
    t_res = r_task.json()
    assert t_res["imported_count"] == 2
    print("3. Task CSV import OK:", t_res)

    task_chunks = httpx.get(f"{BASE}/api/files/{t_res['file_id']}/content").json()
    assert task_chunks[0]["record_id"] == "TASK-101"
    assert task_chunks[0]["source_type"] == "task"

    # Overlapping task record in JSON -> TASK-101 should be skipped as duplicate!
    tasks_json = json.dumps(
        [
            {
                "task_id": "TASK-101",
                "title": "Billing webhook handler",
                "description": "Complete Stripe webhook signature verification",
                "status": "open",
                "assignee": "Ananya",
                "priority": "high",
                "due_date": "2026-11-20",
            },
            {
                "task_id": "TASK-103",
                "title": "API docs refresh",
                "description": "Update OpenAPI examples for handover",
                "status": "pending",
                "assignee": "Priya",
                "priority": "low",
            },
        ]
    ).encode("utf-8")
    r_task2 = httpx.post(
        f"{BASE}/api/imports/tasks",
        files={"file": ("sprint_tasks_extra.json", tasks_json, "application/json")},
    )
    assert r_task2.status_code == 200, r_task2.text
    t2 = r_task2.json()
    assert t2["imported_count"] == 1 and t2["skipped_duplicates"] == 1
    print("3b. Overlapping Task record deduplicated:", t2)

    # 4. Generate claims from imported sources & check cross-source contradiction
    r_gen = httpx.post(f"{BASE}/api/claims/generate", json={"use_gemini": False})
    assert r_gen.status_code == 200, r_gen.text
    gen = r_gen.json()
    print("4. Claim generation after multi-source import:", gen)
    assert gen["generated_count"] >= 6

    # Verify all new claims start as pending & existing approved count remains 6
    post_stats = httpx.get(f"{BASE}/api/claims/stats").json()
    assert post_stats["approved_claims"] == 6, "New claims must NOT be auto-approved!"
    assert post_stats["total_conflicts"] >= 3, "Expected cross-source contradiction between Chat and Task!"

    # Verify cross-source contradiction between team_chat.txt and sprint_tasks.csv
    conflicts = httpx.get(f"{BASE}/api/claims/conflicts").json()
    cross = [
        fl for fl in conflicts
        if fl["conflict_type"] == "contradiction"
        and fl["claim_a"] and fl["claim_b"]
        and {fl["claim_a"]["source_filename"], fl["claim_b"]["source_filename"]} == {"team_chat.txt", "sprint_tasks.csv"}
    ]
    assert len(cross) >= 1, f"Expected cross-source contradiction between team_chat.txt and sprint_tasks.csv! Conflicts: {conflicts}"
    print("5. Cross-source contradiction verified:", cross[0]["description"])

    # Verify GET /api/imports
    imports_list = httpx.get(f"{BASE}/api/imports").json()
    assert len(imports_list) == 5
    print("6. GET /api/imports count:", len(imports_list))
    print("PHASE4_E2E_ALL_PASSED")


if __name__ == "__main__":
    run_phase4_e2e()
