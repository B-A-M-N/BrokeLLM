#!/usr/bin/env python3
"""Bridge localhost TCP traffic to a Unix domain socket for strict sandbox mode."""

import os
import select
import socket
import sys
import threading

IDLE_TIMEOUT_SECONDS = 30
MAX_CONCURRENT_CLIENTS = 8
CLIENT_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_CLIENTS)


def pump(src, dst):
    idle_ticks = 0
    try:
        while True:
            ready, _, _ = select.select([src], [], [], 1.0)
            if not ready:
                idle_ticks += 1
                if idle_ticks >= IDLE_TIMEOUT_SECONDS:
                    break
                continue
            idle_ticks = 0
            chunk = src.recv(65536)
            if not chunk:
                break
            dst.sendall(chunk)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def handle_client(client_sock, unix_socket_path):
    acquired = CLIENT_SLOTS.acquire(blocking=False)
    if not acquired:
        try:
            client_sock.close()
        finally:
            return
    upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client_sock.settimeout(IDLE_TIMEOUT_SECONDS)
        upstream.settimeout(IDLE_TIMEOUT_SECONDS)
        upstream.connect(unix_socket_path)
    except OSError:
        client_sock.close()
        upstream.close()
        CLIENT_SLOTS.release()
        return

    threads = [
        threading.Thread(target=pump, args=(client_sock, upstream), daemon=True),
        threading.Thread(target=pump, args=(upstream, client_sock), daemon=True),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    client_sock.close()
    upstream.close()
    CLIENT_SLOTS.release()


def main():
    listen_port = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    unix_socket_path = sys.argv[2] if len(sys.argv) > 2 else ""
    if not unix_socket_path:
        raise SystemExit("usage: _socket_bridge.py <listen_port> <unix_socket_path>")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", listen_port))
    server.listen(32)
    try:
        while True:
            client_sock, _addr = server.accept()
            threading.Thread(target=handle_client, args=(client_sock, unix_socket_path), daemon=True).start()
    finally:
        server.close()


if __name__ == "__main__":
    main()
