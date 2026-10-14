"""Exit codes and messages from the Waybook spec."""


class WaybookError(Exception):
    def __init__(self, code: str, message: str, exit_code: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code


# Shown whenever a link value is rejected, so one failure names the fix.
LINK_HINT = "accepted forms are commit:<sha> and pr:<number>, for example --link pr:12"


def usage(detail: str) -> WaybookError:
    return WaybookError("E_USAGE", f"Bad arguments: {detail}", 2)


def not_initialized() -> WaybookError:
    return WaybookError(
        "E_NOT_INITIALIZED",
        "No .waybook/ found; run waybook init",
        3,
    )


def schema_invalid(version: int, field: str) -> WaybookError:
    message = f"Entry fails schema v{version}: {field}"
    if field == "links":
        message = f"{message}; {LINK_HINT}"
    return WaybookError(
        "E_SCHEMA_INVALID",
        message,
        4,
    )


def schema_version(found: int, supported: int) -> WaybookError:
    return WaybookError(
        "E_SCHEMA_VERSION",
        f"Board is schema v{found}, tool supports v{supported}; run waybook migrate",
        5,
    )


def not_found(entry_id: str) -> WaybookError:
    return WaybookError("E_NOT_FOUND", f"No entry with id {entry_id}", 6)


def append_only(entry_id: str) -> WaybookError:
    return WaybookError(
        "E_APPEND_ONLY",
        f"Entry {entry_id} is immutable except via mark-resolved",
        7,
    )


def already_resolved(entry_id: str) -> WaybookError:
    return WaybookError(
        "E_ALREADY_RESOLVED",
        f"Entry {entry_id} already resolved",
        8,
    )


def access_denied() -> WaybookError:
    return WaybookError(
        "E_ACCESS_DENIED",
        "Cross-project read requires the coordinator role",
        9,
    )


def reason_required() -> WaybookError:
    return WaybookError(
        "E_REASON_REQUIRED",
        "--reason is required for cross-project access",
        10,
    )


def integrity(entry_id: str) -> WaybookError:
    return WaybookError(
        "E_INTEGRITY",
        f"Hash chain broken at {entry_id}; board modified outside the CLI",
        11,
    )


def link_lookup(archived_some: bool = False) -> WaybookError:
    detail = (
        "entries with a known state were still archived"
        if archived_some
        else "nothing pruned"
    )
    return WaybookError(
        "E_LINK_LOOKUP",
        f"Could not check PR/commit state (offline or no auth); {detail}",
        12,
    )


def secret_refused(pattern_class: str) -> WaybookError:
    return WaybookError(
        "E_SECRET",
        f"Refused write: secret pattern {pattern_class}",
        13,
    )
