from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import requests

from backend.tools.rest_tool import RESTTool


def test_rest_tool_fetch_and_write(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    response = Mock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    response.text = '{"ok": true}'
    response.raise_for_status = Mock()
    response.json = Mock(return_value={"ok": True})
    monkeypatch.setattr(requests, "request", Mock(return_value=response))

    tool = RESTTool()
    result = tool.execute(
        {
            "url": "https://example.com/data.json",
            "workspace_root": str(tmp_path),
            "output_path": "downloads/data.json",
            "expect_json": True,
        }
    )

    assert result["success"] is True
    assert result["metadata"]["status_code"] == 200
    assert (tmp_path / "downloads/data.json").exists()
    assert result["generated_files"][0]["path"] == "downloads/data.json"
