"""설정 파일 로딩 테스트."""

import json
import os

from cmux_agent.cli.commands import _load_config, DEFAULT_CONFIG


class TestLoadConfig:
    def test_default_when_no_file(self, tmp_path):
        config = _load_config(str(tmp_path))
        assert config == DEFAULT_CONFIG

    def test_loads_from_file(self, tmp_path):
        cfg = {
            "orchestrator": "claude",
            "worker-1": "codex",
            "worker-2": "gemini",
        }
        (tmp_path / "cmux-agent.json").write_text(json.dumps(cfg))

        config = _load_config(str(tmp_path))
        assert config["orchestrator"] == "claude"
        assert config["worker-1"] == "codex"
        assert config["worker-2"] == "gemini"

    def test_merges_with_default(self, tmp_path):
        cfg = {"worker-2": "gemini"}
        (tmp_path / "cmux-agent.json").write_text(json.dumps(cfg))

        config = _load_config(str(tmp_path))
        assert config["orchestrator"] == "claude"
        assert config["worker-1"] == "claude"
        assert config["worker-2"] == "gemini"

    def test_invalid_json_returns_default(self, tmp_path):
        (tmp_path / "cmux-agent.json").write_text("not json")
        config = _load_config(str(tmp_path))
        assert config == DEFAULT_CONFIG
