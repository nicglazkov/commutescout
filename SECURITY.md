# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately via
[GitHub Security Advisories](https://github.com/nicglazkov/commutescout/security/advisories/new)
or by email to security@commutescout.com, not in a public issue.
You'll normally get a first response within a few days, and a fix for
confirmed issues ships as a priority release.

There is no bug bounty, but reporters are credited in the release notes
if they want to be.

## Scope

- **This codebase**: the MCP server, the web app, and the feed layer.
- **The hosted service** at commutescout.com and mcp.commutescout.com:
  reports about the live deployment are very welcome. Please keep
  testing non-destructive: no volumetric/DoS testing (rate and cost
  guards are part of the design; hammering them just costs money) and
  no social engineering.

Out of scope: vulnerabilities in the upstream public data feeds (CHP,
Caltrans, etc.) or in third-party services the app calls (Stadia Maps,
which provides routing, place search, and the base map in the static
map images for alert emails and trip pages); report those to their
owners. The interactive map's base tiles come from CommuteScout's own
tile files and OpenFreeMap, not Stadia Maps.

## API keys

You create API keys under Settings on the map. The full key is shown
once, when you create it. The server stores only a SHA-256 hash of the
key's secret, so nobody, including the operators, can show it to you
again. You can revoke a key under Settings at any time; requests that
use it stop working within a minute.

If a key leaks, revoke it under Settings, create a new one, and update
the apps that used the old one. A leaked key can spend that account's
daily request quota and can read that account's saved places, so
revoke it right away.

Saved places reached through a key (Home, Work, favorites) are returned
only to requests made with a key that belongs to the same account.
They are never shared with other accounts and never logged.

## Supported versions

The latest release and the hosted service. Older tags don't receive
patches; self-hosters should track releases.
