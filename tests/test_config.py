"""설정 파일 로딩 테스트."""

import json
import os

from cmux_agent.cli.commands import (
    _load_config,
    _load_normalized_config,
    _normalize_agent_entry,
    DEFAULT_CONFIG,
)


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
        (tmp_path / ".cmux").mkdir()
        (tmp_path / ".cmux" / "agents.json").write_text(json.dumps(cfg))

        config = _load_config(str(tmp_path))
        assert config["orchestrator"] == "claude"
        assert config["worker-1"] == "codex"
        assert config["worker-2"] == "gemini"

    def test_merges_with_default(self, tmp_path):
        cfg = {"worker-2": "gemini"}
        (tmp_path / ".cmux").mkdir()
        (tmp_path / ".cmux" / "agents.json").write_text(json.dumps(cfg))

        config = _load_config(str(tmp_path))
        assert config["orchestrator"] == "claude"
        assert config["worker-1"] == "claude"
        assert config["worker-2"] == "gemini"

    def test_invalid_json_returns_default(self, tmp_path):
        (tmp_path / ".cmux").mkdir()
        (tmp_path / ".cmux" / "agents.json").write_text("not json")
        config = _load_config(str(tmp_path))
        assert config == DEFAULT_CONFIG


class TestNormalizeAgentEntry:
    def test_string_to_provider_dict(self):
        result = _normalize_agent_entry("claude")
        assert result == {"provider": "claude"}

    def test_dict_passthrough(self):
        entry = {"provider": "gemini", "skills": ["code-review"]}
        result = _normalize_agent_entry(entry)
        assert result == entry


class TestLoadNormalizedConfig:
    def test_string_config_normalized(self, tmp_path):
        cfg = {"orchestrator": "claude", "worker-1": "codex"}
        (tmp_path / ".cmux").mkdir()
        (tmp_path / ".cmux" / "agents.json").write_text(json.dumps(cfg))

        config = _load_normalized_config(str(tmp_path))
        assert config["orchestrator"] == {"provider": "claude"}
        assert config["worker-1"] == {"provider": "codex"}

    def test_object_config_preserved(self, tmp_path):
        cfg = {
            "orchestrator": "claude",
            "worker-1": {"provider": "gemini", "skills": ["research"]},
        }
        (tmp_path / ".cmux").mkdir()
        (tmp_path / ".cmux" / "agents.json").write_text(json.dumps(cfg))

        config = _load_normalized_config(str(tmp_path))
        assert config["orchestrator"] == {"provider": "claude"}
        assert config["worker-1"]["provider"] == "gemini"
        assert config["worker-1"]["skills"] == ["research"]

    def test_mixed_config(self, tmp_path):
        cfg = {
            "orchestrator": "claude",
            "worker-1": "codex",
            "worker-2": {"provider": "gemini", "description": "연구 담당"},
        }
        (tmp_path / ".cmux").mkdir()
        (tmp_path / ".cmux" / "agents.json").write_text(json.dumps(cfg))

        config = _load_normalized_config(str(tmp_path))
        assert config["orchestrator"]["provider"] == "claude"
        assert config["worker-1"]["provider"] == "codex"
        assert config["worker-2"]["provider"] == "gemini"

    def test_default_normalized(self, tmp_path):
        config = _load_normalized_config(str(tmp_path))
        assert config["orchestrator"] == {"provider": "claude"}
        assert config["worker-1"] == {"provider": "claude"}
