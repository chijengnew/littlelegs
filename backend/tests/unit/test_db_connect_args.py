import ssl

import certifi

from app.db.session import connect_args


def test_without_ca_uses_plain_connection_settings():
    args = connect_args(None)
    assert args == {"charset": "utf8mb4", "init_command": "SET time_zone = '+00:00'"}


def test_with_ca_requires_verified_tls():
    ctx = connect_args(certifi.where())["ssl"]
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED
