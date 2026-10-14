"""Secret-shaped fixtures joined at runtime.

Scanners read source text. The pieces below never form a scanner literal
on their own; callers still receive the same strings the tests used before.
"""

from __future__ import annotations


def _join(*parts: str) -> str:
    return "".join(parts)


def aws_access_key_example() -> str:
    return _join("AK", "IA", "IOSF", "ODNN", "7EXA", "MPLE")


def aws_temporary_key_example() -> str:
    return _join("AS", "IA", "IOSF", "ODNN", "7EXA", "MPLE")


def aws_access_key_with_zwsp() -> str:
    return _join("AK", "IA", "\u200b", "IOSF", "ODNN", "7EXA", "MPLE")


def aws_access_key_run_of_a() -> str:
    return _join("AK", "IA") + ("A" * 16)


def rsa_private_key_header() -> str:
    return _join("-----", "BEGIN RSA PRIVATE KEY", "-----")


def rsa_private_key_header_lower() -> str:
    return _join("-----", "begin rsa private key", "-----")


def live_secret_key() -> str:
    return _join("sk-", "live-", "abcdefghijklmnopqrstuvwxyz")


def generic_secret_key() -> str:
    return _join("sk-", "abcdefghijklmnop", "qrstuvwxyz123456")


def github_token_a() -> str:
    return _join("gh", "p_") + ("a" * 36)


def github_token_b() -> str:
    return _join("gh", "p_") + ("b" * 36)


def project_secret_key() -> str:
    return _join("sk-", "proj-") + ("a" * 40)


def anthropic_api_key() -> str:
    return _join("sk-", "ant-", "api03-") + ("b" * 40)


def live_secret_key_underscore() -> str:
    return _join("sk_", "live_") + ("a" * 20)


def project_secret_key_underscore() -> str:
    return _join("sk-", "proj-", "_") + ("b" * 40)


def anthropic_admin_key() -> str:
    return _join("sk-", "ant-", "admin01-") + ("c" * 40)
