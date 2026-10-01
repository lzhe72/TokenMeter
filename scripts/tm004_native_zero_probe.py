#!/usr/bin/env python3
"""Reproduce Claude 2.1.126 zero/missing-usage native JSONL in isolation.

Source research only. The loopback responses are synthetic and cannot prove
that an actual provider bills a zero-token call.
"""

from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import socketserver
import stat
import subprocess
import tempfile
import threading


REPO = Path(__file__).resolve().parents[1]
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
CLI = Path("/usr/local/bin/claude")
CLI_SHA256 = "49a90c474383a9eda11310bd71f7ea6bb91361ec99443b733cb5003f6e703ccb"
VERSION = "2.1.126 (Claude Code)"
MODEL = "claude-sonnet-4-6"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sse(kind: str, value: dict) -> bytes:
    return (f"event: {kind}\ndata: " + json.dumps(value, separators=(",", ":")) + "\n\n").encode()


def response(mode: str) -> bytes:
    message = {
        "id": f"msg_tm004_{mode}_zero_probe_001", "type": "message", "role": "assistant",
        "model": MODEL, "content": [], "stop_reason": None, "stop_sequence": None,
    }
    if mode == "explicit_zero":
        message["usage"] = {
            "input_tokens": 0, "output_tokens": 0,
            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
        }
    delta = {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}}
    if mode == "explicit_zero":
        delta["usage"] = {"output_tokens": 0}
    return b"".join((
        sse("message_start", {"type": "message_start", "message": message}),
        sse("content_block_start", {"type": "content_block_start", "index": 0,
                                    "content_block": {"type": "text", "text": ""}}),
        sse("content_block_delta", {"type": "content_block_delta", "index": 0,
                                    "delta": {"type": "text_delta", "text": "SYNTHETIC_OK"}}),
        sse("content_block_stop", {"type": "content_block_stop", "index": 0}),
        sse("message_delta", delta),
        sse("message_stop", {"type": "message_stop"}),
    ))


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def ordinary_owned(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not path.is_symlink()


def run_mode(mode: str, root: Path, evidence: Path) -> dict:
    config = root / mode
    config.mkdir(mode=0o700)
    payload = response(mode)
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append({"path": self.path, "body_sha256": sha(raw)})
            if self.path.startswith("/v1/messages"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                result = payload
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                result = b'{"error":{"type":"not_found_error","message":"synthetic endpoint not defined"}}'
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            self.wfile.write(result)

        def log_message(self, *_):
            pass

    with Server(("127.0.0.1", 0), Handler) as server:
        port = server.server_address[1]
        profile = root / f"{mode}.sb"
        profile.write_text(
            "(version 1)\n(allow default)\n(deny network-outbound)\n"
            f'(allow network-outbound (remote ip "localhost:{port}"))\n'
            f'(deny file-read* (subpath "{Path.home()}"))\n'
            f'(deny file-write* (subpath "{Path.home()}"))\n'
            '(deny file-read* (subpath "/Users/Shared"))\n'
            '(deny file-write* (subpath "/Users/Shared"))\n'
        )
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin", "CLAUDE_CONFIG_DIR": str(config),
            "TMPDIR": str(root), "ANTHROPIC_API_KEY": "tm004-synthetic-fake-key",
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_TELEMETRY": "1",
            "DISABLE_UPDATES": "1", "NO_PROXY": "127.0.0.1,localhost",
        }
        command = ["/usr/bin/sandbox-exec", "-f", str(profile), str(CLI), "-p",
                   "TM004 synthetic zero provenance probe: reply SYNTHETIC_OK.",
                   "--model", MODEL, "--output-format", "json", "--max-turns", "1", "--tools", ""]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            try:
                completed = subprocess.run(command, env=env, cwd=root, capture_output=True,
                                           text=True, timeout=45, check=False)
                exit_code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
            except subprocess.TimeoutExpired as error:
                exit_code = "timeout"
                stdout = (error.stdout or b"").decode(errors="replace")
                stderr = (error.stderr or b"").decode(errors="replace")
        finally:
            server.shutdown()
            thread.join(timeout=5)

    for name, content in (("stdout", stdout), ("stderr", stderr)):
        output = evidence / f"{mode}-{name}.txt"
        output.write_text(content)
        output.chmod(0o600)
    native = []
    observations = []
    for path in config.rglob("*.jsonl"):
        if path.is_symlink() or path.stat().st_uid != os.getuid():
            raise ValueError("Non-owned or linked native file")
        data = path.read_bytes()
        for line in data.splitlines():
            row = json.loads(line)
            if row.get("type") == "assistant" and row.get("message", {}).get("id") == f"msg_tm004_{mode}_zero_probe_001":
                observations.append({"message_id": row["message"]["id"],
                                     "usage": row["message"].get("usage")})
        target = evidence / f"{mode}-{len(native)}.jsonl"
        target.write_bytes(data)
        target.chmod(0o600)
        native.append({"file": target.name, "sha256": sha(data), "bytes": len(data)})
    return {
        "mode": mode, "synthetic_sse_sha256": sha(payload),
        "upstream_usage_present": mode == "explicit_zero",
        "cli_exit": exit_code,
        "stdout_file": f"{mode}-stdout.txt", "stdout_sha256": sha(stdout.encode()),
        "stderr_file": f"{mode}-stderr.txt", "stderr_sha256": sha(stderr.encode()),
        "request_count": len(requests), "requests": requests,
        "native_files": native, "native_assistant_observations": observations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--run-id")
    action.add_argument("--verify-run-id")
    args = parser.parse_args()
    if args.verify_run_id:
        verify_existing(args.verify_run_id)
        return
    if not RUN_ID.fullmatch(args.run_id):
        raise ValueError("Invalid run ID")
    if sha(CLI.read_bytes()) != CLI_SHA256:
        raise ValueError("Claude executable SHA differs from verified 2.1.126")
    version = subprocess.run([str(CLI), "--version"], capture_output=True, text=True,
                             timeout=10, check=True).stdout.strip()
    if version != VERSION:
        raise ValueError("Claude executable version differs")
    evidence_parent = REPO / ".local/ci"
    if not ordinary_owned(evidence_parent):
        raise ValueError("Evidence parent is not an owned ordinary directory")
    evidence = evidence_parent / f"tm004-native-zero-{args.run_id}"
    evidence.mkdir(mode=0o700)
    expected = {
        "source": VERSION, "modes": ["explicit_zero", "omitted_usage"],
        "each_expected_requests": 1, "each_expected_assistant_rows": 1,
        "each_expected_usage": {"input_tokens": 0, "output_tokens": 0},
        "expected_native_usage_indistinguishable": True,
        "valid_provider_zero_proven": False,
    }
    expected_path = evidence / "expected-before-run.json"
    expected_path.write_text(json.dumps(expected, indent=2) + "\n")
    expected_path.chmod(0o600)
    temp = Path(tempfile.mkdtemp(prefix="tm004-zero-", dir="/private/tmp"))
    temp.chmod(0o700)
    marker = temp / ".tm004-owner.json"
    marker.write_text(json.dumps({"run_id": args.run_id, "purpose": "native-zero-source-probe"}))
    marker.chmod(0o600)
    try:
        results = [run_mode(mode, temp, evidence) for mode in ("explicit_zero", "omitted_usage")]
        if any(row["cli_exit"] != 0 or row["request_count"] != 1 or len(row["native_assistant_observations"]) != 1
               for row in results):
            state = "BLOCKED"
        else:
            usage = [row["native_assistant_observations"][0]["usage"] for row in results]
            state = "SOURCE_OBSERVED" if (usage[0] == usage[1] and
                      all(item["input_tokens"] == 0 and item["output_tokens"] == 0 for item in usage)) else "BLOCKED"
        report = {"state": state, "scope": "isolated_synthetic_cli_source_research",
                  "cli_version": VERSION, "cli_sha256": CLI_SHA256,
                  "product_e2e_executed": False, "valid_provider_zero_proven": False,
                  "native_usage_indistinguishable": state == "SOURCE_OBSERVED",
                  "results": results}
        output = evidence / "result.json"
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        output.chmod(0o600)
        print(json.dumps({"state": state, "evidence": str(output.relative_to(REPO)),
                          "observations": [row["native_assistant_observations"] for row in results]}))
    finally:
        if not ordinary_owned(temp) or not marker.is_file() or marker.is_symlink():
            raise ValueError("Private root lost ownership marker; refusing cleanup")
        for path in temp.rglob("*"):
            if path.is_symlink() or path.lstat().st_uid != os.getuid():
                raise ValueError("Private root contains non-owned/link entry; refusing cleanup")
        shutil.rmtree(temp)


def verify_existing(run_id: str) -> None:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid run ID")
    expected = json.loads((REPO / "tests/fixtures/tm004/zero-provenance-2.1.126.json").read_text())
    if run_id != expected["research_run_id"]:
        raise ValueError("Requested run does not match fixed native source fixture")
    evidence = REPO / ".local/ci" / f"tm004-native-zero-{run_id}"
    if not ordinary_owned(evidence):
        raise ValueError("Research evidence directory not owned")
    report = json.loads((evidence / "result.json").read_text())
    if (report["state"] != "SOURCE_OBSERVED" or report["cli_sha256"] != expected["cli_binary_sha256"]
            or report["valid_provider_zero_proven"] or not report["native_usage_indistinguishable"]):
        raise ValueError("Research result differs from fixed fixture")
    for actual, frozen in zip(report["results"], expected["cases"], strict=True):
        if actual["mode"] != frozen["mode"] or actual["synthetic_sse_sha256"] != frozen["synthetic_sse_sha256"]:
            raise ValueError("Synthetic source differs")
        files = actual["native_files"]
        if len(files) != 1 or files[0]["sha256"] != frozen["native_jsonl_sha256"]:
            raise ValueError("Native file identity differs")
        raw_path = evidence / files[0]["file"]
        if raw_path.is_symlink() or not raw_path.is_file() or sha(raw_path.read_bytes()) != files[0]["sha256"]:
            raise ValueError("Native original is missing or changed")
        observation = actual["native_assistant_observations"]
        if len(observation) != 1:
            raise ValueError("Native assistant observation count differs")
        for field, value in frozen["native_assistant_usage"].items():
            if observation[0]["usage"].get(field) != value:
                raise ValueError(f"Native usage differs: {field}")
        if actual["upstream_usage_present"] != frozen["upstream_usage_field_present"]:
            raise ValueError("Source provenance differs")
    if report["results"][0]["native_assistant_observations"][0]["usage"] != report["results"][1]["native_assistant_observations"][0]["usage"]:
        raise ValueError("Native zero shapes differ")
    print(json.dumps({"state": "SOURCE_EVIDENCE_VERIFIED", "run_id": run_id,
                      "product_e2e_executed": False, "valid_provider_zero_proven": False}))


if __name__ == "__main__":
    main()
