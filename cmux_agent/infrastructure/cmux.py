"""cmux CLI 어댑터."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CmuxResult:
    ok: bool
    stdout: str
    stderr: str

    def json(self) -> dict | list:
        return json.loads(self.stdout)


class CmuxAdapter:
    """cmux CLI를 감싼 어댑터. cmux 의존성을 이 클래스에서 격리한다."""

    CMUX_BIN = "cmux"

    def _run(self, *args: str, timeout: int = 10) -> CmuxResult:
        try:
            proc = subprocess.run(
                [self.CMUX_BIN, *args],
                capture_output=True, text=True, timeout=timeout,
            )
            return CmuxResult(
                ok=proc.returncode == 0,
                stdout=proc.stdout.strip(),
                stderr=proc.stderr.strip(),
            )
        except FileNotFoundError:
            return CmuxResult(ok=False, stdout="", stderr="cmux not found")
        except subprocess.TimeoutExpired:
            return CmuxResult(ok=False, stdout="", stderr="cmux timeout")

    # -- 진단 ---------------------------------------------------------------

    def is_available(self) -> bool:
        return self._run("ping").ok

    # -- Workspace ----------------------------------------------------------

    def new_workspace(self, *, cwd: str | None = None) -> CmuxResult:
        args = ["new-workspace"]
        if cwd:
            args.extend(["--cwd", cwd])
        return self._run(*args)

    def list_workspaces(self) -> CmuxResult:
        return self._run("list-workspaces", "--json")

    def current_workspace(self) -> CmuxResult:
        return self._run("current-workspace", "--json")

    def close_workspace(self, workspace_id: str) -> CmuxResult:
        return self._run("close-workspace", "--workspace", workspace_id)

    def select_workspace(self, workspace_id: str) -> CmuxResult:
        return self._run("select-workspace", "--workspace", workspace_id)

    def rename_workspace(self, workspace_id: str, title: str) -> CmuxResult:
        return self._run("rename-workspace", "--workspace", workspace_id, title)

    # -- Pane / Surface -----------------------------------------------------

    def new_split(
        self,
        direction: str,
        *,
        workspace_id: str | None = None,
        surface_id: str | None = None,
    ) -> CmuxResult:
        args = ["new-split", direction]
        if workspace_id:
            args.extend(["--workspace", workspace_id])
        if surface_id:
            args.extend(["--surface", surface_id])
        return self._run(*args)

    def new_surface(
        self,
        *,
        pane_id: str | None = None,
        workspace_id: str | None = None,
    ) -> CmuxResult:
        args = ["new-surface", "--type", "terminal"]
        if pane_id:
            args.extend(["--pane", pane_id])
        if workspace_id:
            args.extend(["--workspace", workspace_id])
        return self._run(*args)

    def list_surfaces(self, workspace_id: str | None = None) -> CmuxResult:
        args = ["list-pane-surfaces"]
        if workspace_id:
            args.extend(["--workspace", workspace_id])
        return self._run(*args)

    def focus_surface(self, surface_id: str) -> CmuxResult:
        return self._run("focus-surface", "--surface", surface_id)

    def close_surface(self, surface_id: str) -> CmuxResult:
        return self._run("close-surface", "--surface", surface_id)

    def rename_tab(
        self,
        title: str,
        *,
        surface_id: str | None = None,
        workspace_id: str | None = None,
    ) -> CmuxResult:
        args = ["rename-tab"]
        if workspace_id:
            args.extend(["--workspace", workspace_id])
        if surface_id:
            args.extend(["--surface", surface_id])
        args.append(title)
        return self._run(*args)

    def tree(self, workspace_id: str | None = None) -> CmuxResult:
        args = ["tree", "--json"]
        if workspace_id:
            args.extend(["--workspace", workspace_id])
        return self._run(*args)

    # -- Input / 통보 -------------------------------------------------------

    def send_text(
        self,
        text: str,
        *,
        surface_id: str | None = None,
        workspace_id: str | None = None,
    ) -> CmuxResult:
        args = ["send"]
        if workspace_id:
            args.extend(["--workspace", workspace_id])
        if surface_id:
            args.extend(["--surface", surface_id])
        args.append(text)
        return self._run(*args)

    def send_key(
        self,
        key: str,
        *,
        surface_id: str | None = None,
        workspace_id: str | None = None,
    ) -> CmuxResult:
        args = ["send-key"]
        if workspace_id:
            args.extend(["--workspace", workspace_id])
        if surface_id:
            args.extend(["--surface", surface_id])
        args.append(key)
        return self._run(*args)

    def trigger_flash(
        self,
        *,
        surface_id: str | None = None,
        workspace_id: str | None = None,
    ) -> CmuxResult:
        args = ["trigger-flash"]
        if workspace_id:
            args.extend(["--workspace", workspace_id])
        if surface_id:
            args.extend(["--surface", surface_id])
        return self._run(*args)

    # -- 알림 / 상태 ---------------------------------------------------------

    def notify(self, title: str, body: str = "") -> CmuxResult:
        args = ["notify", "--title", title]
        if body:
            args.extend(["--body", body])
        return self._run(*args)

    def set_status(
        self,
        key: str,
        value: str,
        *,
        icon: str | None = None,
        color: str | None = None,
        workspace_id: str | None = None,
    ) -> CmuxResult:
        args = ["set-status"]
        if workspace_id:
            args.extend(["--workspace", workspace_id])
        if icon:
            args.extend(["--icon", icon])
        if color:
            args.extend(["--color", color])
        args.extend([key, value])
        return self._run(*args)

    def log(
        self,
        message: str,
        *,
        level: str = "info",
        source: str | None = None,
        workspace_id: str | None = None,
    ) -> CmuxResult:
        args = ["log", "--level", level]
        if source:
            args.extend(["--source", source])
        if workspace_id:
            args.extend(["--workspace", workspace_id])
        args.extend(["--", message])
        return self._run(*args)

    # -- 유틸 ---------------------------------------------------------------

    def identify(
        self,
        *,
        workspace_id: str | None = None,
        surface_id: str | None = None,
    ) -> CmuxResult:
        args = ["identify", "--json"]
        if workspace_id:
            args.extend(["--workspace", workspace_id])
        if surface_id:
            args.extend(["--surface", surface_id])
        return self._run(*args)

    def is_surface_alive(self, surface_id: str) -> bool:
        """surface가 아직 존재하는지 확인한다."""
        result = self._run("surface-health", "--surface", surface_id)
        return result.ok
