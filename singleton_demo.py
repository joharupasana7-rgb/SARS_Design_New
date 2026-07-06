"""
singleton_demo.py — Task 2.3c

Thread-safe Singleton DatabaseConnection using double-checked locking.

Why naive lazy initialisation is unsafe under concurrency:
    A naive implementation would look like:

        class DatabaseConnection:
            _instance = None
            def __new__(cls):
                if cls._instance is None:          # (A) check
                    cls._instance = cls._create()  # (B) create
                return cls._instance

    If two threads call this at nearly the same time, both can pass
    check (A) before either has finished step (B) — Thread 1 sees
    `_instance is None`, gets suspended by the scheduler before it
    finishes creating the object, and Thread 2 also sees `_instance is
    None` (because Thread 1 hasn't assigned it yet) and starts creating
    its OWN instance. The result is two separate DatabaseConnection
    objects instead of one, silently violating the Singleton guarantee.
    A lock is required to make the "check-then-create-then-assign"
    sequence atomic with respect to other threads.
"""

import threading


class DatabaseConnection:
    """
    Thread-safe Singleton providing one shared database connection
    object for the lifetime of the application.
    """

    _instance = None          # holds the single shared instance
    _lock = threading.Lock()  # guards creation of that instance

    def __new__(cls, *args, **kwargs):
        # First check WITHOUT the lock: once the instance exists, every
        # subsequent call can skip locking entirely, which keeps normal
        # (post-initialisation) access fast.
        if cls._instance is None:
            # Only one thread at a time may enter this block.
            with cls._lock:
                # Second check INSIDE the lock: another thread may have
                # already created the instance while this thread was
                # waiting to acquire the lock. Without this second
                # check, two threads that both passed the first "if"
                # could each create an instance once they get the lock
                # one after another.
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._connection = cls._instance._connect()
        return cls._instance

    def _connect(self):
        """
        Placeholder for real connection setup (e.g., psycopg2.connect(...)).
        Returns a simple object here so the demo runs without a real DB.
        """
        return object()

    def get_connection(self):
        """Return the single shared connection object."""
        return self._connection


if __name__ == "__main__":
    # Demonstrate that concurrent access still yields exactly one instance.
    instances = []

    def create_and_store():
        instances.append(DatabaseConnection())

    threads = [threading.Thread(target=create_and_store) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    all_same = all(inst is instances[0] for inst in instances)
    print(f"Created {len(instances)} references from concurrent threads.")
    print(f"All references point to the same instance: {all_same}")
    print(f"Shared connection object: {instances[0].get_connection()}")
