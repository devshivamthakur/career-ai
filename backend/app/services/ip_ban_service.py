"""
IP ban / auto-ban service.

Design goals:
  * Only count clearly-malicious scanner patterns as security violations
    (no more bare substring matching of "admin", "config", etc., which
    collides with legitimate authenticated admin endpoints).
  * Match full path segments, not substrings, so that
    /api/v1/marketplaces/admin does not match /admin.
  * Honour an IP whitelist (manual + per-IP, persisted in Redis).
  * All thresholds/TTLs are read from settings so they can be tuned
    per environment without code changes.

The service uses a shared Redis client (same pattern as rate_limit.py)
for distributed ban tracking across workers.
"""

import ipaddress
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.core.config import settings
from app.core.infrastructure import ServiceConfig
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

class BanReason(str, Enum):
    MANUAL_BAN = "manual"
    RATE_LIMIT_VIOLATIONS = "rate_limit_violations"
    SUSPICIOUS_PATH = "suspicious_path"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class BanInfo:
    ip: str
    reason: str
    banned_at: int
    expires_at: Optional[int] = None
    violations: int = 0


class IPBanService:
    """
    IP ban / auto-ban service.

    Design goals:
      * Only count clearly-malicious scanner patterns as security violations
        (no more bare substring matching of "admin", "config", etc., which
        collides with legitimate authenticated admin endpoints).
      * Match full path segments, not substrings, so that
        /api/v1/marketplaces/admin does not match /admin.
      * Honour an IP whitelist (manual + per-IP, persisted in Redis).
      * All thresholds/TTLs are read from settings so they can be tuned
        per environment without code changes.
    """

    # Real scanner / probe signatures. Each entry is matched against a
    # full path segment (so ".env" won't match "/api/v1/environment").
    SUSPICIOUS_SEGMENTS: list[str] = [
        # Source / config exposure
        ".env",
        ".env.backup",
        ".env.example",
        ".env.local",
        ".env.production",
        ".env.development",
        ".git",
        ".git/config",
        ".git/head",
        ".htaccess",
        ".htpasswd",
        ".config",
        # Backup / DB dumps
        "backup",
        "backup.sql",
        "database.sql",
        "dump.sql",
        "db.sql",
        ".sql",
        ".db",
        ".sqlite",
        ".sqlite3",
        # WordPress / PHP scanners
        "wp-admin",
        "wp-login.php",
        "wp-config.php",
        "xmlrpc.php",
        "wp-cron.php",
        "phpinfo.php",
        "info.php",
        "phpmyadmin",
        "pma",
        "adminer.php",
        # Generic web shells
        ".php",
        ".asp",
        ".aspx",
        ".jsp",
        ".cgi",
        # Common probe / server-status endpoints
        "server-status",
        "server-info",
        "nginx_status",
        ".svn",
        ".ds_store",
        ".dockerenv",
        "actuator",
        "actuator/env",
    ]

    # Static substrings (used as a last-resort check, kept narrow on purpose).
    SUSPICIOUS_SUBSTRINGS: list[str] = [
        "/wp-",
        "credentials",
        "passwords",
        "shell.jsp",
        "cmd.jsp",
        "c99.php",
        "r57.php",
    ]

    def __init__(
        self,
        ban_ttl_seconds: int | None = None,
        violations_before_ban: int | None = None,
        violation_window_seconds: int | None = None,
    ):
        self.ban_ttl_seconds = ban_ttl_seconds or settings.IP_BAN_DEFAULT_TTL_SECONDS
        self.violations_before_ban = violations_before_ban or settings.IP_BAN_VIOLATIONS_BEFORE_BAN
        self.violation_window_seconds = violation_window_seconds or settings.IP_BAN_VIOLATION_WINDOW_SECONDS

    # ------------------------------------------------------------------ #
    # Ban / unban / query
    # ------------------------------------------------------------------ #

    async def is_banned(self, client_ip: str) -> bool:
        """Check if an IP is currently banned (whitelisted IPs always pass)."""
        if await self.is_whitelisted(client_ip):
            return False

        client = await self._get_redis()
        if not client:
            return False

        try:
            ban_key = f"ip_ban:{client_ip}"
            is_banned = await client.exists(ban_key)
            if is_banned:
                logger.warning("Banned IP attempted access: %s", client_ip)
            return bool(is_banned)
        except Exception as e:
            logger.error("Error checking ban status for %s: %s", client_ip, str(e))
            return False

    async def _get_redis(self):
        """Get Redis client, following the same pattern as rate_limit.py."""
        try:
            return get_redis()
        except Exception as e:
            logger.error("Redis client init failed: %s", str(e))
            return None

    async def ban_ip(
        self,
        client_ip: str,
        reason: BanReason,
        duration_seconds: Optional[int] = None,
        violations: int = 0,
    ) -> bool:
        """Manually ban an IP address."""
        client = await self._get_redis()
        if not client:
            return False

        # Never persist a ban for a whitelisted IP.
        if await self.is_whitelisted(client_ip):
            logger.info("Refusing to ban whitelisted IP: %s", client_ip)
            return False

        try:
            ban_key = f"ip_ban:{client_ip}"
            ttl = duration_seconds or self.ban_ttl_seconds
            ban_info = {
                "reason": reason.value,
                "banned_at": int(time.time()),
                "violations": violations,
            }

            await client.hset(ban_key, mapping=ban_info)
            await client.expire(ban_key, ttl)

            logger.warning(
                "IP banned: %s | Reason: %s | Duration: %ds",
                client_ip,
                reason.value,
                ttl,
            )
            return True
        except Exception as e:
            logger.error("Error banning IP %s: %s", client_ip, str(e))
            return False

    async def unban_ip(self, client_ip: str) -> bool:
        """Remove ban from an IP address."""
        client = await self._get_redis()
        if not client:
            return False

        try:
            ban_key = f"ip_ban:{client_ip}"
            result = await client.delete(ban_key)
            if result:
                logger.info("IP unbanned: %s", client_ip)
            return bool(result)
        except Exception as e:
            logger.error("Error unbanning IP %s: %s", client_ip, str(e))
            return False

    async def get_ban_info(self, client_ip: str) -> Optional[BanInfo]:
        """Get ban information for an IP."""
        client = await self._get_redis()
        if not client:
            return None

        try:
            ban_key = f"ip_ban:{client_ip}"
            info = await client.hgetall(ban_key)
            if not info:
                return None

            return BanInfo(
                ip=client_ip,
                reason=info.get("reason", "unknown"),
                banned_at=int(info.get("banned_at", 0)),
                expires_at=await client.ttl(ban_key),
                violations=int(info.get("violations", 0)),
            )
        except Exception as e:
            logger.error("Error getting ban info for %s: %s", client_ip, str(e))
            return None

    # ------------------------------------------------------------------ #
    # Whitelist
    # ------------------------------------------------------------------ #

    async def is_whitelisted(self, client_ip: str) -> bool:
        """Check if an IP is on the static or dynamic whitelist."""
        # 1. Static whitelist from settings (supports exact IPs and CIDR ranges).
        for entry in settings.IP_BAN_WHITELIST:
            try:
                if "/" in entry:
                    if ipaddress.ip_address(client_ip) in ipaddress.ip_network(entry, strict=False):
                        return True
                elif entry == client_ip:
                    return True
            except ValueError:
                # Ignore malformed entries rather than failing the request.
                continue

        # 2. Dynamic whitelist in Redis (set of IPs).
        client = await self._get_redis()
        if not client:
            return False
        try:
            return bool(await client.sismember("ip_ban:whitelist", client_ip))
        except Exception as e:
            logger.error("Error checking whitelist for %s: %s", client_ip, str(e))
            return False

    async def add_to_whitelist(self, client_ip: str) -> bool:
        """Add an IP to the dynamic whitelist and remove any existing ban."""
        client = await self._get_redis()
        if not client:
            return False
        try:
            await client.sadd("ip_ban:whitelist", client_ip)
            await self.unban_ip(client_ip)
            logger.info("IP added to whitelist: %s", client_ip)
            return True
        except Exception as e:
            logger.error("Error whitelisting IP %s: %s", client_ip, str(e))
            return False

    async def remove_from_whitelist(self, client_ip: str) -> bool:
        """Remove an IP from the dynamic whitelist."""
        client = await self._get_redis()
        if not client:
            return False
        try:
            result = await client.srem("ip_ban:whitelist", client_ip)
            if result:
                logger.info("IP removed from whitelist: %s", client_ip)
            return bool(result)
        except Exception as e:
            logger.error("Error removing IP %s from whitelist: %s", client_ip, str(e))
            return False

    async def list_whitelist(self) -> list[str]:
        """List IPs in the dynamic whitelist."""
        client = await self._get_redis()
        if not client:
            return []
        try:
            members = await client.smembers("ip_ban:whitelist")
            return sorted(members or [])
        except Exception as e:
            logger.error("Error listing whitelist: %s", str(e))
            return []

    # ------------------------------------------------------------------ #
    # Suspicious-path detection
    # ------------------------------------------------------------------ #

    def is_suspicious_path(self, path: str) -> bool:
        """
        Check if a request path looks like scanner / probe traffic.

        Matches against full path segments (so '/api/v1/marketplaces/admin'
        does NOT match) plus a small set of narrow substrings.
        """
        # Whitelisted path prefixes never count as suspicious (legitimate
        # application traffic, including all /admin sub-routes).
        for prefix in settings.IP_BAN_SAFE_PATH_PREFIXES:
            if path == prefix or path.startswith(prefix + "/"):
                return False

        # Split into segments; match exact segment names.
        normalized = path.strip("/").lower()
        if not normalized:
            return False
        segments = [seg for seg in normalized.split("/") if seg]

        for seg in segments:
            for pat in self.SUSPICIOUS_SEGMENTS:
                p = pat.lower().lstrip("/")
                if p == seg:
                    return True
            # ".php" should match any segment ending with .php
            if seg.endswith((".php", ".asp", ".aspx", ".jsp", ".cgi")) or seg.endswith(
                (".sql", ".db", ".sqlite", ".sqlite3")
            ):
                return True

        # Narrow substring fallbacks.
        lowered = path.lower()
        for sub in self.SUSPICIOUS_SUBSTRINGS:
            if sub in lowered:
                return True

        return False

    # ------------------------------------------------------------------ #
    # Violation recording
    # ------------------------------------------------------------------ #

    async def record_security_violation(self, client_ip: str, path: str) -> int:
        """Record a security violation and auto-ban if threshold reached."""
        # Whitelisted IPs are immune to auto-ban.
        if await self.is_whitelisted(client_ip):
            return 0

        client = await self._get_redis()
        if not client:
            return 0

        try:
            violation_key = f"security_violations:{client_ip}"
            current_time = int(time.time())

            # Use a sliding window to count violations
            pipeline = client.pipeline()
            pipeline.zremrangebyscore(
                violation_key,
                0,
                current_time - self.violation_window_seconds,
            )
            pipeline.zadd(violation_key, {str(current_time): current_time})
            pipeline.zcard(violation_key)
            pipeline.expire(violation_key, self.violation_window_seconds)

            results = await pipeline.execute()
            violation_count = results[2]

            logger.warning(
                "Security violation recorded for %s | Path: %s | Violations: %d/%d",
                client_ip,
                path,
                violation_count,
                self.violations_before_ban,
            )

            # Auto-ban if threshold reached
            if violation_count >= self.violations_before_ban:
                await self.ban_ip(
                    client_ip,
                    BanReason.SECURITY_VIOLATION,
                    duration_seconds=self.ban_ttl_seconds,
                    violations=violation_count,
                )
                logger.warning(
                    "IP auto-banned due to security violations: %s (%d violations)",
                    client_ip,
                    violation_count,
                )

            return violation_count
        except Exception as e:
            logger.error("Error recording security violation for %s: %s", client_ip, str(e))
            return 0

    async def record_rate_limit_violation(self, client_ip: str) -> int:
        """Record a rate limit violation (whitelisted IPs are immune)."""
        if await self.is_whitelisted(client_ip):
            return 0

        client = await self._get_redis()
        if not client:
            return 0

        try:
            violation_key = f"rate_limit_violations:{client_ip}"
            current_time = int(time.time())

            pipeline = client.pipeline()
            pipeline.zremrangebyscore(
                violation_key,
                0,
                current_time - self.violation_window_seconds,
            )
            pipeline.zadd(violation_key, {str(current_time): current_time})
            pipeline.zcard(violation_key)
            pipeline.expire(violation_key, self.violation_window_seconds)

            results = await pipeline.execute()
            violation_count = results[2]

            # Auto-ban after repeated rate limit violations
            if violation_count >= self.violations_before_ban:
                await self.ban_ip(
                    client_ip,
                    BanReason.RATE_LIMIT_VIOLATIONS,
                    duration_seconds=self.ban_ttl_seconds,
                    violations=violation_count,
                )

            return violation_count
        except Exception as e:
            logger.error("Error recording rate limit violation for %s: %s", client_ip, str(e))
            return 0


# Singleton instance
ip_ban_service = IPBanService()