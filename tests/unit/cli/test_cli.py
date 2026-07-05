"""
Tests for emergence.cli.
"""

from __future__ import annotations

from emergence.cli.__main__ import main


class TestCLI:
    def test_ps_demo_exits_zero(self, capsys):
        assert main(["ps", "--demo"]) == 0

        output = capsys.readouterr().out
        assert "EmergenceOS process monitor" in output
        assert "fast" in output
        assert "pending" in output
        assert "fail" in output

    def test_top_once_demo_exits_zero(self, capsys):
        assert main(["top", "--demo", "--once"]) == 0

        output = capsys.readouterr().out
        assert "READY QUEUE" in output

    def test_sched_demo_exits_zero(self, capsys):
        assert main(["sched", "--demo"]) == 0

        output = capsys.readouterr().out
        assert "READY QUEUE" in output

    def test_state_demo_exits_zero(self, capsys):
        assert main(["state", "--demo"]) == 0

        output = capsys.readouterr().out
        assert "last_completed" in output
