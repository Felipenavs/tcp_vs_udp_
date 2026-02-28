#!/usr/bin/env python3
import argparse
import subprocess
import time
import signal
import sys



def main():
    parser = argparse.ArgumentParser()

    # Required flags (same as your project)
    parser.add_argument("--proto", required=True, choices=["tcp", "udp"])
    parser.add_argument("--bind", required=True)     # server only
    parser.add_argument("--host", required=True)     # client only
    parser.add_argument("--port", required=True)
    parser.add_argument("--payload-bytes", required=True)
    parser.add_argument("--requests", required=True)
    parser.add_argument("--clients", required=True)
    parser.add_argument("--log", required=True)

    args = parser.parse_args()

    # Split log names
    server_log = f"server_{args.log}"
    client_log = f"client_{args.log}"

    # Start server
    server_cmd = [
        "python3", "server.py",
        "--proto", args.proto,
        "--bind", args.bind,
        "--port", args.port,
        "--payload-bytes", args.payload_bytes,
        "--log", args.log,
        "--requests", args.requests,
        "--clients", args.clients,
    ]

    server_proc = subprocess.Popen(server_cmd)

    # Give server time to start
    time.sleep(1)

    # Run client
    client_cmd = [
        "python3", "client.py",
        "--proto", args.proto,
        "--host", args.host,
        "--port", args.port,
        "--payload-bytes", args.payload_bytes,
        "--requests", args.requests,
        "--clients", args.clients,
        "--log", args.log,
    ]

    client_rc = subprocess.call(client_cmd)

    # Stop server
    server_proc.send_signal(signal.SIGINT)
    server_proc.wait()

    sys.exit(client_rc)


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
# from __future__ import annotations
# import argparse
# import shlex
# import subprocess
# import time
# from pathlib import Path
# from typing import List

# ROOT = Path(__file__).resolve().parent
# RESULTS_DIR = ROOT / "results"
# PLOTS_DIR = ROOT / "plots"


# # ---------------------------
# # shell helpers
# # ---------------------------

# def _run(cmd: List[str], *, check: bool = True) -> subprocess.CompletedProcess:
#     print(">>", " ".join(shlex.quote(x) for x in cmd))
#     return subprocess.run(cmd, check=check)

# def _ssh_cmd(user: str, host: str, ssh_opts: List[str], remote_cmd: str) -> List[str]:
#     return ["ssh", *ssh_opts, f"{user}@{host}", remote_cmd]

# def _ssh(user: str, host: str, ssh_opts: List[str], remote_cmd: str, *, check: bool = True):
#     return _run(_ssh_cmd(user, host, ssh_opts, remote_cmd), check=check)

# def _ssh_capture(user: str, host: str, ssh_opts: List[str], remote_cmd: str) -> str:
#     cmd = _ssh_cmd(user, host, ssh_opts, remote_cmd)
#     print(">>", " ".join(shlex.quote(x) for x in cmd))
#     out = subprocess.check_output(cmd)
#     return out.decode("utf-8", errors="replace")

# def remote_expand_path(user: str, host: str, ssh_opts: List[str], path_expr: str) -> str:
#     """
#     Expand a *remote* path expression like:
#       ~/tcp_udp_benchmark
#       $HOME/tcp_udp_benchmark
#     into an absolute path on that remote host.

#     We do this remotely to avoid local shell expansion bugs.
#     """
#     # eval echo expands ~ and $HOME on the remote side
#     # shellcheck: we quote path_expr safely into the remote command
#     remote_cmd = "bash -lc " + shlex.quote(f"eval echo {shlex.quote(path_expr)}")
#     expanded = _ssh_capture(user, host, ssh_opts, remote_cmd).strip()
#     if not expanded:
#         raise RuntimeError(f"Failed to expand remote path expression: {path_expr} on {host}")
#     return expanded

# def rsync_to(user: str, host: str, ssh_opts: List[str], local_dir: Path, remote_dir_abs: str, excludes: List[str]):
#     _ssh(user, host, ssh_opts, "bash -lc " + shlex.quote(f"mkdir -p {shlex.quote(remote_dir_abs)}"))

