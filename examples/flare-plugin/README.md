# Example Flare plugin

One file, every endpoint in [the Flare specification](../../docs/flare.md),
an in-memory store, and a passing conformance check. Start here when you
want to run a source of your own, public or private.

First install the packages. From the repo root, install the repo
itself, which provides the `ca_roads.flare` conformance check, plus
Starlette and Uvicorn, which `server.py` imports:

```
pip install -e .
pip install starlette uvicorn
```

Then run the plugin and check it:

```
cd examples/flare-plugin
python server.py
python -m ca_roads.flare check http://127.0.0.1:8300
```

Run the check in a second terminal while the server runs. The server
listens on port 8300; set `PORT` to change it.

Set `FLARE_TOKEN` to require a bearer token on every call but the
handshake (what a private plugin does), and `FLARE_ID`, `FLARE_NAME`,
`FLARE_CONTACT` to name it. Replace `Store` with your data and keep the
HTTP layer; the check tells you when a record breaks a rule.

To be listed, deploy it behind HTTPS and send the manifest through the
[contact page](https://commutescout.com/contact). To use it privately,
deploy it behind HTTPS, open the app, go to Tools > Community sources,
and add its URL.
