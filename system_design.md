# SARS — System Design (Tasks 2.1 and 2.2)

## Task 2.1 — Requirements and Architecture Choice

### 2.1a — Functional and Non-Functional Requirements

**Functional requirements**

1. A student can log in and view their published marks for each enrolled course.
2. A student can enroll in a course, subject to capacity and prerequisite checks.
3. An administrator can create, update, and delete student, course, and faculty records.

**Non-functional requirements**

| Requirement | Design principle it primarily addresses |
|---|---|
| The system must serve 50,000 concurrent users during result publication without response times degrading past an acceptable threshold. | Scalability |
| The system must remain reachable and serving requests throughout the result-publication window, with minimal planned or unplanned downtime. | Availability |
| Student marks and personal data must be protected from unauthorized access, modification, or interception in transit. | Security |

### 2.1b — Monolithic vs. Microservices

| Dimension | Monolithic | Microservices |
|---|---|---|
| Independent deployment | The whole application is built and deployed as one unit — a small change to the Admin Panel requires redeploying Authentication and the Student Portal too. | Each service (Auth, Student Portal, Admin Panel) can be built, tested, and deployed on its own schedule without touching the others. |
| Fault isolation | A crash or memory leak in one module (e.g., a bug in course enrollment) can bring down the entire process, including login and mark-viewing. | A crash in one service is contained to that service; the others keep running (subject to how well failures are isolated at the call boundaries). |
| Management complexity | Lower complexity: one codebase, one deployment pipeline, one runtime to monitor. | Higher complexity: multiple codebases, service discovery, inter-service network calls, distributed monitoring/logging, and versioning across services. |

**Recommendation**: microservices, for SARS specifically at 50,000-concurrent-user scale. Result-publication day creates a sharp, predictable spike concentrated on the Student Portal (everyone checking marks at once), while Admin Panel and Authentication traffic stays comparatively flat — a microservices split lets the Student Portal be scaled out aggressively and independently without over-provisioning the other modules. It also means a fault in a lower-priority path (for example, an email notification service) cannot take down mark-viewing, which matters when the university explicitly cannot tolerate an outage on this day. The added operational complexity of running multiple services is a real cost, but at this scale and criticality it is outweighed by the ability to scale and isolate failures independently.

## Task 2.2 — High-Level Design

### 2.2a — Main Components

| Component | Single Responsibility | Interface Exposed |
|---|---|---|
| API Gateway | Routes incoming client requests to the correct backend service and terminates TLS. | REST API (HTTP/HTTPS) |
| Authentication Service | Verifies credentials and issues/validates session or JWT tokens. | REST API |
| Student Portal Service | Serves mark-viewing and course-enrollment functionality for students. | REST API |
| Admin Panel Service | Handles CRUD operations on students, courses, and faculty for administrators. | REST API |
| Notification Service | Sends emails and other notifications triggered by events (e.g., marks updated). | Message queue consumer / REST API for direct triggers |
| Database tier | Persists student, course, faculty, and enrollment data. | Database query interface (SQL) |

### 2.2b — Layered Architecture for the Student Portal

1. **Presentation layer**: exposes REST endpoints (e.g., `GET /marks`, `POST /enrollments`). Receives raw HTTP requests, validates request shape/authentication token, converts the request into a plain data structure (DTO), and passes that DTO down to the business layer. It receives back a result object from the business layer and serializes it into an HTTP response (JSON).
2. **Business layer**: contains the actual rules — e.g., "a student cannot enroll in a course above its capacity" or "marks can only be viewed once officially published." It receives DTOs from the presentation layer, applies validation and business rules, and calls the data access layer with the specific data it needs (e.g., "get enrollment count for course X"). It receives domain objects back from the data access layer and returns a result (success/failure, or the requested data) to the presentation layer.
3. **Data access layer**: responsible only for talking to the database — building and executing queries, and mapping rows into domain objects (e.g., `Enrollment`, `Student`). It receives specific requests from the business layer (e.g., "find enrollment by student_id and course_code") and returns domain objects or raw data back up, with no business logic of its own.

### 2.2c — Scaling Strategy for 50,000 Concurrent Users

**Horizontal scaling** is the right choice here, not vertical scaling. Vertical scaling (adding more CPU/RAM to a single server) has a hard ceiling and creates a single point of failure — if that one large server goes down, the entire Student Portal goes down with it, which is unacceptable during result publication. Horizontal scaling (adding more web server instances behind a load balancer) has no such single point of failure, and instances can be added or removed elastically to match the load spike on result day.

**Load-balancing algorithm**: **Least Connections**. Result-viewing and enrollment requests can vary significantly in processing time (a mark lookup is fast; a batch enrollment check involving capacity validation is slower), so a simple Round Robin risks sending new requests to a server that is already tied up with slow requests. Least Connections routes each new request to the server currently handling the fewest active connections, which keeps load balanced even when individual request durations vary — a better fit than Round Robin for this uneven workload.

### 2.2d — Elasticity for Cost Reduction

Elasticity means the number of running web server instances is tied to real-time demand rather than fixed at peak capacity year-round. During off-peak periods (e.g., semester break), an auto-scaling policy monitoring CPU utilization or request rate would detect low load and terminate unneeded instances, so the university only pays for the small baseline capacity actually needed. When examination results approach, the same auto-scaling policy detects rising CPU/request metrics (or is triggered on a schedule known in advance) and automatically launches additional instances to absorb the spike, then scales back down once the surge passes. This avoids paying for 50,000-concurrent-user capacity 365 days a year when it is only needed for a few days around result publication.

### 2.2e — Session Affinity / Distributed Session Problem

**Problem name**: this is the **session affinity problem** (also called the distributed session / lost session problem). Because each web server keeps its own in-memory session store, a session created on Server A during login exists only on Server A. Round-robin load balancing has no awareness of that session, so a later request routed to Server B finds no matching session and treats the user as unauthenticated — the student appears to be logged out mid-session even though they never logged out.

**Strategy 1 — routing-based (sticky sessions)**: configure the load balancer to pin a given client (e.g., via a cookie or client IP hash) to the same server for the duration of their session, so all of that student's requests always land on Server A.
*Trade-off*: this undermines even load distribution — if many long-lived sessions accumulate on one server, that server can become overloaded while others sit idle, and if that server crashes, every session pinned to it is lost.

**Strategy 2 — storage-based (centralized/shared session store)**: move session data out of each web server's memory and into a shared, external store (e.g., Redis) that every web server reads from and writes to, so any server can validate any session regardless of which server created it.
*Trade-off*: this adds an extra network hop (and therefore latency) on every request that needs session validation, and introduces a new piece of infrastructure that itself must be made highly available — the shared session store becomes a potential single point of failure if it isn't also replicated.
