#!/usr/bin/env python3
"""PTY supervisor for harnessed CLI runs."""

from __future__ import annotations

import json
import os
import pty
import select
import signal
import struct
import sys
import termios
import time
import tty
import fcntl

BIN_DIR = os.path.dirname(os.path.abspath(__file__))
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)

from _harness_common import append_event, atomic_write_json, iso_now, read_json
from _run_channel import append_message


def read_intervention(path, last_marker):
    if not path or not os.path.exists(path):
        return None, last_marker
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception:
        return None, last_marker
    command_id = str(payload.get("command_id", "")).strip()
    status = str(payload.get("status", "active")).strip() or "active"
    marker = f"{status}:{command_id}"
    if not command_id or marker == last_marker:
        return None, last_marker
    return payload, marker


def set_raw_if_tty(fd):
    if not os.isatty(fd):
        return None
    attrs = termios.tcgetattr(fd)
    tty.setraw(fd)
    return attrs


def restore_tty(fd, attrs):
    if attrs is None:
        return
    termios.tcsetattr(fd, termios.TCSADRAIN, attrs)


def foreground_pgid(fd):
    if not os.isatty(fd):
        return None
    try:
        return os.tcgetpgrp(fd)
    except Exception:
        return None


def set_foreground_pgid(fd, pgid):
    if not os.isatty(fd):
        return False
    try:
        os.tcsetpgrp(fd, int(pgid))
        return True
    except Exception:
        return False


def reclaim_terminal(fd, target_pgid):
    before = foreground_pgid(fd)
    changed = set_foreground_pgid(fd, target_pgid)
    after = foreground_pgid(fd)
    return {"before": before, "after": after, "changed": changed}


