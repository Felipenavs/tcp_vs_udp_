#!/usr/bin/env python3
"""
TCP/UDP echo client boilerplate.
"""
import argparse
import json
import os
import time
import socket
import threading
import struct
from typing import List, Dict, Tuple
import csv


##### helper functions #####
def now_wall() -> float:
    return time.time()

def now_mono() -> float:
    return time.monotonic()

def log_event(fp, event: dict):
    fp.write(json.dumps(event, sort_keys=True) + "\n")
    fp.flush()

def recv_exact_tcp(conn: socket.socket, n: int) -> bytes:
    """Receive exactly n bytes from a TCP stream (or b'' if the server closes)."""
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return b""
        buf.extend(chunk)
    return bytes(buf)


HDR = struct.Struct("!II")  # cid, seq
def udp_receiver(udp_sock: socket.socket,
                 payload_bytes: int,
                 expected_replies: int,
                 stop_event: threading.Event,
                 bad_l: int,
                 bad_sm: int) -> List[Tuple[int, int, float]]:
    """
    Receives UDP echoes on the shared socket and records receive timestamps.
    Returns list of tuples: (cid, seq, recv_time_mono)
    """
    recv_ts: List[Tuple[int, int, float]] = []
    idle_timeouts_after_stop = 0

    while True:
        # Stop condition 1: got everything we expect
        if len(recv_ts) >= expected_replies:
            break

        try:
            data, _ = udp_sock.recvfrom(payload_bytes + 1024)
        except socket.timeout:
            if stop_event.is_set():
                idle_timeouts_after_stop += 1
                if idle_timeouts_after_stop >= 5:  # ~1s if timeout is 0.2
                    break
            continue
        except OSError:
            break

        if len(data) < HDR.size:
            bad_sm += 1
            continue
        if len(data) != payload_bytes:
            bad_l += 1
            continue

        cid, seq = HDR.unpack_from(data, 0)
        recv_ts.append((cid, seq, now_mono()))

    return recv_ts

def udp_worker(client_id: int,
               host: str,
               port: int,
               payload_bytes: int,
               requests: int,
               udp_sock: socket.socket,
               send_tup: List[Tuple[int, int, float]],
               send_tup_lock: threading.Lock) -> None:
    if payload_bytes < HDR.size:
        raise ValueError(f"payload_bytes must be >= {HDR.size}")

    filler = b"u" * (payload_bytes - HDR.size)
    local_send_tup: List[Tuple[int, int, float]] = []

    for seq in range(requests):
        payload = HDR.pack(client_id, seq) + filler
        send_time = now_mono()
        udp_sock.sendto(payload, (host, port))
        local_send_tup.append((client_id, seq, send_time))

    # publish this worker's sends
    with send_tup_lock:
        send_tup.extend(local_send_tup)

