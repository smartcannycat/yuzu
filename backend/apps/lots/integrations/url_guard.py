"""Strict outbound URL validation helpers to prevent SSRF and unsafe redirects."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeExternalUrlError(ValueError):
    """Raised when a parsed or redirected URL violates scheme, host, or IP policy."""


def _host_matches_allowlist(hostname: str, allowed_hosts: frozenset[str]) -> bool:
    host = hostname.rstrip(".").lower()
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts)


def _is_disallowed_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def validate_external_url(
    url: str,
    *,
    allowed_hosts: frozenset[str] | None = None,
    check_dns: bool = False,
    allow_dns_failure: bool = False,
) -> str:
    """Validate that ``url`` is HTTPS, credential-free, allowlisted, and publicly routable."""
    cleaned = (url or "").strip()
    if not cleaned:
        raise UnsafeExternalUrlError("External URL is empty")
    try:
        parsed = urlparse(cleaned)
    except ValueError as exc:
        raise UnsafeExternalUrlError(f"Malformed external URL: {cleaned}") from exc
    if parsed.scheme.lower() != "https":
        raise UnsafeExternalUrlError(f"Disallowed URL scheme: {parsed.scheme!r}")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeExternalUrlError("Credentials in external URL are disallowed")
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise UnsafeExternalUrlError("External URL has no hostname")

    try:
        ip_literal = ipaddress.ip_address(hostname)
    except ValueError:
        ip_literal = None

    if ip_literal is not None and _is_disallowed_ip(ip_literal):
        raise UnsafeExternalUrlError(f"Disallowed IP target: {hostname!r}")

    if allowed_hosts is not None and not _host_matches_allowlist(hostname, allowed_hosts):
        raise UnsafeExternalUrlError(f"External host is not allowlisted: {hostname!r}")

    if check_dns and ip_literal is None:
        port = parsed.port or 443
        try:
            infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            if allow_dns_failure:
                return cleaned
            raise UnsafeExternalUrlError(f"Could not resolve external host {hostname!r}") from exc
        for _family, _socktype, _proto, _canonname, sockaddr in infos:
            addr_text = sockaddr[0].split("%", 1)[0]
            try:
                resolved_ip = ipaddress.ip_address(addr_text)
            except ValueError:
                continue
            if _is_disallowed_ip(resolved_ip):
                raise UnsafeExternalUrlError(
                    f"External host {hostname!r} resolved to disallowed IP {addr_text!r}"
                )

    return cleaned
