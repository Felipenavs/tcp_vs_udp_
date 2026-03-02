
# TCP vs UDP Performance Benchmark

## Overview

This project benchmarks and compares **TCP and UDP** performance using a custom echo server and client implementation.

The benchmark evaluates performance across varying:

- Payload sizes  
- Number of concurrent clients  
- Number of requests per client  

---

## Requirements

- Python 3.9+
- Linux or macOS
- SSH access (if running distributed tests on remote machines)

---

## How It Works

There are two ways to run experiments:

### Option 1 — Automated Sweep 

The `run_sweep_ilab.sh` script runs a predefined set of tests on remote machines via SSH.

- Must configure username and password
- Remote machines (optional)

---

### Option 2 — Manual Execution

You may also run the server and client scripts directly with custom parameters.

---

## CLI Parameters

### Common Flags (Server and Client)

- `--proto tcp|udp`  
  Selects the protocol.

- `--port <PORT>`  
  TCP/UDP port number.

- `--payload-bytes <BYTES>`  
  Number of bytes per request payload.

- `--clients <N>`  
  Number of concurrent client connections (TCP) or senders (UDP).

- `--requests <N>`  
  Number of requests per client (TCP: per connection).

- `--log <PATH>`  
  Directory where results (CSV/JSON) will be written.

---

### Server-Only Flags

- `--bind <ADDRESS>`  
  Bind address (e.g., `0.0.0.0`).

---

### Client-Only Flags

- `--host <HOSTNAME_OR_IP>`  
  Server hostname or IP address.

---

## Example Usage (Manual Run)

### Start the Server

```bash
python3 server.py \
  --proto tcp \
  --bind 0.0.0.0 \
  --port 9090
  --clients 10
  --requests 50
  --payload-bytes 512 \
  --log results
  -- /
