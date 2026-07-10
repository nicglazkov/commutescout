"""Watch areas: sign in, get approved, draw an area, get alerted.

Access model (premium trial): anyone can create an account (Firebase
Identity Platform: Google sign-in or email link), but the watch feature
only unlocks for approved users. Approval comes from redeeming an invite
code or from an admin flipping the user on in /admin. Nothing here
depends on code secrecy: ID tokens are verified server-side against
Google's published certificates, Firestore is reached only from this
server, and the only secrets (VAPID key, Resend key) live in Secret
Manager.

Storage is Firestore. Clients never talk to Firestore directly, so the
database has no client rules surface at all.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import math
import os
import secrets as pysecrets
import time
from datetime import UTC, datetime

from starlette.requests import Request
from starlette.responses import JSONResponse

from ca_roads.feeds import lcs as lcs_feed
from ca_roads_mcp import server as tools

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "ca-roads-mcp")
ISSUER = f"https://securetoken.google.com/{PROJECT}"
CERTS_URL = ("https://www.googleapis.com/robot/v1/metadata/x509/"
             "securetoken@system.gserviceaccount.com")
FIREBASE_API_KEY = os.environ.get(
    "FIREBASE_API_KEY", "AIzaSyAUFKclbyETTzgYmnNFqIB-CwoKFkoyv-Q")
FIREBASE_APP_ID = os.environ.get(
    "FIREBASE_APP_ID", "1:15002631928:web:25ce2ed159cda9ea35050d")
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", "nic@glazkov.com").split(",")
    if e.strip()
}
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:nic@glazkov.com")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
ALERT_FROM_EMAIL = os.environ.get("ALERT_FROM_EMAIL", "")
# OIDC audience + caller for the Cloud Scheduler push. Empty disables the
# scheduler path (admins can still trigger checks from /admin).
CHECKER_AUDIENCE = os.environ.get("CHECKER_AUDIENCE", "")
CHECKER_SA = os.environ.get("CHECKER_SA", "").lower()

# Trial limits: all in-process constants on purpose (max-instances 1).
MAX_WATCHES = 5
MAX_PUSH_SUBS = 5
MAX_RADIUS_KM = 65.0
MIN_RADIUS_KM = 1.0
MAX_POLY_POINTS = 20
MAX_ALERTS_PER_WATCH_CYCLE = 8
MAX_SEEN_IDS = 1500
CA_LAT = (31.0, 43.5)
CA_LON = (-126.5, -112.5)
WATCH_KINDS = ("incident", "closure", "chain", "fire")


# ---------------------------------------------------------------- tokens

_cert_cache: dict = {"exp": 0.0, "certs": None}
_scheduler_check_lock = asyncio.Lock()


async def _google_certs() -> dict:
    now = time.monotonic()
    if _cert_cache["certs"] is None or now > _cert_cache["exp"]:
        road = tools.get_road()
        resp = await road.client.get(CERTS_URL, timeout=10)
        resp.raise_for_status()
        _cert_cache["certs"] = resp.json()
        _cert_cache["exp"] = now + 45 * 60
    return _cert_cache["certs"]


async def verify_user(request: Request) -> dict | None:
    """Verify the Firebase ID token in Authorization: Bearer.

    Returns the claims dict, or None when missing/invalid. Signature,
    expiry, and audience are checked by google.auth.jwt against Google's
    x509 certs; issuer and subject are checked here.
    """
    header = request.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        return None
    token = header[7:].strip()
    if not token:
        return None
    try:
        from google.auth import jwt as gjwt

        claims = gjwt.decode(token, certs=await _google_certs(),
                             audience=PROJECT)
    except Exception:  # noqa: BLE001 - any bad token is just "no"
        return None
    if claims.get("iss") != ISSUER or not claims.get("sub"):
        return None
    return claims


def is_admin(claims: dict) -> bool:
    return (bool(claims.get("email_verified"))
            and (claims.get("email") or "").lower() in ADMIN_EMAILS)


async def verify_scheduler(request: Request) -> bool:
    """Accept the Cloud Scheduler OIDC push (audience + caller checked)."""
    if not CHECKER_AUDIENCE or not CHECKER_SA:
        return False
    header = request.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        return False

    def _check(token: str) -> bool:
        try:
            from google.auth.transport import requests as gadc
            from google.oauth2 import id_token as gidt

            info = gidt.verify_oauth2_token(
                token, gadc.Request(), audience=CHECKER_AUDIENCE)
            return (info.get("email") or "").lower() == CHECKER_SA
        except Exception:  # noqa: BLE001
            return False

    return await asyncio.to_thread(_check, header[7:].strip())


# ---------------------------------------------------------------- VAPID

_vapid: dict = {"raw": None, "public": None}


def vapid_keys() -> tuple[str | None, str | None]:
    """(raw_private_b64url, public_b64url) derived from the PEM in
    VAPID_PRIVATE_KEY, or (None, None) when unset (push disabled)."""
    if _vapid["raw"] is None:
        pem = os.environ.get("VAPID_PRIVATE_KEY", "")
        if "BEGIN" not in pem:
            return None, None
        from cryptography.hazmat.primitives import serialization
        from py_vapid import Vapid, b64urlencode

        v = Vapid.from_pem(pem.encode())
        _vapid["raw"] = b64urlencode(
            v.private_key.private_numbers().private_value.to_bytes(32, "big"))
        _vapid["public"] = b64urlencode(
            v.public_key.public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint))
    return _vapid["raw"], _vapid["public"]


# ---------------------------------------------------------------- store

class FirestoreStore:
    """Thin Firestore wrapper; tests swap in an in-memory twin."""

    def __init__(self) -> None:
        from google.cloud import firestore

        self.db = firestore.AsyncClient(project=PROJECT)

    async def get_user(self, uid: str) -> dict | None:
        snap = await self.db.collection("watch_users").document(uid).get()
        return snap.to_dict() if snap.exists else None

    async def upsert_user(self, uid: str, data: dict) -> None:
        await self.db.collection("watch_users").document(uid).set(
            data, merge=True)

    async def list_users(self) -> list[dict]:
        out = []
        async for snap in self.db.collection("watch_users").stream():
            d = snap.to_dict()
            d["uid"] = snap.id
            out.append(d)
        return out

    async def get_code(self, code: str) -> dict | None:
        snap = await self.db.collection("watch_codes").document(code).get()
        return snap.to_dict() if snap.exists else None

    async def upsert_code(self, code: str, data: dict) -> None:
        await self.db.collection("watch_codes").document(code).set(
            data, merge=True)

    async def increment_code_use(self, code: str) -> None:
        from google.cloud import firestore

        await self.db.collection("watch_codes").document(code).update(
            {"uses": firestore.Increment(1)})

    async def list_codes(self) -> list[dict]:
        out = []
        async for snap in self.db.collection("watch_codes").stream():
            d = snap.to_dict()
            d["code"] = snap.id
            out.append(d)
        return out

    async def list_watches(self, uid: str | None = None) -> list[dict]:
        from google.cloud.firestore_v1 import FieldFilter

        query = self.db.collection("watches")
        if uid is not None:
            query = query.where(filter=FieldFilter("uid", "==", uid))
        out = []
        async for snap in query.stream():
            d = snap.to_dict()
            d["id"] = snap.id
            out.append(d)
        return out

    async def create_watch(self, data: dict) -> str:
        ref = self.db.collection("watches").document()
        await ref.set(data)
        return ref.id

    async def get_watch(self, watch_id: str) -> dict | None:
        snap = await self.db.collection("watches").document(watch_id).get()
        return snap.to_dict() if snap.exists else None

    async def delete_watch(self, watch_id: str) -> None:
        await self.db.collection("watches").document(watch_id).delete()
        await self.db.collection("watch_state").document(watch_id).delete()

    async def list_push_subs(self, uid: str) -> list[dict]:
        from google.cloud.firestore_v1 import FieldFilter

        out = []
        async for snap in (self.db.collection("watch_pushsubs")
                           .where(filter=FieldFilter("uid", "==", uid))
                           .stream()):
            d = snap.to_dict()
            d["id"] = snap.id
            out.append(d)
        return out

    async def upsert_push_sub(self, sub_id: str, data: dict) -> None:
        await self.db.collection("watch_pushsubs").document(sub_id).set(data)

    async def delete_push_sub(self, sub_id: str) -> None:
        await self.db.collection("watch_pushsubs").document(sub_id).delete()

    async def get_seen(self, watch_id: str) -> set[str] | None:
        """None means the watch has never completed a cycle; an empty
        set means it has, and everything since cleared."""
        snap = await self.db.collection("watch_state").document(watch_id).get()
        if not snap.exists:
            return None
        return set((snap.to_dict() or {}).get("seen", []))

    async def set_seen(self, watch_id: str, seen: set[str]) -> None:
        ids = sorted(seen)[-MAX_SEEN_IDS:]
        await self.db.collection("watch_state").document(watch_id).set(
            {"seen": ids, "updated_at": datetime.now(UTC).isoformat()})


_store: FirestoreStore | None = None


def get_store() -> FirestoreStore:
    global _store
    if _store is None:
        _store = FirestoreStore()
    return _store


# ---------------------------------------------------------------- geometry

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def point_in_polygon(lat: float, lon: float, points: list[list[float]]) -> bool:
    """Ray casting over [lat, lon] vertex pairs."""
    inside = False
    n = len(points)
    j = n - 1
    for i in range(n):
        yi, xi = points[i]
        yj, xj = points[j]
        if ((xi > lon) != (xj > lon)) and (
                lat < (yj - yi) * (lon - xi) / ((xj - xi) or 1e-12) + yi):
            inside = not inside
        j = i
    return inside


def watch_matches(watch: dict, lat: float, lon: float) -> bool:
    if not lat or not lon:
        return False
    if watch.get("type") == "polygon":
        return point_in_polygon(lat, lon, watch.get("points") or [])
    center = watch.get("center") or {}
    return haversine_km(center.get("lat", 0.0), center.get("lon", 0.0),
                        lat, lon) <= float(watch.get("radius_km") or 0)


# ---------------------------------------------------------------- helpers

def _err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


async def _load_user(claims: dict) -> dict:
    """Fetch the user doc, creating a pending record on first sight."""
    store = get_store()
    uid = claims["sub"]
    user = await store.get_user(uid)
    if user is None:
        user = {
            "email": (claims.get("email") or "").lower(),
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
        }
        await store.upsert_user(uid, user)
    return user


def _approved(user: dict) -> bool:
    return user.get("status") == "approved"


async def _read_json(request: Request) -> dict | None:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return None
    return body if isinstance(body, dict) else None


# ---------------------------------------------------------------- API

async def api_watch_config(_: Request) -> JSONResponse:
    """Public client bootstrap. The Firebase web config is public by
    design; access control happens server-side on every call."""
    _, public = vapid_keys()
    return JSONResponse({
        "firebase": {
            "apiKey": FIREBASE_API_KEY,
            "authDomain": f"{PROJECT}.firebaseapp.com",
            "projectId": PROJECT,
            "appId": FIREBASE_APP_ID,
        },
        "vapidPublicKey": public,
        "emailEnabled": bool(RESEND_API_KEY and ALERT_FROM_EMAIL),
        "limits": {"watches": MAX_WATCHES, "radius_km": MAX_RADIUS_KM,
                   "polygon_points": MAX_POLY_POINTS},
    })


async def api_watch_me(request: Request) -> JSONResponse:
    claims = await verify_user(request)
    if not claims:
        return _err("sign in required", 401)
    user = await _load_user(claims)
    watches = []
    if _approved(user):
        watches = await get_store().list_watches(claims["sub"])
    return JSONResponse({
        "email": user.get("email"),
        "status": user.get("status"),
        "admin": is_admin(claims),
        "watches": watches,
    })


async def api_watch_redeem(request: Request) -> JSONResponse:
    claims = await verify_user(request)
    if not claims:
        return _err("sign in required", 401)
    body = await _read_json(request)
    code = ((body or {}).get("code") or "").strip().upper()
    if not code or len(code) > 40:
        return _err("access code required")
    store = get_store()
    user = await _load_user(claims)
    if _approved(user):
        return JSONResponse({"status": "approved"})
    rec = await store.get_code(code)
    if (rec is None or not rec.get("active")
            or rec.get("uses", 0) >= rec.get("max_uses", 1)):
        return _err("that code is not valid", 403)
    # Read-then-increment without a transaction: worst case a code is
    # honored one extra time at trial scale, which an admin can revoke.
    await store.increment_code_use(code)
    await store.upsert_user(claims["sub"], {
        "status": "approved",
        "code_used": code,
        "approved_at": datetime.now(UTC).isoformat(),
        "approved_by": "code",
    })
    return JSONResponse({"status": "approved"})


async def api_watch_create(request: Request) -> JSONResponse:
    claims = await verify_user(request)
    if not claims:
        return _err("sign in required", 401)
    user = await _load_user(claims)
    if not _approved(user):
        return _err("watch access is not enabled for this account", 403)
    body = await _read_json(request)
    if body is None:
        return _err("json body required")

    name = str(body.get("name") or "").strip()[:60] or "Watch area"
    kinds = [k for k in (body.get("kinds") or []) if k in WATCH_KINDS]
    if not kinds:
        return _err("pick at least one alert kind")
    channels = body.get("channels") or {}
    watch: dict = {
        "uid": claims["sub"],
        "name": name,
        "kinds": kinds,
        "channels": {"push": bool(channels.get("push", True)),
                     "email": bool(channels.get("email", False))},
        "active": True,
        "created_at": datetime.now(UTC).isoformat(),
    }

    wtype = body.get("type")
    if wtype == "circle":
        center = body.get("center") or {}
        try:
            lat, lon = float(center.get("lat")), float(center.get("lon"))
            radius = float(body.get("radius_km"))
        except (TypeError, ValueError):
            return _err("circle needs center {lat, lon} and radius_km")
        if not (CA_LAT[0] <= lat <= CA_LAT[1] and CA_LON[0] <= lon <= CA_LON[1]):
            return _err("center must be in California")
        radius = min(max(radius, MIN_RADIUS_KM), MAX_RADIUS_KM)
        watch.update({"type": "circle", "center": {"lat": lat, "lon": lon},
                      "radius_km": radius})
    elif wtype == "polygon":
        raw = body.get("points") or []
        if not (3 <= len(raw) <= MAX_POLY_POINTS):
            return _err(f"polygon needs 3-{MAX_POLY_POINTS} points")
        points = []
        try:
            for p in raw:
                lat, lon = float(p[0]), float(p[1])
                if not (CA_LAT[0] <= lat <= CA_LAT[1]
                        and CA_LON[0] <= lon <= CA_LON[1]):
                    return _err("all points must be in California")
                points.append([lat, lon])
        except (TypeError, ValueError, IndexError):
            return _err("points must be [lat, lon] pairs")
        watch.update({"type": "polygon", "points": points})
    else:
        return _err("type must be circle or polygon")

    store = get_store()
    existing = await store.list_watches(claims["sub"])
    if len(existing) >= MAX_WATCHES:
        return _err(f"trial accounts are limited to {MAX_WATCHES} watches", 403)
    watch_id = await store.create_watch(watch)
    watch["id"] = watch_id
    return JSONResponse(watch)


async def api_watch_delete(request: Request) -> JSONResponse:
    claims = await verify_user(request)
    if not claims:
        return _err("sign in required", 401)
    watch_id = request.path_params["watch_id"]
    store = get_store()
    watch = await store.get_watch(watch_id)
    if watch is None or watch.get("uid") != claims["sub"]:
        return _err("not found", 404)
    await store.delete_watch(watch_id)
    return JSONResponse({"deleted": watch_id})


async def api_push_subscribe(request: Request) -> JSONResponse:
    claims = await verify_user(request)
    if not claims:
        return _err("sign in required", 401)
    user = await _load_user(claims)
    if not _approved(user):
        return _err("watch access is not enabled for this account", 403)
    body = await _read_json(request)
    sub = (body or {}).get("subscription") or {}
    endpoint = sub.get("endpoint") or ""
    if not endpoint.startswith("https://") or "keys" not in sub:
        return _err("a web push subscription is required")
    store = get_store()
    subs = await store.list_push_subs(claims["sub"])
    sub_id = hashlib.sha256(endpoint.encode()).hexdigest()[:24]
    if len(subs) >= MAX_PUSH_SUBS and all(s["id"] != sub_id for s in subs):
        return _err("too many devices registered", 403)
    await store.upsert_push_sub(sub_id, {
        "uid": claims["sub"],
        "subscription": sub,
        "created_at": datetime.now(UTC).isoformat(),
    })
    return JSONResponse({"ok": True})


_test_sends: dict[str, float] = {}


async def api_watch_test(request: Request) -> JSONResponse:
    """Send a test notification so people can confirm their device."""
    claims = await verify_user(request)
    if not claims:
        return _err("sign in required", 401)
    user = await _load_user(claims)
    if not _approved(user):
        return _err("watch access is not enabled for this account", 403)
    now = time.monotonic()
    if now - _test_sends.get(claims["sub"], 0.0) < 120:
        return _err("test already sent; wait two minutes", 429)
    _test_sends[claims["sub"]] = now
    subs = await get_store().list_push_subs(claims["sub"])
    if not subs:
        return _err("no devices registered for push yet")
    sent = await _push_to_subs(subs, {
        "title": "CA Roads test alert",
        "body": "Push notifications are working for your account.",
        "url": "/watch",
    })
    return JSONResponse({"sent": sent, "devices": len(subs)})


# ---------------------------------------------------------------- admin

async def _require_admin(request: Request) -> dict | None:
    claims = await verify_user(request)
    if not claims or not is_admin(claims):
        return None
    return claims


async def api_admin_overview(request: Request) -> JSONResponse:
    if not await _require_admin(request):
        return _err("admin only", 403)
    store = get_store()
    users = await store.list_users()
    codes = await store.list_codes()
    watches = await store.list_watches()
    counts: dict[str, int] = {}
    for w in watches:
        counts[w.get("uid", "")] = counts.get(w.get("uid", ""), 0) + 1
    for u in users:
        u["watch_count"] = counts.get(u.get("uid", ""), 0)
    return JSONResponse({"users": users, "codes": codes})


async def api_admin_user(request: Request) -> JSONResponse:
    if not await _require_admin(request):
        return _err("admin only", 403)
    body = await _read_json(request)
    uid = (body or {}).get("uid") or ""
    action = (body or {}).get("action") or ""
    if not uid or action not in ("approve", "revoke"):
        return _err("uid and action approve|revoke required")
    status = "approved" if action == "approve" else "revoked"
    await get_store().upsert_user(uid, {
        "status": status,
        "approved_at": datetime.now(UTC).isoformat(),
        "approved_by": "admin",
    })
    return JSONResponse({"uid": uid, "status": status})


async def api_admin_code(request: Request) -> JSONResponse:
    if not await _require_admin(request):
        return _err("admin only", 403)
    body = await _read_json(request) or {}
    action = body.get("action") or "create"
    store = get_store()
    if action == "disable":
        code = (body.get("code") or "").strip().upper()
        if not code or await store.get_code(code) is None:
            return _err("unknown code")
        await store.upsert_code(code, {"active": False})
        return JSONResponse({"code": code, "active": False})
    max_uses = min(max(int(body.get("max_uses") or 1), 1), 100)
    code = "ROADS-" + pysecrets.token_hex(3).upper()
    await store.upsert_code(code, {
        "active": True,
        "max_uses": max_uses,
        "uses": 0,
        "note": str(body.get("note") or "")[:80],
        "created_at": datetime.now(UTC).isoformat(),
    })
    return JSONResponse({"code": code, "max_uses": max_uses})


# ---------------------------------------------------------------- checker

async def _collect_events() -> list[dict]:
    """Current statewide events in watchable form. Every feed here is
    TTL-cached by the shared road object, so this piggybacks on the
    same fetches the map already makes."""
    road = tools.get_road()
    chp, lcs, cc, wf = await asyncio.gather(
        road.incidents(), road.lane_closures(), road.chain_controls(),
        road.wildfires(),
    )
    events: list[dict] = []
    for i in chp.records:
        events.append({
            "id": f"chp:{i.id}", "kind": "incident",
            "lat": i.lat, "lon": i.lon,
            "title": i.log_type or "Incident",
            "body": f"{i.location} ({i.area})",
        })
    for c in lcs.records:
        events.append({
            "id": f"lcs:{c.index}", "kind": "closure",
            "lat": c.begin_lat, "lon": c.begin_lon,
            "title": f"{c.route} {lcs_feed.closure_class(c)}",
            "body": lcs_feed.describe(c),
        })
    for c in cc.records:
        if c.status and c.status != "R-0":
            events.append({
                "id": f"chain:{c.index}:{c.status}", "kind": "chain",
                "lat": c.lat, "lon": c.lon,
                "title": f"Chain control {c.status} on {c.route}",
                "body": c.status_description or c.location_name,
            })
    for f in wf.records:
        events.append({
            "id": f"fire:{f.id}", "kind": "fire",
            "lat": f.lat, "lon": f.lon,
            "title": f"Wildfire: {f.name}",
            "body": (f"{f.size_acres:,.0f} acres"
                     if f.size_acres else "size unknown"),
        })
    return events


async def _push_to_subs(subs: list[dict], payload: dict) -> int:
    raw, _ = vapid_keys()
    if raw is None:
        return 0
    data = json.dumps(payload)
    sent = 0

    def _send(sub_info: dict) -> bool:
        from pywebpush import WebPushException, webpush

        try:
            webpush(subscription_info=sub_info, data=data,
                    vapid_private_key=raw,
                    vapid_claims={"sub": VAPID_SUBJECT}, ttl=600)
            return True
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                raise _GonePush from exc
            return False

    for sub in subs:
        try:
            ok = await asyncio.to_thread(_send, sub["subscription"])
        except _GonePush:
            with contextlib.suppress(Exception):
                await get_store().delete_push_sub(sub["id"])
            continue
        sent += 1 if ok else 0
    return sent


class _GonePush(Exception):
    """Push endpoint says the subscription no longer exists."""


async def _email_alert(to_email: str, subject: str, lines: list[str]) -> bool:
    if not (RESEND_API_KEY and ALERT_FROM_EMAIL and to_email):
        return False
    body_html = "".join(f"<p>{line}</p>" for line in lines)
    disclaimer = ("<p style='color:#777;font-size:12px'>Informational only; "
                  "may be delayed, incomplete, or wrong. Verify with 511 or "
                  "quickmap.dot.ca.gov before you drive. Never rely on this "
                  "for evacuation or emergency decisions.</p>")
    road = tools.get_road()
    try:
        resp = await road.client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={"from": ALERT_FROM_EMAIL, "to": [to_email],
                  "subject": subject, "html": body_html + disclaimer},
            timeout=15,
        )
        return resp.status_code in (200, 201)
    except Exception:  # noqa: BLE001
        return False


async def run_check_cycle() -> dict:
    """One pass over every active watch: new matching events get pushed
    (and emailed when configured), then the seen-set advances. First run
    of a watch seeds the seen-set silently so creating a watch does not
    dump the current backlog on the user."""
    store = get_store()
    events = await _collect_events()
    watches = await store.list_watches()
    users: dict[str, dict | None] = {}
    stats = {"watches": len(watches), "events": len(events),
             "alerts": 0, "pushes": 0, "emails": 0}

    for watch in watches:
        if not watch.get("active"):
            continue
        uid = watch.get("uid", "")
        if uid not in users:
            users[uid] = await store.get_user(uid)
        user = users[uid]
        if not user or user.get("status") != "approved":
            continue

        matched = [e for e in events
                   if e["kind"] in (watch.get("kinds") or [])
                   and watch_matches(watch, e["lat"], e["lon"])]
        seen = await store.get_seen(watch["id"])
        first_run = seen is None
        seen = seen or set()
        fresh = [e for e in matched if e["id"] not in seen]
        current_ids = {e["id"] for e in matched}

        if not first_run and fresh:
            for event in fresh[:MAX_ALERTS_PER_WATCH_CYCLE]:
                stats["alerts"] += 1
                title = f"{watch.get('name', 'Watch')}: {event['title']}"
                if watch.get("channels", {}).get("push", True):
                    subs = await store.list_push_subs(uid)
                    stats["pushes"] += await _push_to_subs(subs, {
                        "title": title, "body": event["body"],
                        "url": "/watch",
                    })
                if watch.get("channels", {}).get("email"):
                    ok = await _email_alert(
                        user.get("email") or "", title,
                        [event["body"],
                         "From your CA Roads watch area "
                         f"“{watch.get('name', '')}”."])
                    stats["emails"] += 1 if ok else 0

        # Advance state: keep ids still current plus everything alerted,
        # trimmed in set_seen. An id that clears and returns re-alerts,
        # which is the behavior people want for reopened incidents.
        await store.set_seen(watch["id"], seen.intersection(current_ids)
                             | current_ids)
    return stats


async def api_check_watches(request: Request) -> JSONResponse:
    """Cloud Scheduler entry point (also runnable by an admin)."""
    if not await verify_scheduler(request):
        admin = await _require_admin(request)
        if not admin:
            return _err("not authorized", 403)
    if _scheduler_check_lock.locked():
        return JSONResponse({"skipped": "check already running"})
    async with _scheduler_check_lock:
        stats = await run_check_cycle()
    return JSONResponse(stats)
