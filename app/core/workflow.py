"""Serialize checkout with changes to the customer, cart and menu it observes.
Participants acquire this process-wide lock once, before any repository lock.
"""

from threading import Lock

workflow_lock = Lock()
