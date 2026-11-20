"""Define the storage-failure signal shared by checkout's repository adapters.
Domain access denials and absent records travel through separate channels.
"""


class StorageFailure(Exception):
    """A store could not read, validate, or save its data."""
