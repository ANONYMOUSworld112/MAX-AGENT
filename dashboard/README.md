# Local dashboard

`dashboard/server.py` defines a FastAPI dashboard server with HTTP and WebSocket routes. `main.py` attempts to start it as an optional part of the live application; if dashboard startup fails, the voice application continues without it.

The server defaults to `127.0.0.1:8000`. Its web UI files are `static/login.html` and `static/app.html`; `static/crypto-js.min.js` is served locally for the dashboard client. The server includes token-based access checks, rate limiting, device-session handling, and upload routes.

The dashboard requires FastAPI, Uvicorn, and cryptography. File upload support also depends on `python-multipart`. Review host and network exposure before changing the loopback default. The server does not provide a separately documented CLI entry point in this checkout.
