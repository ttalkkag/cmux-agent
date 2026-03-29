"""CLI 테스트."""

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
