#!/usr/bin/env python3
import csv
from pathlib import Path
import matplotlib.pyplot as plt

PAYLOADS = [64, 512, 1024, 4096, 8192]
CLIENTS_LIST = [1, 10]
REQUESTS = 200

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
PLOTS_DIR = BASE_DIR / "plots"
PLOTS_DIR.mkdir(exist_ok=True)

def percentile(values, q: float) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    k = int(round((q / 100.0) * (len(xs) - 1)))
    return xs[k]

def read_tcp_rtts(path: Path):
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
    return vals

def read_udp_rtts(sent_path: Path, recv_path: Path):
    sent = {}
    with sent_path.open("r", newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)
        for row in rd:
            if len(row) >= 3:
                try:
                    sent[(int(row[0]), int(row[1]))] = float(row[2])
                except ValueError:
                    pass

    rtts = []
    with recv_path.open("r", newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        next(rd, None)
        for row in rd:
            if len(row) >= 3:
                try:
                    key = (int(row[0]), int(row[1]))
                    rt = float(row[2])
                except ValueError:
                    continue
                st = sent.get(key)
                if st is not None:
                    rtt = rt - st
                    if rtt >= 0:
                        rtts.append(rtt)
    return rtts

def collect_percentiles(q):
    data = {
        ("tcp", 1): [],
        ("tcp", 10): [],
        ("udp", 1): [],
        ("udp", 10): [],
    }

    for c in CLIENTS_LIST:
        for p in PAYLOADS:
            # TCP
            tcp_path = RESULTS_DIR / f"tcp_rtt_c{c}_r{REQUESTS}_p{p}.csv"
            if tcp_path.exists():
                vals = read_tcp_rtts(tcp_path)
                data[("tcp", c)].append(percentile(vals, q))
            else:
                data[("tcp", c)].append(float("nan"))

            # UDP
            sent_path = RESULTS_DIR / f"udp_sent_c{c}_r{REQUESTS}_p{p}.csv"
            recv_path = RESULTS_DIR / f"udp_recv_c{c}_r{REQUESTS}_p{p}.csv"
            if sent_path.exists() and recv_path.exists():
                vals = read_udp_rtts(sent_path, recv_path)
                data[("udp", c)].append(percentile(vals, q))
            else:
                data[("udp", c)].append(float("nan"))

    return data

def plot_graph(data, q_label):
    plt.figure()

    plt.plot(PAYLOADS, data[("tcp", 1)], marker="o", label="TCP c=1")
    plt.plot(PAYLOADS, data[("udp", 1)], marker="o", label="UDP c=1")
    plt.plot(PAYLOADS, data[("tcp", 10)], marker="o", label="TCP c=10")
    plt.plot(PAYLOADS, data[("udp", 10)], marker="o", label="UDP c=10")

    plt.xlabel("payload_bytes")
    plt.ylabel(f"RTT {q_label} (seconds)")
    plt.title(f"Latency {q_label} vs Payload (requests=200)")
    plt.legend()
    plt.tight_layout()

    out_path = PLOTS_DIR / f"latency_{q_label}_vs_payload_r200.png"
    plt.savefig(out_path, dpi=200)
    print(f"Wrote {out_path}")

def main():
    if not RESULTS_DIR.exists():
        print("ERROR: results/ not found.")
        return

    print("Generating p50 graph...")
    data_p50 = collect_percentiles(50)
    plot_graph(data_p50, "p50")

    print("Generating p95 graph...")
    data_p95 = collect_percentiles(95)
    plot_graph(data_p95, "p95")

if __name__ == "__main__":
    main()