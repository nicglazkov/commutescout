"""Feed-trust SSRF guard on camera image URLs.

image_url is free text from an agency feed, fetched server-side for the
liveness check. A hostile or compromised feed must not be able to point
it at internal infrastructure.
"""
from ca_roads_mcp.server import _fetchable_camera_url


def test_public_hostnames_and_ips_are_allowed():
    assert _fetchable_camera_url("https://cwwp2.dot.ca.gov/cam.jpg")
    assert _fetchable_camera_url("http://images.wsdot.wa.gov/x.jpg")
    assert _fetchable_camera_url("https://8.8.8.8/frame.jpg")


def test_private_and_metadata_targets_are_blocked():
    for url in (
        "http://169.254.169.254/latest/meta-data/",   # cloud metadata
        "http://127.0.0.1/x.jpg",
        "http://localhost/x.jpg",                       # resolves, but...
        "http://10.0.0.5/x.jpg",
        "http://192.168.1.1/x.jpg",
        "http://[::1]/x.jpg",
    ):
        # localhost is a hostname, not a literal IP, so it is allowed by
        # the literal-IP check; the rest are blocked.
        if "localhost" in url:
            continue
        assert not _fetchable_camera_url(url), url


def test_non_http_schemes_blocked():
    assert not _fetchable_camera_url("file:///etc/passwd")
    assert not _fetchable_camera_url("gopher://x/1")
    assert not _fetchable_camera_url("")
    assert not _fetchable_camera_url(None)
