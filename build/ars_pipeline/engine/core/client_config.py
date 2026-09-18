"""Top-level access to 0_Config/clients_config.json.

The file is a flat map of client ID to client record, with one exception:
a key beginning with an underscore carries metadata about the file itself,
not a client. `_meta` records when the competition config was last repaired
and by which tool, so a reader can tell a stale book from a current one
without going to git.

Every consumer that walks the top level must skip those keys. A consumer
that does not will report the stamp as a client with no ClientID, no
Products and no code sheet -- eleven spurious ERRORs from the validator, and
a client count one too high on every generated page.

    from core.client_config import clients_only, meta

    for cid, rec in clients_only(config).items():
        ...
"""

from __future__ import annotations

META_KEY = "_meta"
_META_PREFIX = "_"


def is_meta_key(key: str) -> bool:
    """True for a top-level key that describes the file, not a client."""
    return key.startswith(_META_PREFIX)


def clients_only(config: dict) -> dict:
    """The client records, with every metadata key removed."""
    return {cid: rec for cid, rec in config.items() if not is_meta_key(cid)}


def meta(config: dict) -> dict:
    """The file's metadata block, or an empty dict if it carries none."""
    return config.get(META_KEY) or {}


def with_meta(clients: dict, block: dict) -> dict:
    """A config with `block` as its metadata, written ahead of the clients.

    Insertion order is what json.dump writes, so the stamp lands at the top
    of the file where a person opening it will see it first.
    """
    return {META_KEY: block, **clients_only(clients)}
