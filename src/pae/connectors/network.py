"""Database egress validation with DNS and private-address protections."""

from __future__ import annotations

import asyncio
import ipaddress
import socket

from pae.persistence.errors import DatabaseHostRejected


class DatabaseNetworkPolicy:
    def __init__(self, allowed_hosts: tuple[str, ...], *, allow_private_hosts: bool) -> None:
        self.allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self.allow_private_hosts = allow_private_hosts

    async def validate(self, host: str, port: int) -> None:
        normalized = host.lower().rstrip(".")
        explicitly_allowed = normalized in self.allowed_hosts
        if self.allowed_hosts and not explicitly_allowed:
            raise DatabaseHostRejected(
                "The database host is not in the configured allowlist.",
                details={"host": "***"},
            )
        try:
            addresses = await asyncio.to_thread(
                socket.getaddrinfo, normalized, port, type=socket.SOCK_STREAM
            )
        except socket.gaierror as exc:
            raise DatabaseHostRejected("The database host could not be resolved.") from exc
        if not addresses:
            raise DatabaseHostRejected("The database host did not resolve to an address.")
        for address in {item[4][0] for item in addresses}:
            ip = ipaddress.ip_address(address)
            blocked = not ip.is_global
            if blocked and not (self.allow_private_hosts and explicitly_allowed):
                raise DatabaseHostRejected(
                    "The database host resolves to a private or reserved network address.",
                    details={"host": "***"},
                )
