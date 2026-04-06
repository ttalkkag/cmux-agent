"""CLI 테스트."""

import json
import sys
from unittest.mock import patch

import pytest

from cmux_agent.cli import main


class TestCLI:
    def test_no_command_defaults_to_start(self):
        """인자 없이 실행하면 start가 기본 동작."""
        from unittest.mock import patch
        with patch("cmux_agent.cli.cmd_start") as mock_start:
            main([])
            mock_start.assert_called_once()

    def test_doctor(self, capsys):
        main(["doctor"])
        output = capsys.readouterr().out
        assert "python" in output

    def test_unknown_command(self, capsys):
        with pytest.raises(SystemExit):
            main(["nonexistent"])


class TestInitCommand:
    def test_init_creates_default_files(self, tmp_path):
        main(["init", "--cwd", str(tmp_path)])

        cmux_dir = tmp_path / ".cmux"
        assert (cmux_dir / "agents.json").exists()
        assert (cmux_dir / "prompts" / "orchestrator.md").exists()
        assert (cmux_dir / "prompts" / "worker.md").exists()
        assert (cmux_dir / "prompts" / "dispatch.md").exists()
        assert (cmux_dir / "prompts" / "result.md").exists()

        config = json.loads((cmux_dir / "agents.json").read_text(encoding="utf-8"))
        assert config["orchestrator"] == "claude"
        assert config["worker-1"] == "claude"

    def test_init_does_not_overwrite_existing_files(self, tmp_path):
        cmux_dir = tmp_path / ".cmux"
        prompts_dir = cmux_dir / "prompts"
        prompts_dir.mkdir(parents=True)
        (cmux_dir / "agents.json").write_text('{"orchestrator":"gemini"}\n', encoding="utf-8")
        (prompts_dir / "worker.md").write_text("custom-worker\n", encoding="utf-8")

        main(["init", "--cwd", str(tmp_path)])

        config = json.loads((cmux_dir / "agents.json").read_text(encoding="utf-8"))
        assert config["orchestrator"] == "gemini"
        assert (prompts_dir / "worker.md").read_text(encoding="utf-8") == "custom-worker\n"
