#!/usr/bin/env python3
import argparse
import subprocess
import time
import signal
import sys



def main():
    parser = argparse.ArgumentParser()

    # Required flags (same as your project)
    parser.add_argument("--proto", required=True, choices=["tcp", "udp"])
    parser.add_argument("--bind", required=True)     # server only
    parser.add_argument("--host", required=True)     # client only
    parser.add_argument("--port", required=True)
    parser.add_argument("--payload-bytes", required=True)
    parser.add_argument("--requests", required=True)
    parser.add_argument("--clients", required=True)
    parser.add_argument("--log", required=True)

    args = parser.parse_args()

    # Split log names
    server_log = f"server_{args.log}"
    client_log = f"client_{args.log}"

    # Start server
    server_cmd = [
        "python3", "server.py",
        "--proto", args.proto,
        "--bind", args.bind,
        "--port", args.port,
        "--payload-bytes", args.payload_bytes,
        "--log", args.log,
        "--requests", args.requests,
        "--clients", args.clients,
    ]

    server_proc = subprocess.Popen(server_cmd)

    # Give server time to start
    time.sleep(1)

    # Run client
    client_cmd = [
        "python3", "client.py",
        "--proto", args.proto,
        "--host", args.host,
        "--port", args.port,
        "--payload-bytes", args.payload_bytes,
        "--requests", args.requests,
        "--clients", args.clients,
        "--log", args.log,
    ]

    client_rc = subprocess.call(client_cmd)

    # Stop server
    server_proc.send_signal(signal.SIGINT)
    server_proc.wait()

    sys.exit(client_rc)


if __name__ == "__main__":
    main()