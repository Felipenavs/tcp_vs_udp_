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

    xs, ys = [], []

    print("--- UDP loss rate vs clients (payload=512, r=10) ---")
    for c in CLIENTS_LIST:
        meta_path = RESULTS_DIR / f"udp_meta_c{c}_r{REQUESTS}_p{PAYLOAD}.json"
        if not meta_path.exists():
            print(f"Missing: {meta_path.name}")
            continue

        meta = read_json_one_line(meta_path)
        expected = float(meta.get("expected_replies", 0))
        lost = float(meta.get("lost_replies", 0))

        if expected <= 0:
            print(f"Bad expected_replies in {meta_path.name}: {expected}")
            continue

        loss_rate = lost / expected
        xs.append(c)
        ys.append(loss_rate)
        print(f"c={c:4d} expected={int(expected):6d} lost={int(lost):6d} loss_rate={loss_rate:.6f}")

    if not xs:
        print("No UDP points found.")
        return

    plt.figure()
    plt.plot(xs, ys, marker="o")
    plt.xlabel("clients")
    plt.ylabel("udp_loss_rate")
    plt.title(f"UDP Loss Rate vs Clients (p{PAYLOAD}, r{REQUESTS})")
    plt.tight_layout()

    out_path = PLOTS_DIR / f"udp_loss_rate_vs_clients.png"
    plt.savefig(out_path, dpi=200)
    print(f"\nWrote {out_path}")

if __name__ == "__main__":
    main()