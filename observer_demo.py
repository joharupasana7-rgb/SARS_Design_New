"""
observer_demo.py — Task 2.3d

Observer pattern: MarksUpdateNotifier (subject) notifies EmailNotifier
and AuditLogNotifier (observers) whenever a student's marks change.

See README.md for the explanation of how this keeps the Admin Panel
loosely coupled from the notification services.
"""

from abc import ABC, abstractmethod
from typing import List


class MarksObserver(ABC):
    """Common interface every observer of marks updates must implement."""

    @abstractmethod
    def update(self, student_id: int, new_marks: float) -> None:
        raise NotImplementedError


class MarksUpdateNotifier:
    """
    Subject: the Admin Panel calls notify_marks_updated() whenever a
    student's marks change. It has no knowledge of *what* the observers
    do with that information — it just calls update() on each of them.
    """

    def __init__(self) -> None:
        self._observers: List[MarksObserver] = []

    def attach(self, observer: MarksObserver) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: MarksObserver) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_marks_updated(self, student_id: int, new_marks: float) -> None:
        for observer in self._observers:
            observer.update(student_id, new_marks)


class EmailNotifier(MarksObserver):
    """Sends an email to the student when their marks are updated."""

    def update(self, student_id: int, new_marks: float) -> None:
        # In production this would call the real email service/API.
        print(f"[EmailNotifier] Sending email to student {student_id}: "
              f"your new marks are {new_marks}.")


class AuditLogNotifier(MarksObserver):
    """Writes a record to the audit log whenever marks are updated."""

    def update(self, student_id: int, new_marks: float) -> None:
        # In production this would write to a persistent audit log store.
        print(f"[AuditLogNotifier] Logged: student {student_id} marks "
              f"changed to {new_marks}.")


if __name__ == "__main__":
    notifier = MarksUpdateNotifier()

    email_notifier = EmailNotifier()
    audit_notifier = AuditLogNotifier()

    notifier.attach(email_notifier)
    notifier.attach(audit_notifier)

    # Admin Panel updates a student's marks and notifies all observers.
    notifier.notify_marks_updated(student_id=1001, new_marks=91.0)

    # Demonstrate deregistering an observer.
    notifier.detach(email_notifier)
    print("-- EmailNotifier detached --")
    notifier.notify_marks_updated(student_id=1001, new_marks=93.0)