def get_winsize(fd):
    if not os.isatty(fd):
        return None
    try:
        data = fcntl.ioctl(fd, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
        rows, cols, xpix, ypix = struct.unpack("HHHH", data)
        return {"rows": rows, "cols": cols, "xpix": xpix, "ypix": ypix}
    except Exception:
        return None


def set_winsize(fd, winsize):
    if not winsize:
        return False
    try:
        packed = struct.pack(
            "HHHH",
            int(winsize.get("rows", 0) or 0),
            int(winsize.get("cols", 0) or 0),
            int(winsize.get("xpix", 0) or 0),
            int(winsize.get("ypix", 0) or 0),
        )
        fcntl.ioctl(fd, termios.TIOCSWINSZ, packed)
        return True
    except Exception:
        return False


def sync_winsize(src_fd, dst_fd):
    winsize = get_winsize(src_fd)
    if not winsize:
        return None
    return winsize if set_winsize(dst_fd, winsize) else None


def install_supervisor_signal_guards():
    previous = {}
    for sig in (signal.SIGTTOU, signal.SIGTTIN):
        try:
            previous[sig] = signal.getsignal(sig)
            signal.signal(sig, signal.SIG_IGN)
        except Exception:
            continue
    return previous


def restore_supervisor_signal_guards(previous):
    for sig, handler in (previous or {}).items():
        try:
            signal.signal(sig, handler)
        except Exception:
            continue


def emit_event(event_type, actor_id, payload=None):
    run_id = os.environ.get("BROKE_HARNESS_RUN_ID", "")
    events_file = os.environ.get("BROKE_HARNESS_EVENTS_FILE", "")
    if not run_id or not events_file:
        return
    append_event(
        events_file,
        run_id,
        event_type,
        "runtime_control",
        "pty_supervisor",
        actor_id,
        payload=payload or {},
    )


def emit_message(kind, payload=None, channel="control"):
    run_id = os.environ.get("BROKE_HARNESS_RUN_ID", "")
    channel_file = os.environ.get("BROKE_HARNESS_CHANNEL_FILE", "")
    if not run_id or not channel_file:
        return
    append_message(channel_file, run_id, channel, kind, payload or {})


def child_pgid(pid):
    try:
        return os.getpgid(pid)
    except OSError:
        return None


def child_sid(pid):
    try:
        return os.getsid(pid)
    except OSError:
        return None


def append_output(path, data):
    if not path or not data:
        return
    try:
        with open(path, "ab") as fh:
            fh.write(data)
    except Exception:
        return
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def write_session(path, payload):
    if not path:
        return
    atomic_write_json(path, payload)


def update_session(path, **updates):
    if not path:
        return
    current = read_json(path, {})
    current.update(updates)
    write_session(path, current)


def read_control(path, last_marker):
    if not path or not os.path.exists(path):
        return None, last_marker
    payload = read_json(path, {})
    command_id = str(payload.get("command_id", "")).strip()
    action = str(payload.get("action", "")).strip()
    marker = f"{command_id}:{action}"
    if not command_id or not action or marker == last_marker:
        return None, last_marker
    return payload, marker


def control_matches_session(control, supervisor_pid, child_pid):
    expected_supervisor = control.get("expected_supervisor_pid")
    expected_child = control.get("expected_child_pid")
    if expected_supervisor not in (None, "", supervisor_pid):
        return False
    if expected_child not in (None, "", child_pid):
        return False
    return True


def signal_child_tree(pid, sig):
    try:
        pgid = os.getpgid(pid)
    except OSError:
        pgid = None
    if pgid:
        try:
            os.killpg(pgid, sig)
            return "process_group"
        except OSError:
            pass
    try:
        os.kill(pid, sig)
        return "process"
    except OSError:
        return "missing"


def terminate_child_tree(pid, grace_seconds=0.3):
    target = signal_child_tree(pid, signal.SIGTERM)
    if target == "missing":
        return "missing"
    deadline = time.time() + max(0.0, grace_seconds)
    while time.time() < deadline:
        if signal_child_tree(pid, 0) == "missing":
            return target
        time.sleep(0.05)
    signal_child_tree(pid, signal.SIGKILL)
    return f"{target}_escalated"


def main():
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        cmd = sys.argv[idx + 1 :]
    else:
        cmd = sys.argv[1:]
    if not cmd:
        print("usage: _pty_harness.py -- <command> [args...]", file=sys.stderr)
        return 2

    intervention_file = os.environ.get("BROKE_HARNESS_INTERVENTION_FILE", "")
    session_file = os.environ.get("BROKE_HARNESS_SESSION_FILE", "")
    control_file = os.environ.get("BROKE_HARNESS_CONTROL_FILE", "")
    output_file = os.environ.get("BROKE_HARNESS_OUTPUT_FILE", "")
    last_intervention_id = ""
    last_control_id = ""
    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()
    stderr_fd = sys.stderr.fileno()
    saved_tty = set_raw_if_tty(stdin_fd)
    saved_signal_guards = install_supervisor_signal_guards()
    resize_pending = False
    hup_pending = False
    reattach_pending = False

    def on_sigwinch(signum, frame):
        nonlocal resize_pending
        resize_pending = True

    def on_sighup(signum, frame):
        nonlocal hup_pending
        hup_pending = True

    def on_sigcont(signum, frame):
        nonlocal reattach_pending
        reattach_pending = True

    previous_winch = None
    previous_hup = None
    previous_cont = None
    try:
        previous_winch = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, on_sigwinch)
    except Exception:
        previous_winch = None
    try:
        previous_hup = signal.getsignal(signal.SIGHUP)
        signal.signal(signal.SIGHUP, on_sighup)
    except Exception:
        previous_hup = None
    try:
        previous_cont = signal.getsignal(signal.SIGCONT)
        signal.signal(signal.SIGCONT, on_sigcont)
    except Exception:
        previous_cont = None

    pid, master_fd = pty.fork()
    if pid == 0:
        os.execvpe(cmd[0], cmd, os.environ)
        return 127

    current_winsize = sync_winsize(stdin_fd, master_fd)
    target_pgid = child_pgid(pid)
    foreground = reclaim_terminal(stdin_fd, target_pgid) if target_pgid else {"before": foreground_pgid(stdin_fd), "after": foreground_pgid(stdin_fd), "changed": False}

    write_session(
        session_file,
        {
            "status": "running",
            "started_at": iso_now(),
            "supervisor_pid": os.getpid(),
            "child_pid": pid,
            "child_pgid": target_pgid,
            "child_sid": child_sid(pid),
            "supervisor_sid": os.getsid(0) if os.isatty(stdin_fd) else None,
            "foreground_pgid": foreground.get("after"),
            "foreground_claimed": bool(foreground.get("changed")),
            "argv": cmd,
            "stdin_attached": True,
            "winsize": current_winsize or {},
        },
    )
    emit_event("session.started", "pty_harness", {"argv": cmd, "child_pid": pid})
    emit_message("session.started", {"argv": cmd, "child_pid": pid, "supervisor_pid": os.getpid(), "child_pgid": child_pgid(pid)})
    interrupted_for_intervention = False
    stdin_attached = True
    try:
        while True:
            if hup_pending:
                hup_pending = False
                stdin_attached = False
                update_session(session_file, stdin_attached=False, detached=True, detach_reason="sighup", updated_at=iso_now())
                emit_event("session.detached", "pty_harness", {"reason": "sighup", "child_pid": pid, "child_pgid": child_pgid(pid)})
                emit_message("session.detached", {"reason": "sighup", "child_pid": pid, "child_pgid": child_pgid(pid)})
            if reattach_pending:
                reattach_pending = False
                if os.isatty(stdin_fd):
                    saved_tty = set_raw_if_tty(stdin_fd)
                    fg = reclaim_terminal(stdin_fd, child_pgid(pid) or pid)
                    winsize = sync_winsize(stdin_fd, master_fd)
                    stdin_attached = True
                    update_session(
                        session_file,
                        stdin_attached=True,
                        detached=False,
                        detach_reason="",
                        reattached_at=iso_now(),
                        foreground_pgid=fg.get("after"),
                        foreground_claimed=bool(fg.get("changed")),
                        winsize=winsize or read_json(session_file, {}).get("winsize", {}),
                        updated_at=iso_now(),
                    )
                    emit_event("session.reattached", "pty_harness", {"foreground_pgid": fg.get("after"), "child_pgid": child_pgid(pid)})
                    emit_message("session.reattached", {"foreground_pgid": fg.get("after"), "child_pgid": child_pgid(pid)})
            if resize_pending:
                resize_pending = False
                winsize = sync_winsize(stdin_fd, master_fd)
                if winsize:
                    update_session(session_file, winsize=winsize, updated_at=iso_now())
                    emit_event("session.window_resized", "pty_harness", winsize)
                    emit_message("session.window_resized", winsize)

            control, last_control_id = read_control(control_file, last_control_id)
            if control is not None:
                if not control_matches_session(control, os.getpid(), pid):
                    emit_event(
                        "session.operator_ignored",
                        "pty_harness",
                        {
                            "command_id": control.get("command_id", ""),
                            "reason": "session_mismatch",
                            "expected_supervisor_pid": control.get("expected_supervisor_pid"),
                            "expected_child_pid": control.get("expected_child_pid"),
                        },
                    )
                    continue
                action = control.get("action", "")
                command_id = control.get("command_id", "")
                if action == "interrupt":
                    target = signal_child_tree(pid, signal.SIGINT)
                    message = b"\r\n[harness] operator interrupt requested\r\n"
                    os.write(stderr_fd, message)
                    append_output(output_file, message)
                    update_session(
                        session_file,
                        status="interrupted",
                        last_operator_action="interrupt",
                        last_operator_action_id=command_id,
                        last_signal_target=target,
                        last_control_at=iso_now(),
                        updated_at=iso_now(),
                    )
                    emit_event("session.operator_interrupt", "pty_harness", {"command_id": command_id, "target": target, "supervisor_pid": os.getpid(), "child_pid": pid, "child_pgid": child_pgid(pid)})
                    emit_message("session.operator_interrupt", {"command_id": command_id, "target": target, "supervisor_pid": os.getpid(), "child_pid": pid, "child_pgid": child_pgid(pid)})
                    interrupted_for_intervention = True
                elif action == "kill":
                    target = terminate_child_tree(pid)
                    message = b"\r\n[harness] operator kill requested\r\n"
                    os.write(stderr_fd, message)
                    append_output(output_file, message)
                    update_session(
                        session_file,
                        status="terminating",
                        last_operator_action="kill",
                        last_operator_action_id=command_id,
                        last_signal_target=target,
                        last_control_at=iso_now(),
                        updated_at=iso_now(),
                    )
                    emit_event("session.operator_kill", "pty_harness", {"command_id": command_id, "target": target, "supervisor_pid": os.getpid(), "child_pid": pid, "child_pgid": child_pgid(pid)})
                    emit_message("session.operator_kill", {"command_id": command_id, "target": target, "supervisor_pid": os.getpid(), "child_pid": pid, "child_pgid": child_pgid(pid)})
                elif action == "resume":
                    interrupted_for_intervention = False
                    message = b"\r\n[harness] operator resume requested\r\n"
                    os.write(stderr_fd, message)
                    append_output(output_file, message)
                    update_session(
                        session_file,
                        status="running",
                        last_operator_action="resume",
                        last_operator_action_id=command_id,
                        last_control_at=iso_now(),
                        updated_at=iso_now(),
                    )
                    emit_event("session.operator_resume", "pty_harness", {"command_id": command_id, "supervisor_pid": os.getpid(), "child_pid": pid, "child_pgid": child_pgid(pid)})
                    emit_message("session.operator_resume", {"command_id": command_id, "supervisor_pid": os.getpid(), "child_pid": pid, "child_pgid": child_pgid(pid)})
                elif action == "reattach":
                    reattach_pending = True
                    update_session(session_file, last_operator_action="reattach", last_operator_action_id=command_id, last_control_at=iso_now(), updated_at=iso_now())
                    emit_event("session.operator_reattach", "pty_harness", {"command_id": command_id, "supervisor_pid": os.getpid(), "child_pid": pid, "child_pgid": child_pgid(pid)})
                    emit_message("session.operator_reattach", {"command_id": command_id, "supervisor_pid": os.getpid(), "child_pid": pid, "child_pgid": child_pgid(pid)})

            intervention, last_intervention_id = read_intervention(intervention_file, last_intervention_id)
            if intervention is not None:
                notice = intervention.get("notice", "harness intervention active")
                next_action = intervention.get("next_action", "")
                status = intervention.get("status", "active")
                if status == "resolved":
                    message = f"\r\n[harness] resumed: {notice}\r\n".encode()
                    os.write(stderr_fd, message)
                    append_output(output_file, message)
                    if next_action:
                        next_bytes = f"[harness] next: {next_action}\r\n".encode()
                        os.write(stderr_fd, next_bytes)
                        append_output(output_file, next_bytes)
                    update_session(session_file, status="running", updated_at=iso_now(), intervention_status="resolved")
                    emit_event(
                        "session.resumed",
                        "pty_harness",
                        {"notice": notice, "next_action": next_action, "command_id": intervention.get("command_id", "")},
                    )
                    emit_message("session.resolved", {"notice": notice, "next_action": next_action, "command_id": intervention.get("command_id", "")})
                    interrupted_for_intervention = False
                else:
                    reason = intervention.get("reason", "intervention")
                    message = f"\r\n[harness] intervention: {notice}\r\n".encode()
                    os.write(stderr_fd, message)
                    append_output(output_file, message)
                    if next_action:
                        next_bytes = f"[harness] next: {next_action}\r\n".encode()
                        os.write(stderr_fd, next_bytes)
                        append_output(output_file, next_bytes)
                    target = signal_child_tree(pid, signal.SIGINT)
                    try:
                        os.write(master_fd, b"\x03")
                        injected = f"\n[harness] {notice}\n"
                        if next_action:
                            injected += f"[harness] next: {next_action}\n"
                        injected_bytes = injected.encode()
                        os.write(master_fd, injected_bytes)
                        append_output(output_file, injected_bytes)
                    except OSError:
                        pass
                    update_session(session_file, status="interrupted", updated_at=iso_now(), intervention_status="active", intervention_reason=reason)
                    emit_event(
                        "session.interrupted",
                        "pty_harness",
                        {"reason": reason, "notice": notice, "next_action": next_action, "command_id": intervention.get("command_id", ""), "target": target},
                    )
                    emit_message("session.interrupted", {"reason": reason, "notice": notice, "next_action": next_action, "command_id": intervention.get("command_id", ""), "target": target})
                    interrupted_for_intervention = True

            rfds = [master_fd]
            if stdin_attached and not interrupted_for_intervention:
                rfds.append(stdin_fd)
            ready, _, _ = select.select(rfds, [], [], 0.2)

            if master_fd in ready:
                try:
                    data = os.read(master_fd, 65536)
                except OSError:
                    data = b""
                if not data:
                    break
                os.write(stdout_fd, data)
                append_output(output_file, data)

            if stdin_fd in ready:
                try:
                    data = os.read(stdin_fd, 65536)
                except OSError:
                    data = b""
                if not data:
                    stdin_attached = False
                    update_session(session_file, stdin_attached=False, stdin_detached_at=iso_now(), updated_at=iso_now())
                    emit_event("session.stdin_detached", "pty_harness", {"child_pid": pid, "child_pgid": child_pgid(pid)})
                    emit_message("session.stdin_detached", {"child_pid": pid, "child_pgid": child_pgid(pid)})
                    continue
                if interrupted_for_intervention:
                    interrupted_for_intervention = False
                    update_session(session_file, status="running", updated_at=iso_now())
                os.write(master_fd, data)

            try:
                waited_pid, status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                break
            if waited_pid == pid:
                if os.WIFEXITED(status):
                    update_session(session_file, status="completed", updated_at=iso_now(), exit_code=os.WEXITSTATUS(status))
                    emit_event("session.completed", "pty_harness", {"exit_code": os.WEXITSTATUS(status)})
                    emit_message("session.completed", {"exit_code": os.WEXITSTATUS(status), "supervisor_pid": os.getpid(), "child_pid": pid, "child_pgid": child_pgid(pid)})
                    return os.WEXITSTATUS(status)
                if os.WIFSIGNALED(status):
                    code = 128 + os.WTERMSIG(status)
                    update_session(session_file, status="completed", updated_at=iso_now(), exit_code=code, signal=os.WTERMSIG(status))
                    emit_event("session.completed", "pty_harness", {"exit_code": code, "signal": os.WTERMSIG(status)})
                    emit_message("session.completed", {"exit_code": code, "signal": os.WTERMSIG(status), "supervisor_pid": os.getpid(), "child_pid": pid, "child_pgid": child_pgid(pid)})
                    return code
                break
    finally:
        update_session(session_file, updated_at=iso_now())
        restore_tty(stdin_fd, saved_tty)
        restore_supervisor_signal_guards(saved_signal_guards)
        if previous_winch is not None:
            try:
                signal.signal(signal.SIGWINCH, previous_winch)
            except Exception:
                pass
        if previous_hup is not None:
            try:
                signal.signal(signal.SIGHUP, previous_hup)
            except Exception:
                pass
        if previous_cont is not None:
            try:
                signal.signal(signal.SIGCONT, previous_cont)
            except Exception:
                pass
        try:
            os.close(master_fd)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
