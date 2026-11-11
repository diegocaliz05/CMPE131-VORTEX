"""Only storage-level errors are exceptions. Expected business outcomes
(denied, invalid, conflict ...) are returned as services.results.Result instead."""


class StorageError(Exception):
    """The data could not be saved or read."""


class DuplicateRecordError(StorageError):
    """A unique constraint rejected the record (e.g. the same event twice)."""
