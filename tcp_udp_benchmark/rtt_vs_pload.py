#!/usr/bin/env python3
import csv
import statistics
from pathlib import Path
import matplotlib.pyplot as plt

PAYLOADS = [64, 512, 1024, 4096, 8192]
CLIENTS = 1
REQUESTS = 50

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
PLOTS_DIR = BASE_DIR / "plots"
PLOTS_DIR.mkdir(exist_ok=True)

def read_tcp_avg_rtt(path: Path) -> float:
    # header: client_id,request_index,rtt_s
    vals = []
    with path.open("r", newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)
        for row in rd:
            if len(row) >= 3:
                try:
                    vals.append(float(row[2]))
                except ValueError:
                    pass
    if not vals:
        raise ValueError(f"No RTT rows in {path.name}")
    return statistics.mean(vals)

def read_avg_tcp_conn_setup(path: Path) -> float:
    # header: client_id,conn_setup_s
    vals = []
    with path.open("r", newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)
        for row in rd:
            if len(row) >= 2:
                try:
                    vals.append(float(row[1]))
                except ValueError:
                    pass
    return statistics.mean(vals) if vals else 0.0

def read_udp_avg_rtt(sent_path: Path, recv_path: Path) -> float:
    # sent header: cid,seq,send_time_mono
    sent = {}
    with sent_path.open("r", newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)
        for row in rd:
            if len(row) >= 3:
                try:
                    cid = int(row[0]); seq = int(row[1]); ts = float(row[2])
                    sent[(cid, seq)] = ts
                except ValueError:
                    pass

    # recv header: cid,seq,recv_time_mono
    rtts = []
    with recv_path.open("r", newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)
        for row in rd:
            if len(row) >= 3:
                try:
                    cid = int(row[0]); seq = int(row[1]); rt = float(row[2])
                except ValueError:
                    continue
                st = sent.get((cid, seq))
                if st is None:
                    continue
                rtt = rt - st
                if rtt >= 0:
                    rtts.append(rtt)

    if not rtts:
        raise ValueError(f"No matched RTT pairs between {sent_path.name} and {recv_path.name}")
    return statistics.mean(rtts)

def main():
    print("BASE_DIR   =", BASE_DIR)
    print("RESULTS_DIR=", RESULTS_DIR)
    print("PLOTS_DIR  =", PLOTS_DIR)

    if not RESULTS_DIR.exists():
        print("ERROR: results/ folder not found next to this script.")
        return

    tcp_x, tcp_y = [], []
    udp_x, udp_y = [], []

    print("\n--- Reading points (Phase D c1 r50) ---")
    for p in PAYLOADS:
        # TCP
        tcp_rtt_path  = RESULTS_DIR / f"tcp_rtt_c{CLIENTS}_r{REQUESTS}_p{p}.csv"
        tcp_conn_path = RESULTS_DIR / f"tcp_conn_c{CLIENTS}_r{REQUESTS}_p{p}.csv"

        if tcp_rtt_path.exists():
            rtt_avg = read_tcp_avg_rtt(tcp_rtt_path)
            conn_avg = read_avg_tcp_conn_setup(tcp_conn_path) if tcp_conn_path.exists() else 0.0
            plotted = rtt_avg + conn_avg
            tcp_x.append(p); tcp_y.append(plotted)
            print(f"TCP p={p}: avg_rtt={rtt_avg:.9f} conn_avg={conn_avg:.9f} plotted={plotted:.9f}")
        else:
            print(f"TCP p={p}: MISSING {tcp_rtt_path.name}")

        # UDP (raw avg RTT)
        udp_sent_path = RESULTS_DIR / f"udp_sent_c{CLIENTS}_r{REQUESTS}_p{p}.csv"
        udp_recv_path = RESULTS_DIR / f"udp_recv_c{CLIENTS}_r{REQUESTS}_p{p}.csv"

        if udp_sent_path.exists() and udp_recv_path.exists():
            rtt_avg = read_udp_avg_rtt(udp_sent_path, udp_recv_path)
            udp_x.append(p); udp_y.append(rtt_avg)
            print(f"UDP p={p}: avg_rtt={rtt_avg:.9f} plotted={rtt_avg:.9f} (raw)")
        else:
            miss = []
            if not udp_sent_path.exists(): miss.append(udp_sent_path.name)
            if not udp_recv_path.exists(): miss.append(udp_recv_path.name)
            print(f"UDP p={p}: MISSING {', '.join(miss)}")

    # Plot
    plt.figure()
    if udp_x:
        plt.plot(udp_x, udp_y, marker="o", label="UDP RTT (avg, raw)")
    if tcp_x:
        plt.plot(tcp_x, tcp_y, marker="o", label="TCP RTT (avg_rtt + conn_setup)")

    plt.xlabel("payload_bytes")
    plt.ylabel("rtt_s")
    plt.title("RTT vs Payload (clients: 1, requests: 50) — TCP includes conn setup once")
    plt.legend()
    plt.tight_layout()

    out_path = PLOTS_DIR / "rtt_s_vs_payload.png"
    plt.savefig(out_path, dpi=200)
    print(f"\nWrote {out_path}")

if __name__ == "__main__":
    main()