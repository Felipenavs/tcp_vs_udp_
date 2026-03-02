#!/usr/bin/env python3
import json
from pathlib import Path
import matplotlib.pyplot as plt

# Throughput run config
PAYLOADS = [64, 512, 1024, 4096, 8192]
CLIENTS = 10
REQUESTS = 100

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
PLOTS_DIR = BASE_DIR / "plots"
PLOTS_DIR.mkdir(exist_ok=True)

def read_json_one_line(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        line = f.readline().strip()
        return json.loads(line) if line else {}

def mbps(bytes_per_s: float) -> float:
    return (bytes_per_s * 8.0) / 1_000_000.0

def main():
    if not RESULTS_DIR.exists():
        print("ERROR: results/ not found next to this script.")
        return

    tcp_x, tcp_y = [], []
    udp_x, udp_y = [], []

    print("--- Throughput vs Payload (c=10, r=100) ---")

    for p in PAYLOADS:
        # ---- TCP ----
        tcp_meta_path = RESULTS_DIR / f"tcp_meta_c{CLIENTS}_r{REQUESTS}_p{p}.json"
        if tcp_meta_path.exists():
            meta = read_json_one_line(tcp_meta_path)
            elapsed = float(meta.get("elapsed", 0.0))
            total_requests = int(meta.get("total_requests", 0))

            if elapsed > 0 and total_requests > 0:
                total_bytes = total_requests * p * 2
                thr_Bps = total_bytes / elapsed
                tcp_x.append(p)
                tcp_y.append(mbps(thr_Bps))
                print(f"TCP p={p:5d} elapsed={elapsed:.6f}s "
                      f"completed={total_requests:6d} "
                      f"throughput={mbps(thr_Bps):.3f} Mbps")
            else:
                print(f"TCP p={p:5d} bad meta values.")
        else:
            print(f"TCP missing: {tcp_meta_path.name}")

        # ---- UDP ----
        udp_meta_path = RESULTS_DIR / f"udp_meta_c{CLIENTS}_r{REQUESTS}_p{p}.json"
        if udp_meta_path.exists():
            meta = read_json_one_line(udp_meta_path)
            elapsed = float(meta.get("elapsed_s", 0.0))
            expected = int(meta.get("expected_replies", 0))
            lost = int(meta.get("lost_replies", 0))
            received = expected - lost

            if elapsed > 0 and received > 0:
                total_bytes = received * p * 2
                thr_Bps = total_bytes / elapsed
                udp_x.append(p)
                udp_y.append(mbps(thr_Bps))
                print(f"UDP p={p:5d} elapsed={elapsed:.6f}s "
                      f"received={received:6d}/{expected:6d} "
                      f"throughput={mbps(thr_Bps):.3f} Mbps")
            else:
                print(f"UDP p={p:5d} bad meta values.")
        else:
            print(f"UDP missing: {udp_meta_path.name}")

    if not tcp_x and not udp_x:
        print("No data found.")
        return

    plt.figure()

    if udp_x:
        plt.plot(udp_x, udp_y, marker="o", label="UDP Throughput (Mbps)")
    if tcp_x:
        plt.plot(tcp_x, tcp_y, marker="o", label="TCP Throughput (Mbps)")

    plt.xlabel("payload_bytes")
    plt.ylabel("throughput (Mbps)")
    plt.title("Throughput vs Payload (clients=10, requests=100)")
    plt.legend()
    plt.tight_layout()

    out_path = PLOTS_DIR / "throughput_vs_payload.png"
    plt.savefig(out_path, dpi=200)

    print(f"\nWrote {out_path}")

if __name__ == "__main__":
    main()