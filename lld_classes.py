"""
lld_classes.py — Task 2.3a and 2.3b

Defines the Student and Enrollment classes for the Student Portal module,
and the EnrollmentRepository interface that Enrollment-related business
logic depends on for persistence.

SOLID principles applied:
  - Single Responsibility Principle (SRP): Student holds only student
    identity/profile data and behaviour. It deliberately has NO method for
    sending email notifications — that responsibility belongs to a
    separate notification component (see observer_demo.py), so a change
    to email logic never forces a change to the Student class, and vice
    versa.
  - Open/Closed Principle (OCP): Enrollment is open for extension via
    subclassing (see WaitlistedEnrollment below) without modifying the
    base class itself. New enrollment behaviours are added by overriding
    methods in a subclass, not by editing Enrollment's existing code.
  - Dependency Inversion Principle (DIP): high-level business logic
    depends on the EnrollmentRepository abstraction, not on a concrete
    database implementation. See the note above the interface for detail.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional, List


# ============================================================
# Student class
# ============================================================
class Student:
    """
    Represents a student's identity and profile data.

    SRP: this class is only responsible for representing a student and
    the operations that belong to a student's own state (updating a
    department, reading identity fields). It intentionally does NOT
    contain a `send_email()` or `notify()` method — email notification
    is a separate concern owned by the notification services, not by
    the data model for a student.
    """

    def __init__(self, student_id: int, name: str, department: str,
                 email: str, advisor_id: Optional[int] = None) -> None:
        self.student_id: int = student_id
        self.name: str = name
        self.department: str = department
        self.email: str = email
        self.advisor_id: Optional[int] = advisor_id

    def get_id(self) -> int:
        return self.student_id

    def get_name(self) -> str:
        return self.name

    def get_email(self) -> str:
        return self.email

    def get_department(self) -> str:
        return self.department

    def update_department(self, new_department: str) -> None:
        self.department = new_department

    def assign_advisor(self, advisor_id: int) -> None:
        self.advisor_id = advisor_id

    def __repr__(self) -> str:
        return f"Student(id={self.student_id}, name={self.name!r}, department={self.department!r})"


# ============================================================
# Enrollment class hierarchy
# ============================================================
class Enrollment:
    """
    Represents a student's enrollment in a course.

    OCP: methods that vary by enrollment "kind" (here, calculate_grade
    and is_active) are written to be overridden by subclasses. New
    enrollment types (e.g., WaitlistedEnrollment) can change this
    behaviour purely through inheritance, without any edit to this
    base class's source code.
    """

    def __init__(self, enrollment_id: int, student_id: int, course_code: str,
                 enrollment_year: int, marks: Optional[float] = None,
                 status: str = "active") -> None:
        self.enrollment_id: int = enrollment_id
        self.student_id: int = student_id
        self.course_code: str = course_code
        self.enrollment_year: int = enrollment_year
        self.marks: Optional[float] = marks
        self.status: str = status

    def get_status(self) -> str:
        return self.status

    def is_active(self) -> bool:
        return self.status == "active"

    def calculate_grade(self) -> str:
        """Default grading logic for a normally-enrolled student."""
        if self.marks is None:
            return "N/A"
        if self.marks >= 85:
            return "A"
        if self.marks >= 70:
            return "B"
        if self.marks >= 55:
            return "C"
        if self.marks >= 35:
            return "D"
        return "F"

    def __repr__(self) -> str:
        return (f"Enrollment(id={self.enrollment_id}, student_id={self.student_id}, "
                f"course_code={self.course_code!r}, status={self.status!r})")


class WaitlistedEnrollment(Enrollment):
    """
    Extension point demonstrating OCP: adds waitlist-specific behaviour
    without changing a single line of the base Enrollment class.
    """

    def __init__(self, enrollment_id: int, student_id: int, course_code: str,
                 enrollment_year: int, waitlist_position: int) -> None:
        super().__init__(enrollment_id, student_id, course_code,
                          enrollment_year, marks=None, status="waitlisted")
        self.waitlist_position: int = waitlist_position

    def is_active(self) -> bool:
        # A waitlisted student is not actively enrolled yet.
        return False

    def calculate_grade(self) -> str:
        # A waitlisted student has no marks to grade.
        return "N/A"

    def __repr__(self) -> str:
        return (f"WaitlistedEnrollment(id={self.enrollment_id}, student_id={self.student_id}, "
                f"course_code={self.course_code!r}, position={self.waitlist_position})")


# ============================================================
# EnrollmentRepository interface (Task 2.3b)
# ============================================================
class EnrollmentRepository(ABC):
    """
    Abstraction that Enrollment-related business logic depends on for
    persistence, instead of depending on a concrete database class.

    DIP explanation: without this interface, business logic (e.g., a
    course-registration service) would have to import and call a
    concrete class like `PostgresEnrollmentRepository` directly, tying
    high-level policy to a low-level implementation detail. By depending
    on this abstract interface instead, the business logic is written
    once against `EnrollmentRepository`, and any concrete implementation
    (Postgres, MySQL, an in-memory fake for testing) can be substituted
    without changing the business logic at all. Both the high-level
    module (business logic) and the low-level module (a concrete
    repository) depend on this shared abstraction, which is exactly the
    inversion DIP calls for.
    """

    @abstractmethod
    def save(self, enrollment: Enrollment) -> None:
        """Persist a new or updated Enrollment."""
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, enrollment_id: int) -> Optional[Enrollment]:
        """Retrieve a single Enrollment by its primary key, or None."""
        raise NotImplementedError

    @abstractmethod
    def find_by_student(self, student_id: int) -> List[Enrollment]:
        """Retrieve all Enrollment records belonging to a given student."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, enrollment_id: int) -> bool:
        """Delete an Enrollment by id. Returns True if a row was removed."""
        raise NotImplementedError


if __name__ == "__main__":
    # Small smoke test / usage example.
    s = Student(1001, "Neha Sharma", "Computer Science", "neha@university.edu")
    print(s)

    e = Enrollment(1, 1001, "CS101", 2026, marks=78.5)
    print(e, "-> grade:", e.calculate_grade())

    w = WaitlistedEnrollment(2, 1002, "CS202", 2026, waitlist_position=3)
    print(w, "-> grade:", w.calculate_grade(), "-> active:", w.is_active())