#     rsync_cmd = ["rsync", "-az", "--delete"]
#     for ex in excludes:
#         rsync_cmd += ["--exclude", ex]
#     rsync_cmd += ["-e", "ssh " + " ".join(shlex.quote(x) for x in ssh_opts)]
#     rsync_cmd += [str(local_dir) + "/", f"{user}@{host}:{remote_dir_abs}/"]
#     _run(rsync_cmd)

# def rsync_from_dir(user: str, host: str, ssh_opts: List[str], remote_dir_abs: str, local_dest: Path):
#     local_dest.mkdir(parents=True, exist_ok=True)
#     rsync_cmd = [
#         "rsync", "-az",
#         "-e", "ssh " + " ".join(shlex.quote(x) for x in ssh_opts),
#         f"{user}@{host}:{remote_dir_abs}/",
#         str(local_dest) + "/"
#     ]
#     _run(rsync_cmd, check=False)


# # ---------------------------
# # experiment orchestration
# # ---------------------------

# def stop_server_bg(user: str, host: str, ssh_opts: List[str], remote_dir_abs: str) -> None:
#     inner = (
#         f"cd {shlex.quote(remote_dir_abs)} || exit 0; "
#         f"if [ -f .server.pid ]; then "
#         f"  pid=$(cat .server.pid); "
#         f"  kill $pid 2>/dev/null || true; "
#         f"  sleep 0.2; "
#         f"  kill -9 $pid 2>/dev/null || true; "
#         f"  rm -f .server.pid; "
#         f"  echo SERVER_STOPPED; "
#         f"else echo NO_SERVER_PID; fi"
#     )
#     _ssh(user, host, ssh_opts, "bash -lc " + shlex.quote(inner), check=False)

# def start_server_bg(
#     user: str,
#     host: str,
#     ssh_opts: List[str],
#     remote_dir_abs: str,
#     proto: str,
#     bind: str,
#     port: int,
#     payload_bytes: int,
#     requests: int,
#     clients: int,
#     server_log_rel: str,
# ) -> None:
#     # Ensure results dir exists and start server in background
#     inner = (
#         f"cd {shlex.quote(remote_dir_abs)} && "
#         f"mkdir -p results && "
#         f"nohup python3 server.py "
#         f"--proto {shlex.quote(proto)} "
#         f"--bind {shlex.quote(bind)} "
#         f"--port {port} "
#         f"--payload-bytes {payload_bytes} "
#         f"--requests {requests} "
#         f"--clients {clients} "
#         f"--log {shlex.quote(server_log_rel)} "
#         f"> .server.nohup 2>&1 & "
#         f"echo $! > .server.pid && "
#         f"echo SERVER_STARTED pid=$(cat .server.pid)"
#     )
#     _ssh(user, host, ssh_opts, "bash -lc " + shlex.quote(inner))

# def run_client_fg(
#     user: str,
#     host: str,
#     ssh_opts: List[str],
#     remote_dir_abs: str,
#     proto: str,
#     server_host: str,
#     port: int,
#     payload_bytes: int,
#     requests: int,
#     clients: int,
#     client_log_rel: str,
# ) -> None:
#     inner = (
#         f"cd {shlex.quote(remote_dir_abs)} && "
#         f"mkdir -p results && "
#         f"python3 client.py "
#         f"--proto {shlex.quote(proto)} "
#         f"--host {shlex.quote(server_host)} "
#         f"--port {port} "
#         f"--payload-bytes {payload_bytes} "
#         f"--requests {requests} "
#         f"--clients {clients} "
#         f"--log {shlex.quote(client_log_rel)}"
#     )
#     _ssh(user, host, ssh_opts, "bash -lc " + shlex.quote(inner))

# def parse_list_int(s: str) -> List[int]:
#     return [int(tok) for tok in s.replace(",", " ").split() if tok.strip()]


# def main():
#     ap = argparse.ArgumentParser(description="Run TCP/UDP experiments across iLab machines (push -> run -> fetch).")
#     ap.add_argument("--user", required=True)
#     ap.add_argument("--server-host", required=True)
#     ap.add_argument("--client-host", required=True)
#     ap.add_argument("--remote-dir", default="~/tcp_udp_benchmark",
#                     help="REMOTE directory expression (expanded on iLab). Example: ~/tcp_udp_benchmark or $HOME/tcp_udp_benchmark")

