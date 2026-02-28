#!/usr/bin/env python3
"""
TCP/UDP echo server boilerplate.
"""

import argparse
import os
import socket
import threading
import json
import time


#### helper functions #####
def now_wall() -> float:
    return time.time()


def now_mono() -> float:
    return time.monotonic()


def log_event(fp, event: dict):
    fp.write(json.dumps(event, sort_keys=True) + "\n")
    fp.flush()


def recv_exact_tcp(conn: socket.socket, n: int) -> bytes:
    """Receive exactly n bytes from a TCP stream (or b'' if the client closes)."""
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:          # client closed connection
            return b""
        buf.extend(chunk)
    return bytes(buf)

def handle_client_tcp(conn: socket.socket, addr, payload_bytes: int, requests: int):
    """Handle one TCP connection: receive+echo payload_bytes, repeated 'requests' times."""
    with conn:
        for i in range(requests):
            data = recv_exact_tcp(conn, payload_bytes)
            if not data:
                # client closed early
                break

            conn.sendall(data)  # echo back to client


##### Required functions to implement. Do not change signatures. #####
def run_tcp_server(bind: str, port: int, log_path: str,
                   payload_bytes: int, requests: int, clients: int) -> None:

    """Run the TCP server benchmark."""
    # server start timestamp
    start_ts = now_wall()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((bind, port))
        server_socket.listen(socket.SOMAXCONN)
        print(f"[TCP] Server listening on {bind}:{port}")

        threads = []
        for _ in range(clients):
            conn, addr = server_socket.accept()
            t = threading.Thread(
                target=handle_client_tcp,
                args=(conn, addr, payload_bytes, requests),
                daemon=True
            )
            t.start()
            threads.append(t)

        # Wait for all clients to finish
        for t in threads:
            t.join()
    
    # server end timestamp
    finish_ts = now_wall()

    os.makedirs(log_path, exist_ok=True)
    filename = os.path.join(log_path, f"tcp_server_c{clients}_r{requests}_p{payload_bytes}.jsonl")
    with open(filename, "w") as fp:
        log_event(fp, {
            "event": "server_run",
            "proto": "tcp",
            "bind": bind,
            "port": port,
            "payload_bytes": payload_bytes,
            "requests": requests,
            "clients": clients,
            "server_start": start_ts,
            "server_end": finish_ts,
            "elapsed": finish_ts - start_ts
        })


def run_udp_server(bind: str, port: int, log_path: str,
                   payload_bytes: int, requests: int, clients: int) -> None:
    
    """Run the UDP server benchmark."""
    #server start timestamp
    start_ts = now_wall()

    # open UDP socket and bind
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((bind, port))

        print(f"[UDP] Server listening on {bind}:{port}")

        # buffer size greater than max UDP to avoid truncation
        BUF_SIZE = 65535
        try:
            while True:
                data, addr = server_socket.recvfrom(BUF_SIZE)
                #echo back to client
                server_socket.sendto(data, addr)

        # Handle server shutdown on Ctrl+C
        except KeyboardInterrupt:
            print("\n[UDP] Server shutting down...")

    #server end timestamp
    finish_ts = now_wall()
    
    os.makedirs(log_path, exist_ok=True)
    filename = os.path.join(log_path, f"udp_server_c{clients}_r{requests}_p{payload_bytes}.jsonl")
    with open(filename, "w") as fp:
        log_event(fp, {
            "event": "server_run",
            "proto": "udp",
            "bind": bind,
            "port": port,
            "payload_bytes": payload_bytes,
            "requests": requests,
            "clients": clients,
            "server_start": start_ts,
            "server_end": finish_ts,
            "elapsed": finish_ts - start_ts
        })


def parse_args() -> argparse.Namespace:
    """Parse CLI args.

    Required flags:
    - --proto tcp|udp
    - --bind
    - --port
    - --payload-bytes
    - --requests
    - --clients
    - --log
    """
    p = argparse.ArgumentParser(description="TCP/UDP echo server for benchmarking")
    p.add_argument("--proto", choices=["tcp", "udp"], required=True)
    p.add_argument("--bind", default="0.0.0.0")
    p.add_argument("--port", type=int, default=5001)
    p.add_argument("--payload-bytes", type=int, default=1)
    p.add_argument("--requests", type=int, default=1)
    p.add_argument("--clients", type=int, default=1)
    p.add_argument("--log", required=True)
    return p.parse_args()


def main() -> None:
    """Entry point."""

    args = parse_args()
    if args.proto == "tcp":
        run_tcp_server(args.bind, args.port, args.log, args.payload_bytes, args.requests, args.clients)
    else:
        run_udp_server(args.bind, args.port, args.log, args.payload_bytes, args.requests, args.clients)
    pass


if __name__ == "__main__":
    main()
