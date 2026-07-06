# SARS — Architecture, Design Pattern, and Redundancy Notes

## 1. Architecture Decisions (Task 2.1)

SARS is recommended to run as a **microservices architecture** (Authentication, Student Portal, Admin Panel, and Notification each as independent services behind an API Gateway), rather than a monolith. The deciding factor is the shape of the load: examination result publication creates an extreme, predictable spike concentrated almost entirely on the Student Portal, while Admin Panel and Authentication traffic stays comparatively steady. Splitting these into independent services means the Student Portal can be scaled out aggressively on result day without over-provisioning (and over-paying for) the other modules. It also means the Notification service — a lower-priority, non-critical path — can fail without taking down mark-viewing or enrollment, which matters given the university's stated zero-tolerance for downtime during result publication. The trade-off accepted here is higher operational complexity (multiple deployable services, inter-service networking, distributed monitoring) in exchange for independent scaling and fault isolation, which is the right trade at 50,000-concurrent-user scale. Full detail, including the requirements list and the layered design for the Student Portal, is in `system_design.md`.

## 2. SOLID Principles Applied (Task 2.3a–b)

Full code is in `lld_classes.py`. Summary of where each principle shows up:

- **Single Responsibility Principle** — `Student` holds only student identity/profile data and behaviour (getters, `update_department`, `assign_advisor`). It has no method for sending emails or any other notification logic; that is a separate concern owned by the Observer-based notification components below, so a change to how emails are sent never requires touching the `Student` class.
- **Open/Closed Principle** — `Enrollment` is open for extension via subclassing. `WaitlistedEnrollment` overrides `is_active()` and `calculate_grade()` to give waitlisted students different behaviour, without a single line of the base `Enrollment` class being modified.
- **Dependency Inversion Principle** — the `EnrollmentRepository` abstract interface defines the persistence operations (`save`, `find_by_id`, `find_by_student`, `delete`) that business logic depends on. Business logic is written against this abstraction, not against a concrete database class, so a concrete implementation (Postgres, MySQL, or an in-memory fake for tests) can be swapped in without changing the business logic that uses it. Both the high-level business logic and the low-level concrete repository depend on the same abstraction — the inversion DIP describes.

## 3. Observer Pattern Rationale (Task 2.3d)

Full code is in `observer_demo.py`. The Admin Panel needs to trigger two unrelated side effects whenever a student's marks are updated — emailing the student and writing an audit log entry — but it should not need to know how either of those things works, or how many notification consumers exist.

The Observer pattern solves this by having the Admin Panel talk only to a `MarksUpdateNotifier` (the subject) and call `notify_marks_updated(student_id, new_marks)`. The notifier keeps a list of registered observers (`EmailNotifier`, `AuditLogNotifier`) and calls `update()` on each of them, but the Admin Panel itself never imports or references `EmailNotifier` or `AuditLogNotifier` directly. This keeps the Admin Panel loosely coupled from the notification services in two concrete ways:

1. **Adding or removing a notification consumer requires no change to the Admin Panel's code.** A new `SmsNotifier` could be attached to the same notifier tomorrow, and the Admin Panel's marks-update code would not change at all.
2. **A failure or slowness in one observer does not need to be known about by the subject or the Admin Panel** — the notifier simply iterates and calls `update()`; the Admin Panel's responsibility ends at calling `notify_marks_updated()`.

This is also directly relevant to Task 2.4b below: because the Admin Panel is not hard-wired to the Email service, the two can be deployed and can fail independently.

## 4. Redundancy and Fault Tolerance (Task 2.4)

### 4a — Database Tier Redundancy

Data is replicated across at least one primary database server and one or more replica servers, rather than relying on a single database instance. Write requests are always directed to the primary, which then propagates changes to the replica(s). Read requests can be served from either the primary or a replica (spreading read load), which also means that if the primary fails, a replica already holds a near-complete copy of the data and can be promoted to take over write traffic, avoiding total data loss and minimizing downtime.

### 4b — Fault Isolation in Microservices

The property that makes this possible is **fault isolation** (services are independently deployed processes with their own failure boundary). In a monolithic design, the Email Notification code runs in the same process and shares the same memory space and request-handling threads as the Student Portal code; an unhandled exception, memory leak, or crash in the email path can crash or hang the entire process, taking mark-viewing and enrollment down with it. In a microservices design, the Email Notification service is a separate process (and typically a separate deployment) — its crash does not touch the Student Portal's process or memory at all.

For this isolation to actually protect the Student Portal, its code must not call the Email service *synchronously and unguarded* on the request path. Specifically, the Student Portal should apply the **circuit breaker pattern** at the call site where it would otherwise call the Email service directly: calls to the Email service are wrapped so that if the Email service is failing or timing out, the circuit "opens," the call is skipped (or queued/fire-and-forgotten) instead of blocking, and the marks-display or enrollment request completes successfully regardless. Without this pattern, even a separately-deployed Email service could still stall or fail the Student Portal's own requests if the Portal waits synchronously on a call that never returns.

### 4c — Synchronous Replication Trade-off and Failover

**Write latency trade-off**: with synchronous replication, every write must wait for the replica to acknowledge receipt before the primary confirms the write to the application — this adds the network round-trip and replica processing time to every single write, so writes are slower than under asynchronous replication (where the primary confirms immediately and forwards to the replica in the background). The benefit purchased with that extra latency is that acknowledged writes are guaranteed to exist on the replica, i.e., zero replica lag for anything the application was told succeeded.

**If the primary crashes before the replica received the last committed transaction** (a scenario that, by definition of synchronous replication, should only happen if the acknowledgment itself never completed):

(i) At the moment of failover, the replica holds all transactions that it acknowledged, but may be missing the very last transaction(s) the primary considered committed if the crash happened between the primary committing locally and the replica's acknowledgment being received.

(ii) A student reading from the newly promoted replica will not see that last, unacknowledged transaction — from their perspective, the most recent change appears to be missing or "rolled back," even though the primary may have briefly recorded it before crashing.

(iii) Before the system is declared fully consistent again, the database administrator must attempt to recover the missing transaction(s) from the crashed primary's write-ahead log (WAL) or binary log, provided that log is still accessible, and replay it onto the newly promoted replica. If the primary's log is not recoverable, the DBA must instead formally acknowledge the small data loss, resynchronize any other remaining replicas against the newly promoted primary's current state, and only then declare the system consistent.
