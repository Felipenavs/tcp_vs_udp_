#!/usr/bin/env python3
"""
TCP/UDP echo client boilerplate.
"""
import argparse
import json
import time
import socket
import threading
from typing import List

##### helper functions #####
def now_wall() -> float:
    return time.time()

def now_mono() -> float:
    return time.monotonic()

def log_event(fp, event: dict):
    fp.write(json.dumps(event, sort_keys=True) + "\n")
    fp.flush()

def recv_exact(conn: socket.socket, n: int) -> bytes:
    """Receive exactly n bytes from a TCP stream (or b'' if the server closes)."""
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return b""
        buf.extend(chunk)
    return bytes(buf)

##### Required functions to implement. Do not change signatures. #####
def run_tcp_client(host: str, port: int, log_path: str,
                   payload_bytes: int, requests: int, clients: int) -> None:
    """Run the TCP client benchmark."""
    payload = b"x" * payload_bytes

    lock = threading.Lock()
    all_rtts: List[float] = []
    all_conn_setup: List[float] = []
    errors: List[str] = []

    def client_worker(client_id: int):
        nonlocal all_rtts, all_conn_setup, errors

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # Measure TCP connection setup time (handshake)
                t0 = now_mono()
                s.connect((host, port))
                t1 = now_mono()
                conn_setup = t1 - t0

                local_rtts: List[float] = []

                for req_i in range(requests):
                    start = now_mono()
                    s.sendall(payload)

                    echoed = recv_exact(s, payload_bytes)
                    end = now_mono()

                    if not echoed:
                        raise RuntimeError("Server closed connection early.")
                    if len(echoed) != payload_bytes:
                        raise RuntimeError(f"Expected {payload_bytes} bytes, got {len(echoed)} bytes.")

                    local_rtts.append(end - start)

                with lock:
                    all_conn_setup.append(conn_setup)
                    all_rtts.extend(local_rtts)

        except Exception as e:
            with lock:
                errors.append(f"client_id={client_id}: {repr(e)}")

    # Start overall timer for throughput and time-to-finish
    wall_start = now_wall()
    mono_start = now_mono()

    threads = []
    for cid in range(clients):
        t = threading.Thread(target=client_worker, args=(cid,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    mono_end = now_mono()
    wall_end = now_wall()

    elapsed = mono_end - mono_start

    # Compute throughput 
    total_requests_completed = len(all_rtts)
    total_bytes = total_requests_completed * payload_bytes * 2
    throughput_Bps = total_bytes / elapsed if elapsed > 0 else 0.0

    # Write logs
    with open(log_path, "w") as fp:

        log_event(fp, {
            "event": "run_start",
            "proto": "tcp",
            "host": host,
            "port": port,
            "payload_bytes": payload_bytes,
            "requests": requests,
            "clients": clients,
            "ts": wall_start
        })

        # Per-request RTT logs 
        for rtt in all_rtts:
            log_event(fp, {
                "event": "rtt",
                "proto": "tcp",
                "payload_bytes": payload_bytes,
                "rtt_s": rtt
            })

        # Connection setup logs
        for cs in all_conn_setup:
            log_event(fp, {
                "event": "conn_setup",
                "proto": "tcp",
                "conn_setup_s": cs
            })

        # Summary
        log_event(fp, {
            "event": "run_end",
            "proto": "tcp",
            "elapsed_s": elapsed,
            "total_requests_completed": total_requests_completed,
            "total_bytes": total_bytes,
            "throughput_Bps": throughput_Bps,
            "errors": errors,
            "ts": wall_end
        })

def run_udp_client(host: str, port: int, log_path: str,
                   payload_bytes: int, requests: int, clients: int) -> None:
    """Run the UDP client benchmark."""
    pass

def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    p = argparse.ArgumentParser(description="TCP/UDP echo client for benchmarking")
    p.add_argument("--proto", choices=["tcp", "udp"], required=True)
    p.add_argument("--host", required=True)
    p.add_argument("--port", type=int, default=5001)
    p.add_argument("--payload-bytes", type=int, default=64)
    p.add_argument("--requests", type=int, default=1)
    p.add_argument("--clients", type=int, default=1)
    p.add_argument("--log", required=True)
    return p.parse_args()

def main() -> None:
    """Entry point."""
    args = parse_args()
    if args.proto == "tcp":
        run_tcp_client(args.host, args.port, args.log,
                       args.payload_bytes, args.requests, args.clients)
    else:
        run_udp_client(args.host, args.port, args.log,
                       args.payload_bytes, args.requests, args.clients)

if __name__ == "__main__":
    main()
