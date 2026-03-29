"""CLI 진입점."""

from __future__ import annotations

import argparse
import sys

from cmux_agent.cli.commands import (
    cmd_agents,
    cmd_doctor,
    cmd_events,
    cmd_messages,
    cmd_register,
    cmd_send,
    cmd_start,
    cmd_status,
    cmd_stop,
    cmd_watch,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cmux-agent",
        description="cmux 기반 멀티 에이전트 메시지 브로커",
    )
    sub = parser.add_subparsers(dest="command")

    # doctor
    sub.add_parser("doctor", help="시스템 진단")

    # start
    p_start = sub.add_parser("start", help="새 run 시작")
    p_start.add_argument("--cwd", default=".", help="작업 디렉토리")

    # stop
    p_stop = sub.add_parser("stop", help="run 종료")
    p_stop.add_argument("run_id", nargs="?", help="run ID (기본: 최근)")

    # register
    p_reg = sub.add_parser("register", help="agent 등록")
    p_reg.add_argument("name", help="agent 이름")
    p_reg.add_argument(
        "--role",
        choices=["orchestrator", "worker"],
        default="worker",
        help="역할 (기본: worker)",
    )
    p_reg.add_argument("--surface-id", help="cmux surface ID")

    # agents
    p_agents = sub.add_parser("agents", help="등록된 agent 목록")
    p_agents.add_argument("run_id", nargs="?", help="run ID")

    # watch
    p_watch = sub.add_parser("watch", help="outbox watcher 시작")
    p_watch.add_argument("--daemon", action="store_true", help="백그라운드 모드")

    # status
    p_status = sub.add_parser("status", help="run 상태 조회")
    p_status.add_argument("run_id", nargs="?", help="run ID")

    # events
    p_events = sub.add_parser("events", help="이벤트 로그 조회")
    p_events.add_argument("run_id", nargs="?", help="run ID")
    p_events.add_argument("-n", "--limit", type=int, default=20, help="최근 N건")

    # send
    p_send = sub.add_parser("send", help="수동 메시지 전송")
    p_send.add_argument("recipient", help="수신자 agent 이름")
    p_send.add_argument("message", help="메시지 내용")

    # messages
    p_msg = sub.add_parser("messages", help="메시지 이력 조회")
    p_msg.add_argument("run_id", nargs="?", help="run ID")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        args.command = "start"
        args.cwd = "."

    commands = {
        "doctor": cmd_doctor,
        "start": cmd_start,
        "stop": cmd_stop,
        "register": cmd_register,
        "agents": cmd_agents,
        "watch": cmd_watch,
        "status": cmd_status,
        "events": cmd_events,
        "send": cmd_send,
        "messages": cmd_messages,
    }

    handler = commands.get(args.command)
    if handler:
        try:
            handler(args)
        except Exception as exc:  # noqa: BLE001
            print(f"오류: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
