import ipaddress
from fastapi import Request
from fastapi_audit.services.audit.request_context import ClientIPAddress


def _extract_ip(raw: str) -> ClientIPAddress | None:
    """
    Parse a single IP from a header or client value.
    Supports IPv4, IPv6, bracketed IPv6, IPv4 with port (host:port).
    """
    s = raw.strip()
    if not s:
        return None

    if s.startswith("["):
        end = s.find("]")
        if end != -1:
            inner = s[1:end]
            try:
                return ipaddress.ip_address(inner)
            except ValueError:
                return None
        return None

    no_zone = s.split("%", 1)[0]
    try:
        return ipaddress.ip_address(no_zone)
    except ValueError:
        pass

    # IPv4 with port (single colon; avoid breaking IPv6)
    if s.count(":") == 1:
        host, _, port = s.partition(":")
        if port.isdigit():
            try:
                return ipaddress.ip_address(host)
            except ValueError:
                pass

    return None


def get_client_ip(request: Request) -> ClientIPAddress | None:
    """
    Extract the client's IP address from a FastAPI Request.

    Checks, in order:
    1. X-Forwarded-For (left-most valid IP)
    2. X-Real-IP
    3. Forwarded (RFC 7239) first for=
    4. request.client.host

    Returns "" only when nothing usable is available.
    """
    headers = request.headers

    x_forwarded_for = headers.get("x-forwarded-for")
    if x_forwarded_for:
        for part in (ip.strip() for ip in x_forwarded_for.split(",")):
            parsed = _extract_ip(part)
            if parsed is not None:
                return parsed

    x_real_ip = headers.get("x-real-ip")
    if x_real_ip:
        parsed = _extract_ip(x_real_ip)
        if parsed is not None:
            return parsed

    forwarded = headers.get("forwarded")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(";")]
        for part in parts:
            if part.lower().startswith("for="):
                val = part[4:].strip().strip('"')
                return _extract_ip(val)

    client = request.client
    if client and client.host:
        return _extract_ip(client.host)

    return None
