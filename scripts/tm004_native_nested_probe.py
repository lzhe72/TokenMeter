#!/usr/bin/env python3
"""Inspect whether Claude 2.1.126 exposes Agent inside an isolated subagent.

The fixed synthetic loopback sequence records native output. Lack of a nested
tool in this one profile does not prove that all nested modes are unsupported.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import threading

from tm004_native_zero_probe import CLI, CLI_SHA256, MODEL, REPO, RUN_ID, Server, sha, sse


def response(message_id: str, blocks: list[dict], stop_reason: str,
             input_tokens: int, output_tokens: int) -> bytes:
    message = {"id": message_id, "type": "message", "role": "assistant", "model": MODEL,
               "content": [], "stop_reason": None, "stop_sequence": None,
               "usage": {"input_tokens": input_tokens, "output_tokens": 1,
                         "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}
    parts = [sse("message_start", {"type": "message_start", "message": message})]
    for index, block in enumerate(blocks):
        if block["type"] == "text":
            start = {"type": "text", "text": ""}
            delta = {"type": "text_delta", "text": block["text"]}
        else:
            start = {"type": "tool_use", "id": block["id"], "name": "Agent", "input": {}}
            delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"], separators=(",", ":"))}
        parts.extend((sse("content_block_start", {"type": "content_block_start", "index": index,
                                                   "content_block": start}),
                      sse("content_block_delta", {"type": "content_block_delta", "index": index,
                                                   "delta": delta}),
                      sse("content_block_stop", {"type": "content_block_stop", "index": index})))
    parts.extend((sse("message_delta", {"type": "message_delta",
                                       "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                                       "usage": {"output_tokens": output_tokens}}),
                  sse("message_stop", {"type": "message_stop"})))
    return b"".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--run-id")
    action.add_argument("--verify-run-id")
    args = parser.parse_args()
    if args.verify_run_id:
        verify_existing(args.verify_run_id)
        return
    if not RUN_ID.fullmatch(args.run_id) or sha(CLI.read_bytes()) != CLI_SHA256:
        raise ValueError("Invalid run ID or unexpected Claude binary")
    evidence_parent = REPO / ".local/ci"
    parent = evidence_parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid():
        raise ValueError("Evidence parent not owned")
    evidence = evidence_parent / f"tm004-native-nested-{args.run_id}"
    evidence.mkdir(mode=0o700)
    expected = {"cli_sha256": CLI_SHA256, "source_version": "2.1.126",
                "first_response": "parent Agent tool_use to custom tm004-nested",
                "second_response": "nested Agent tool_use only if child request exposes Agent; otherwise text",
                "valid_nested_support_proven": False, "product_e2e_executed": False}
    expected_path = evidence / "expected-before-run.json"
    expected_path.write_text(json.dumps(expected, indent=2) + "\n")
    expected_path.chmod(0o600)
    root = Path(tempfile.mkdtemp(prefix="tm004-nested-", dir="/private/tmp"))
    root.chmod(0o700)
    marker = root / ".tm004-owner.json"
    marker.write_text(json.dumps({"run_id": args.run_id}))
    marker.chmod(0o600)
    config = root / "config"
    config.mkdir(mode=0o700)
    agent_dir = config / "agents"
    agent_dir.mkdir(mode=0o700)
    definition = agent_dir / "tm004-nested.md"
    definition.write_text("---\nname: tm004-nested\ndescription: Synthetic nested Agent availability probe\ntools:\n  - Agent\nmaxTurns: 3\n---\nDelegate one tiny subtask using Agent if the tool is available, then reply SYNTHETIC_SUB_DONE.\n")
    definition.chmod(0o600)
    requests: list[dict] = []
    nested_exposed = False

    class Handler(__import__("http.server").server.BaseHTTPRequestHandler):
        def do_POST(self):
            nonlocal nested_exposed
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            body = json.loads(raw)
            tools = [item.get("name") for item in body.get("tools", [])]
            index = len(requests)
            requests.append({"index": index, "path": self.path, "body_sha256": sha(raw),
                             "agent_tool_exposed": "Agent" in tools})
            if index == 0:
                item = response("msg_tm004_nested_parent_tool", [{"type": "tool_use", "id": "toolu_tm004_parent",
                    "input": {"description": "Synthetic nested probe", "prompt": "Delegate one tiny subtask, then answer SYNTHETIC_SUB_DONE.",
                              "subagent_type": "tm004-nested"}}], "tool_use", 17, 5)
            elif index == 1:
                nested_exposed = "Agent" in tools
                item = (response("msg_tm004_nested_child_tool", [{"type": "tool_use", "id": "toolu_tm004_child",
                         "input": {"description": "Synthetic leaf", "prompt": "Reply SYNTHETIC_LEAF_DONE.",
                                   "subagent_type": "general-purpose"}}], "tool_use", 19, 6)
                        if nested_exposed else response("msg_tm004_nested_child_no_tool",
                                                      [{"type": "text", "text": "SYNTHETIC_SUB_NO_AGENT"}], "end_turn", 19, 6))
            elif index == 2 and nested_exposed:
                item = response("msg_tm004_nested_leaf", [{"type": "text", "text": "SYNTHETIC_LEAF_DONE"}], "end_turn", 11, 3)
            elif (index == 2 and not nested_exposed) or (index == 4 and nested_exposed):
                item = response("msg_tm004_nested_parent_final", [{"type": "text", "text": "SYNTHETIC_PARENT_DONE"}], "end_turn", 23, 7)
            elif index == 3 and nested_exposed:
                item = response("msg_tm004_nested_child_final", [{"type": "text", "text": "SYNTHETIC_SUB_DONE"}], "end_turn", 13, 4)
            else:
                item = b'{"error":{"type":"not_found_error","message":"synthetic sequence exhausted"}}'
            self.send_response(200 if index <= (4 if nested_exposed else 2) else 404)
            self.send_header("Content-Type", "text/event-stream" if index <= (4 if nested_exposed else 2) else "application/json")
            self.send_header("Content-Length", str(len(item)))
            self.end_headers()
            self.wfile.write(item)

        def log_message(self, *_):
            pass

    try:
        with Server(("127.0.0.1", 0), Handler) as server:
            port = server.server_address[1]
            profile = root / "probe.sb"
            profile.write_text("(version 1)\n(allow default)\n(deny network-outbound)\n"
                               f'(allow network-outbound (remote ip "localhost:{port}"))\n'
                               f'(deny file-read* (subpath "{Path.home()}"))\n'
                               f'(deny file-write* (subpath "{Path.home()}"))\n'
                               '(deny file-read* (subpath "/Users/Shared"))\n'
                               '(deny file-write* (subpath "/Users/Shared"))\n')
            profile.chmod(0o600)
            env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "CLAUDE_CONFIG_DIR": str(config),
                   "TMPDIR": str(root), "ANTHROPIC_API_KEY": "tm004-synthetic-fake-key",
                   "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
                   "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_TELEMETRY": "1",
                   "DISABLE_UPDATES": "1", "NO_PROXY": "127.0.0.1,localhost"}
            command = ["/usr/bin/sandbox-exec", "-f", str(profile), str(CLI), "-p",
                       "TM004 synthetic nested Agent probe: delegate to tm004-nested, then answer.",
                       "--model", MODEL, "--output-format", "json", "--max-turns", "5", "--tools", "Agent"]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                try:
                    completed = subprocess.run(command, env=env, cwd=root, capture_output=True,
                                               text=True, timeout=50, check=False)
                    exit_code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
                except subprocess.TimeoutExpired as error:
                    exit_code = "timeout"
                    stdout = (error.stdout or b"").decode(errors="replace")
                    stderr = (error.stderr or b"").decode(errors="replace")
            finally:
                server.shutdown()
                thread.join(timeout=5)
        for name, content in (("stdout", stdout), ("stderr", stderr)):
            path = evidence / f"{name}.txt"
            path.write_text(content)
            path.chmod(0o600)
        native = []
        for path in config.rglob("*.jsonl"):
            if path.is_symlink() or path.stat().st_uid != os.getuid():
                raise ValueError("Unexpected native file ownership")
            data = path.read_bytes()
            copy = evidence / f"native-{len(native)}.jsonl"
            copy.write_bytes(data)
            copy.chmod(0o600)
            native.append({"file": copy.name, "sha256": sha(data), "bytes": len(data),
                           "agent_rows": sum(1 for line in data.splitlines() if json.loads(line).get("isSidechain")),
                           "fork_context_refs": sum(1 for line in data.splitlines() if json.loads(line).get("type") == "fork-context-ref")})
        report = {"state": "SOURCE_OBSERVED" if exit_code == 0 else "BLOCKED",
                  "scope": "isolated_synthetic_cli_source_research", "cli_sha256": CLI_SHA256,
                  "product_e2e_executed": False, "nested_agent_tool_exposed_in_child_request": nested_exposed,
                  "nested_agent_native_supported": nested_exposed and len(native) >= 3 and exit_code == 0,
                  "requests": requests, "cli_exit": exit_code, "native_files": native,
                  "stdout_sha256": sha(stdout.encode()), "stderr_sha256": sha(stderr.encode())}
        result = evidence / "result.json"
        result.write_text(json.dumps(report, indent=2) + "\n")
        result.chmod(0o600)
        print(json.dumps({"state": report["state"], "evidence": str(result.relative_to(REPO)),
                          "request_count": len(requests), "nested_agent_tool_exposed_in_child_request": nested_exposed,
                          "native_files": len(native)}))
    finally:
        if root.is_symlink() or not root.is_dir() or root.stat().st_uid != os.getuid() or not marker.is_file():
            raise ValueError("Private root changed; refusing cleanup")
        for path in root.rglob("*"):
            if path.is_symlink() or path.lstat().st_uid != os.getuid():
                raise ValueError("Private root contains non-owned/link entry; refusing cleanup")
        shutil.rmtree(root)


def verify_existing(run_id: str) -> None:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid run ID")
    expected = json.loads((REPO / "tests/fixtures/tm004/nested-agent-availability-2.1.126.json").read_text())
    if run_id != expected["research_run_id"]:
        raise ValueError("Requested run does not match fixed source fixture")
    evidence = REPO / ".local/ci" / f"tm004-native-nested-{run_id}"
    info = evidence.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or evidence.is_symlink():
        raise ValueError("Research evidence directory not owned")
    report = json.loads((evidence / "result.json").read_text())
    if (report["state"] != "SOURCE_OBSERVED" or report["cli_sha256"] != expected["cli_binary_sha256"]
            or report["nested_agent_native_supported"] or report["product_e2e_executed"]
            or len(report["requests"]) != expected["request_count"]):
        raise ValueError("Research result differs")
    if [row["agent_tool_exposed"] for row in report["requests"]] != expected["agent_tool_exposed_by_request"]:
        raise ValueError("Request tool availability differs")
    if len(report["native_files"]) != len(expected["native_jsonl_sha256"]):
        raise ValueError("Native file count differs")
    for row, digest in zip(report["native_files"], expected["native_jsonl_sha256"], strict=True):
        path = evidence / row["file"]
        if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != digest or row["sha256"] != digest:
            raise ValueError("Native original missing or changed")
    if report["native_files"][1]["agent_rows"] != expected["child_native_agent_rows"] or sum(
            row["fork_context_refs"] for row in report["native_files"]) != expected["fork_context_refs"]:
        raise ValueError("Native structure differs")
    print(json.dumps({"state": "SOURCE_EVIDENCE_VERIFIED", "run_id": run_id,
                      "nested_agent_native_supported": False, "product_e2e_executed": False}))


if __name__ == "__main__":
    main()