def run_udp_client(host: str, port: int, log_path: str,
                   payload_bytes: int, requests: int, clients: int) -> None:
    """
    Run UDP client benchmark using ONE shared UDP socket
    Produces two CSVs:
      - <log_path>_sent.csv : cid, seq, send_time_mono
      - <log_path>_recv.csv : cid, seq, recv_time_mono
    """
    expected_replies = clients * requests

    # Global list of per-worker send tup
    send_tup: List[Tuple[int, int, float]] = []
    send_tup_lock = threading.Lock()

    stop_event = threading.Event()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:

        BUF = 16 * 1024 * 1024
        udp_sock.settimeout(0.2)  # lets receiver check stop_event
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUF)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUF)

        # Receiver thread returns a list of tuples: (cid, seq, recv_time_mono)
        recv_holder = [None]  # mutable holder for receiver result since threads can't return

        bad_len = 0
        bad_small = 0
        def receiver_runner():
            recv_holder[0] = udp_receiver(
                udp_sock=udp_sock,
                payload_bytes=payload_bytes,
                expected_replies=expected_replies,
                stop_event=stop_event,
                bad_l=bad_len,
                bad_sm=bad_small
            )

        recv_thread = threading.Thread(target=receiver_runner, daemon=True)
        recv_thread.start()

        wall_start = now_wall()
        mono_start = now_mono()

        # Start workers
        threads = []
        for cid in range(clients):
            t = threading.Thread(
                target=udp_worker,
                args=(cid, host, port, payload_bytes, requests,
                      udp_sock, send_tup, send_tup_lock),
                daemon=True
            )
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        # tell receiver we're done sending (it may still be receiving late replies)
        stop_event.set()
        recv_thread.join()

        mono_end = now_mono()
        wall_end = now_wall()
        elapsed = mono_end - mono_start

    recv_ts: List[Tuple[int, int, float]] = recv_holder[0] or []

    last_recv_time = max((ts for _, _, ts in recv_ts), default=0)
    # output file names

    os.makedirs(log_path, exist_ok=True)
    sent_csv = os.path.join(log_path, f"udp_sent_c{clients}_r{requests}_p{payload_bytes}.csv")
    recv_csv = os.path.join(log_path, f"udp_recv_c{clients}_r{requests}_p{payload_bytes}.csv")
    jsonmeta = os.path.join(log_path, f"udp_meta_c{clients}_r{requests}_p{payload_bytes}.jsonl")

    # Write CSV: sent
    with open(sent_csv, "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["cid", "seq", "send_time_mono"])
        for cid, seq, ts in send_tup:
            w.writerow([cid, seq, ts])

    # Write CSV: recv
    with open(recv_csv, "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["cid", "seq", "recv_time_mono"])
        for cid, seq, ts in recv_ts:
            w.writerow([cid, seq, ts])

    # Write JSON metadata 
    with open(jsonmeta, "w") as fp:
        log_event(fp, {
            "event": "client_run",
            "proto": "udp",
            "host": host,
            "port": port,
            "payload_bytes": payload_bytes,
            "requests": requests,
            "clients": clients,
            "expected_replies": expected_replies,
            "start_ts": wall_start,
            "end_ts": wall_end,
            "elapsed_s": elapsed,
            "lost_replies": expected_replies - len(recv_ts),
            "last_recv_package_ts": last_recv_time,
            "bad_len": bad_len,
            "bad_small": bad_small,
        })




def tcp_client_worker(client_id: int, con_info: tuple, lock: threading.Lock, all_rtts: List[Tuple[int, int, float]], all_conn_setup: List[Tuple[int, float]], errors: List[str]) -> None:

    host, port, requests, payload_bytes = con_info
    payload = b"x" * payload_bytes
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:

            # Measure TCP connection setup
            t0 = now_mono()
            s.connect((host, port))
            t1 = now_mono()
            conn_setup = t1 - t0

            local_rtts: List[Tuple[int, int, float]] = []

            for req_i in range(requests):
                
                start = now_mono()
                s.sendall(payload)
                echoed = recv_exact_tcp(s, payload_bytes)
                end = now_mono()

                if not echoed:
                    raise RuntimeError("Server closed connection early.")
                if len(echoed) != payload_bytes:
                    raise RuntimeError("Incorrect payload size.")

                local_rtts.append((client_id, req_i, end - start))

            with lock:
                all_conn_setup.append((client_id, conn_setup))
                all_rtts.extend(local_rtts)

    except Exception as e:
        with lock:
            errors.append(f"client_id={client_id}: {repr(e)}")


def run_tcp_client(host: str, port: int, log_path: str,
                   payload_bytes: int, requests: int, clients: int) -> None:
    
    """Run the TCP client benchmark (CSV data + JSON metadata)."""
    lock = threading.Lock()
    all_rtts: List[Tuple[int, int, float]] = []      # (cid, req_i, rtt)
    all_conn_setup: List[Tuple[int, float]] = []     # (cid, conn_setup)
    errors: List[str] = []

    conn_info = (host, port, requests, payload_bytes)  # reuse this tuple to avoid passing many args to worker
    # Run timing window
    wall_start = now_wall()
    mono_start = now_mono()

    threads = []
    for cid in range(clients):
        t = threading.Thread(target=tcp_client_worker, args=(cid, conn_info, lock, all_rtts, all_conn_setup, errors), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    mono_end = now_mono()
    wall_end = now_wall()
    elapsed = mono_end - mono_start

    os.makedirs(log_path, exist_ok=True)
    # output file names
    rtt_csv = os.path.join(log_path, f"tcp_rtt_c{clients}_r{requests}_p{payload_bytes}.csv")
    conn_csv = os.path.join(log_path, f"tcp_conn_c{clients}_r{requests}_p{payload_bytes}.csv")
    jsonmeta = os.path.join(log_path, f"tcp_meta_c{clients}_r{requests}_p{payload_bytes}.jsonl")

    # Write RTT CSV 
    with open(rtt_csv, "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["client_id", "request_index", "rtt_s"])
        for row in all_rtts:
            w.writerow(row)

    # Write connection setup CSV 
    with open(conn_csv, "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["client_id", "conn_setup_s"])
        for row in all_conn_setup:
            w.writerow(row)

    # Write JSON metadata
    with open(jsonmeta, "w") as fp:
        log_event(fp, {
            "event": "client_run",
            "proto": "tcp",
            "host": host,
            "port": port,
            "clients": clients,
            "requests": requests,
            "payload_bytes": payload_bytes,
            "start_ts": wall_start,
            "end_ts": wall_end,
            "elapsed": elapsed,
            "total_requests": len(all_rtts),
            "errors": errors,
            
        })


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
