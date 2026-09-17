"""The synthetic device fingerprint sent in ClientInfo.

Ported from ``DeviceIdentity.java``: one of eight fixed profiles, each with a
fresh installation id. The relay picks a profile once and keeps it for the
life of the account, as the Java version does by persisting it.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass

POOL = (
    ("samsung", "SM-S928B", "16-SDK36", 1440, 3088),
    ("samsung", "SM-A546B", "15-SDK35", 1080, 2340),
    ("Google", "Pixel 9 Pro", "16-SDK36", 1280, 2856),
    ("Google", "Pixel 8", "15-SDK35", 1080, 2400),
    ("OnePlus", "CPH2451", "15-SDK35", 1240, 2772),
    ("Xiaomi", "2201117TG", "14-SDK34", 1220, 2712),
    ("motorola", "moto g84", "15-SDK35", 1080, 2400),
    ("Nothing", "A065", "15-SDK35", 1080, 2412),
)


@dataclass(frozen=True)
class DeviceIdentity:
    manufacturer: str
    model: str
    os_version: str
    screen_w: int
    screen_h: int
    installation_id: str

    @staticmethod
    def random() -> DeviceIdentity:
        manufacturer, model, os_version, w, h = random.choice(POOL)  # noqa: S311
        return DeviceIdentity(manufacturer, model, os_version, w, h, str(uuid.uuid4()))

    def as_dict(self) -> dict:
        return {
            "manufacturer": self.manufacturer, "model": self.model,
            "os_version": self.os_version, "screen_w": self.screen_w,
            "screen_h": self.screen_h, "installation_id": self.installation_id,
        }

    @staticmethod
    def from_dict(d: dict) -> DeviceIdentity:
        return DeviceIdentity(
            d.get("manufacturer", "Google"), d.get("model", "Pixel 8"),
            d.get("os_version", "15-SDK35"), int(d.get("screen_w", 1080)),
            int(d.get("screen_h", 2400)), d.get("installation_id") or str(uuid.uuid4()))
