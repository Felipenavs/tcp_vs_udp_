#!/usr/bin/env python3
import csv
import statistics
from pathlib import Path
import matplotlib.pyplot as plt

PAYLOADS = [64, 512, 1024, 4096, 8192]
CLIENTS = 1
REQUESTS = 1

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
PLOTS_DIR = BASE_DIR / "plots"
PLOTS_DIR.mkdir(exist_ok=True)

def read_first_tcp_rtt(path: Path) -> float:
    # header: client_id,request_index,rtt_s
    with path.open("r", newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)  # header
        row = next(rd, None)
        if not row or len(row) < 3:
            raise ValueError(f"No RTT rows in {path.name}")
        return float(row[2])

def read_avg_tcp_conn_setup(path: Path) -> float:
    # header: client_id,conn_setup_s
    vals = []
    with path.open("r", newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)  # header
        for row in rd:
            if len(row) >= 2:
                vals.append(float(row[1]))
    return statistics.mean(vals) if vals else 0.0

def read_udp_single_rtt(sent_path: Path, recv_path: Path) -> float:
    # sent header: cid,seq,send_time_mono
    with sent_path.open("r", newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)
        row = next(rd, None)
        if not row or len(row) < 3:
            raise ValueError(f"No sent rows in {sent_path.name}")
        ts = float(row[2])

    # recv header: cid,seq,recv_time_mono
    with recv_path.open("r", newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)
        row = next(rd, None)
        if not row or len(row) < 3:
            raise ValueError(f"No recv rows in {recv_path.name}")
        rt = float(row[2])

    return max(0.0, rt - ts)

def main():
    print("BASE_DIR   =", BASE_DIR)
    print("RESULTS_DIR=", RESULTS_DIR)
    print("PLOTS_DIR  =", PLOTS_DIR)

    if not RESULTS_DIR.exists():
        print("ERROR: results/ folder not found next to this script.")
        return

    tcp_x, tcp_y = [], []
    udp_x, udp_y = [], []

    print("\n--- Reading points ---")
    for p in PAYLOADS:
        # TCP
        tcp_rtt_path  = RESULTS_DIR / f"tcp_rtt_c{CLIENTS}_r{REQUESTS}_p{p}.csv"
        tcp_conn_path = RESULTS_DIR / f"tcp_conn_c{CLIENTS}_r{REQUESTS}_p{p}.csv"

        if tcp_rtt_path.exists():
            rtt = read_first_tcp_rtt(tcp_rtt_path)
            conn = read_avg_tcp_conn_setup(tcp_conn_path) if tcp_conn_path.exists() else 0.0
            adj = rtt + conn
            tcp_x.append(p); tcp_y.append(adj)
            print(f"TCP p={p}: rtt={rtt:.9f} conn_avg={conn:.9f} plotted={adj:.9f}")
        else:
            print(f"TCP p={p}: MISSING {tcp_rtt_path.name}")

        # UDP 
        udp_sent_path = RESULTS_DIR / f"udp_sent_c{CLIENTS}_r{REQUESTS}_p{p}.csv"
        udp_recv_path = RESULTS_DIR / f"udp_recv_c{CLIENTS}_r{REQUESTS}_p{p}.csv"

        if udp_sent_path.exists() and udp_recv_path.exists():
            rtt = read_udp_single_rtt(udp_sent_path, udp_recv_path)
            udp_x.append(p); udp_y.append(rtt)
            print(f"UDP p={p}: rtt={rtt:.9f} plotted={rtt:.9f} (raw)")
        else:
            miss = []
            if not udp_sent_path.exists(): miss.append(udp_sent_path.name)
            if not udp_recv_path.exists(): miss.append(udp_recv_path.name)
            print(f"UDP p={p}: MISSING {', '.join(miss)}")

    # Plot
    plt.figure()
    if udp_x:
        plt.plot(udp_x, udp_y, marker="o", label="UDP RTT (raw)")
    if tcp_x:
        plt.plot(tcp_x, tcp_y, marker="o", label="TCP RTT (rtt + conn_setup)")

    plt.xlabel("payload_bytes")
    plt.ylabel("rtt_s")
    plt.title("Phase C: RTT vs Payload (c1, r1) — TCP includes conn setup")
    plt.legend()
    plt.tight_layout()

    out_path = PLOTS_DIR / "rtt_s_vs_payload_c1_r1.png"
    plt.savefig(out_path, dpi=200)
    print(f"\nWrote {out_path}")

if __name__ == "__main__":
    main()