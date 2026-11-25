"""Cooperative, cancellable priority gate for local inference workloads."""
from contextlib import contextmanager
import threading
import itertools


class Cancelled(RuntimeError):
    pass


class JobGate:
    def __init__(self):
        self.condition = threading.Condition()
        self.waiters = []
        self.active = None
        self.sequence = itertools.count()

    def acquire(self, cancelled, priority=0):
        ticket = (priority, next(self.sequence))
        with self.condition:
            self.waiters.append(ticket)
            try:
                while True:
                    if cancelled.is_set():
                        raise Cancelled('Bekor qilindi.')
                    if self.active is None and ticket == min(self.waiters):
                        self.active = ticket
                        return ticket
                    self.condition.wait(.05)
            finally:
                self.waiters.remove(ticket)

    def release(self, ticket):
        with self.condition:
            if self.active == ticket:
                self.active = None
                self.condition.notify_all()

    def try_acquire(self):
        with self.condition:
            if self.active is not None or self.waiters:return None
            self.active=(0,next(self.sequence))
            return self.active

    @contextmanager
    def hold(self, cancelled, priority=0):
        ticket = self.acquire(cancelled, priority)
        try:
            yield
        finally:
            self.release(ticket)


gate = JobGate()
