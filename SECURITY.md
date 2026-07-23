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
Caltrans, etc.) or in third-party services the app calls (CARTO, OSRM,
Nominatim); report those to their owners.

## Supported versions

The latest release and the hosted service. Older tags don't receive
patches; self-hosters should track releases.
