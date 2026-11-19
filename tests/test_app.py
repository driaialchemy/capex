"""The presentation page loads, runs a review, and shows a refused sign-off."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from capex.llm import repo_root

APP = repo_root() / "app.py"


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEX_LLM_MODE", "offline")
    monkeypatch.setenv("CAPEX_KILL_SWITCH", "0")
    monkeypatch.setenv("CAPEX_RUNS_ROOT", str(tmp_path))


def _page(at: AppTest) -> str:
    chunks = []
    for collection in (at.markdown, at.success, at.error, at.warning, at.info):
        for item in collection:
            chunks.append(str(item.value))
    return "\n".join(chunks)


def test_app_loads():
    at = AppTest.from_file(str(APP), default_timeout=90).run()
    assert not at.exception
    assert at.button(key="run_review").label == "Run review"


def test_cpx_003_run_review_shows_pending_approval():
    at = AppTest.from_file(str(APP), default_timeout=90).run()
    at.selectbox(key="proposal").select("CPX-003")
    at.button(key="run_review").click().run(timeout=90)
    assert not at.exception
    assert "PENDING_APPROVAL" in _page(at)


def test_department_head_is_refused_for_cpx_001(tmp_path):
    at = AppTest.from_file(str(APP), default_timeout=90).run()
    at.selectbox(key="proposal").select("CPX-001")
    at.button(key="run_review").click().run(timeout=90)
    assert not at.exception
    at.text_input(key="approver_name").set_value("Pat Lee")
    at.selectbox(key="approver_role").select("department_head")
    at.selectbox(key="decision").select("APPROVED")
    at.button(key="sign_off").click().run(timeout=90)
    assert not at.exception
    assert any("cannot approve" in item.value for item in at.error)
    status_files = list(Path(tmp_path).glob("CPX-001-*/status.json"))
    assert len(status_files) == 1
    status = json.loads(status_files[0].read_text(encoding="utf-8"))
    assert status["status"] == "PENDING_APPROVAL"
    assert not (status_files[0].parent / "approvals.json").exists()


def test_kill_switch_refuses_run_review(monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEX_KILL_SWITCH", "1")
    at = AppTest.from_file(str(APP), default_timeout=90).run()
    at.button(key="run_review").click().run(timeout=90)
    assert not at.exception
    assert any("Kill switch" in item.value for item in at.error)
    folders = [path for path in Path(tmp_path).iterdir() if path.is_dir()]
    assert folders == []