#     ap.add_argument("--proto", choices=["tcp", "udp"], required=True)
#     ap.add_argument("--bind", default="0.0.0.0")
#     ap.add_argument("--port", type=int, required=True)

#     ap.add_argument("--payloads", default="64,512,1024,4096,8192")
#     ap.add_argument("--clients-list", default="1,10,100,1000")
#     ap.add_argument("--requests", type=int, default=100)

#     ap.add_argument("--no-push", action="store_true")
#     ap.add_argument("--no-fetch", action="store_true")
#     ap.add_argument("--server-warmup-ms", type=int, default=200)

#     args = ap.parse_args()

#     # SSH options: keep it interactive (Rutgers password/2FA), reduce noise
#     ssh_opts = [
#         "-o", "StrictHostKeyChecking=no",
#         "-o", "UserKnownHostsFile=/dev/null",
#         "-o", "LogLevel=ERROR",
#     ]

#     RESULTS_DIR.mkdir(parents=True, exist_ok=True)
#     PLOTS_DIR.mkdir(parents=True, exist_ok=True)

#     # Expand remote dir *on each host* so we never accidentally use /Users/...
#     remote_dir_server = remote_expand_path(args.user, args.server_host, ssh_opts, args.remote_dir)
#     remote_dir_client = remote_expand_path(args.user, args.client_host, ssh_opts, args.remote_dir)

#     excludes = [".git/", "__pycache__/", "*.pyc", ".DS_Store", "results/", "plots/"]

#     if not args.no_push:
#         print("\n=== PUSH PHASE ===")
#         rsync_to(args.user, args.server_host, ssh_opts, ROOT, remote_dir_server, excludes)
#         if args.client_host != args.server_host:
#             rsync_to(args.user, args.client_host, ssh_opts, ROOT, remote_dir_client, excludes)

#     payloads = parse_list_int(args.payloads)
#     clients_list = parse_list_int(args.clients_list)

#     print("\n=== RUN PHASE ===")
#     for pb in payloads:
#         for cc in clients_list:
#             tag = f"{args.proto}_pb{pb}_c{cc}_r{args.requests}_p{args.port}"
#             server_log = f"results/server_{tag}.jsonl"   # RELATIVE (important)
#             client_log = f"results/client_{tag}.jsonl"   # RELATIVE (important)

#             print(f"\n--- Experiment {tag} ---")

#             stop_server_bg(args.user, args.server_host, ssh_opts, remote_dir_server)

#             start_server_bg(
#                 user=args.user,
#                 host=args.server_host,
#                 ssh_opts=ssh_opts,
#                 remote_dir_abs=remote_dir_server,
#                 proto=args.proto,
#                 bind=args.bind,
#                 port=args.port,
#                 payload_bytes=pb,
#                 requests=args.requests,
#                 clients=cc,
#                 server_log_rel=server_log,
#             )

#             time.sleep(max(0, args.server_warmup_ms) / 1000.0)

#             run_client_fg(
#                 user=args.user,
#                 host=args.client_host,
#                 ssh_opts=ssh_opts,
#                 remote_dir_abs=remote_dir_client,
#                 proto=args.proto,
#                 server_host=args.server_host,
#                 port=args.port,
#                 payload_bytes=pb,
#                 requests=args.requests,
#                 clients=cc,
#                 client_log_rel=client_log,
#             )

#             stop_server_bg(args.user, args.server_host, ssh_opts, remote_dir_server)

#     if not args.no_fetch:
#         print("\n=== FETCH PHASE ===")
#         # Pull results directories from both hosts
#         rsync_from_dir(args.user, args.server_host, ssh_opts, f"{remote_dir_server}/results", RESULTS_DIR / f"from_{args.server_host}")
#         rsync_from_dir(args.user, args.client_host, ssh_opts, f"{remote_dir_client}/results", RESULTS_DIR / f"from_{args.client_host}")

#     print("\nDone.")


# if __name__ == "__main__":
#     main()