# Kestrel changelog

## 2.4.1 (18 June 2026)

- Fixes the memory leak in the HTTP/2 client that was introduced in 2.4.0.
- The default connection pool size is now 16 (it was 10).

## 2.4.0 (2 June 2026)

- Adds HTTP/2 support to the client.
- Drops support for Python 3.9.
