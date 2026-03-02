#!/usr/bin/env python3
import json
from pathlib import Path
import matplotlib.pyplot as plt

PAYLOAD = 512
CLIENTS_LIST = [10, 20, 40, 80, 120]
REQUESTS = 10

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
PLOTS_DIR = BASE_DIR / "plots"
PLOTS_DIR.mkdir(exist_ok=True)

def read_json_one_line(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        line = f.readline().strip()
        return json.loads(line) if line else {}

def main():
    if not RESULTS_DIR.exists():
        print("ERROR: results/ not found next to script.")
        return

    tcp_x, tcp_y = [], []
    udp_x, udp_y = [], []

    print("--- Success rate vs clients (TCP + UDP) (p=512, r=10) ---")
    for c in CLIENTS_LIST:
        expected_total = c * REQUESTS

        # ---- TCP ----
        tcp_meta_path = RESULTS_DIR / f"tcp_meta_c{c}_r{REQUESTS}_p{PAYLOAD}.json"
        if tcp_meta_path.exists():
            meta = read_json_one_line(tcp_meta_path)
            completed = int(meta.get("total_requests", 0))
            success = completed / expected_total if expected_total > 0 else 0.0
            tcp_x.append(c)
            tcp_y.append(success)
            print(f"TCP c={c:4d} completed={completed:6d}/{expected_total:6d} success_rate={success:.6f}")
        else:
            print(f"TCP missing: {tcp_meta_path.name}")

        # ---- UDP ----
        udp_meta_path = RESULTS_DIR / f"udp_meta_c{c}_r{REQUESTS}_p{PAYLOAD}.json"
        if udp_meta_path.exists():
            meta = read_json_one_line(udp_meta_path)
            expected = int(meta.get("expected_replies", expected_total))
            lost = int(meta.get("lost_replies", 0))
            received = expected - lost
            denom = expected if expected > 0 else expected_total
            success = received / denom if denom > 0 else 0.0
            udp_x.append(c)
            udp_y.append(success)
            print(f"UDP c={c:4d} received={received:6d}/{expected:6d} success_rate={success:.6f}")
        else:
            print(f"UDP missing: {udp_meta_path.name}")

    if not tcp_x and not udp_x:
        print("No points found.")
        return

    plt.figure()
    if udp_x:
        plt.plot(udp_x, udp_y, marker="o", label="UDP success rate")
    if tcp_x:
        plt.plot(tcp_x, tcp_y, marker="o", label="TCP success rate")

    plt.xlabel("clients")
    plt.ylabel("success_rate")
    plt.ylim(0.0, 1.05)
    plt.title(f"Success Rate vs Clients (p{PAYLOAD}, r{REQUESTS})")
    plt.legend()
    plt.tight_layout()

    out_path = PLOTS_DIR / f"success_rate_vs_clients.png"
    plt.savefig(out_path, dpi=200)
    print(f"\nWrote {out_path}")

if __name__ == "__main__":
    main()