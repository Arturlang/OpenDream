"""Minimal BYOND world Topic client (the protocol both DreamDaemon and OpenDream's topic port speak)."""
import socket, struct


def topic(port, query, host="127.0.0.1", timeout=15.0):
    """Sends "?query" to /world/Topic and returns the reply: str, float, or None for no data."""
    if not query.startswith("?"):
        query = "?" + query
    body = b"\x00" * 5 + query.encode("utf-8") + b"\x00"
    packet = b"\x00\x83" + struct.pack(">H", len(body)) + body
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(packet)
        head = _read(s, 4)
        if head[:2] != b"\x00\x83":
            raise IOError(f"bad topic reply header {head!r}")
        size = struct.unpack(">H", head[2:])[0]
        data = _read(s, size)
    kind, payload = data[0], data[1:]
    if kind == 0x06:
        return payload.rstrip(b"\x00").decode("utf-8", errors="backslashreplace")
    if kind == 0x2A:
        return struct.unpack("<f", payload[:4])[0]
    return None


def _read(s, n):
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise IOError("topic connection closed early")
        buf += chunk
    return buf
