"""Waze RT protocol error conditions.

Ported from ``WazeExceptions.java``. The three classes are the ones the
recovery logic branches on: a rejected account is replaced, an expired
session is re-logged-in, and anything else is a transient failure that must
not cost the account.
"""

from __future__ import annotations


class WazeError(Exception):
    """Base class, so one ``except`` catches the whole protocol."""


class AccountRejected(WazeError):
    """The server rejected the account or session (HTTP 4xx, for example
    403). The account should be replaced."""


class SessionExpired(WazeError):
    """The session is no longer valid ("relogin", "unknown userid",
    "secretkey missing"). Log in again with the same account."""


class WazeOperationError(WazeError):
    """A generic protocol or operation failure (HTTP 5xx, a failed
    register, an empty response)."""
