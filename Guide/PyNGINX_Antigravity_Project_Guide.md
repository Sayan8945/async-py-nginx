# PyNGINX --- Project Specification & Implementation Guide

> **Purpose:** Build an educational, Python-only reverse proxy and load
> balancer inspired by NGINX, starting from raw TCP sockets and
> `asyncio`, with HTTPS/TLS support.
>
> **Target IDE:** Google Antigravity\
> **Implementation style:** Incremental, test-driven, security-conscious
> systems engineering\
> **Budget:** ₹0 --- local development with free, open-source tools\
> **Initial protocol scope:** HTTP/1.1 over TLS (HTTPS)\
> **Important:** This is an educational implementation, not a production
> replacement for NGINX.

------------------------------------------------------------------------

## 1. Instructions for the AI coding agent

Use this document as the source of truth for the project. Work
incrementally and do not generate the entire system in one pass.

### Mandatory working rules

1.  Inspect the existing repository before changing files.
2.  If the repository is empty, create the structure described in this
    document.
3.  Implement one phase at a time. Do not skip ahead.
4.  Before implementing a phase, provide a short plan listing files to
    create or modify.
5.  Write maintainable, typed Python code with clear module boundaries.
6.  Add tests alongside each feature. Prefer `pytest` and
    `pytest-asyncio`.
7.  Run relevant tests after each meaningful change and fix failures
    before continuing.
8.  Never claim a feature works unless it has been implemented and
    tested.
9.  Do not replace the raw-socket core with FastAPI, Flask, Starlette,
    aiohttp, or another web framework.
10. Do not use a third-party reverse-proxy package. The proxy core must
    be implemented by this project.
11. Third-party libraries may be used for supporting tasks such as YAML
    configuration, test clients, metrics exposition, and load testing.
12. Explain important networking and protocol decisions in comments or
    documentation.
13. Do not silently introduce breaking changes. Update tests and
    documentation when interfaces change.
14. Keep secrets, private keys, local certificates, logs, virtual
    environments, and generated data out of Git.
15. Ask before adding paid services, cloud dependencies, or external
    APIs. The default is fully local and free.
16. Do not proceed to the next phase until the current phase's
    acceptance criteria pass.

### First action

Inspect the repository and report: - Existing files and project state. -
Python version available. - Whether Git is initialized. - Whether the
required development tools are available.

Then propose the smallest safe implementation step. Do not overwrite
existing user work.

------------------------------------------------------------------------

## 2. Project vision

PyNGINX is a lightweight reverse proxy that accepts client connections,
terminates TLS, parses HTTP/1.1 requests, selects an upstream backend,
forwards requests, and returns backend responses.

The project is intended to teach:

-   TCP socket programming.
-   Asynchronous I/O and connection lifecycle management.
-   TLS handshakes and certificate configuration.
-   HTTP/1.1 parsing and message framing.
-   Reverse proxying and header management.
-   Load-balancing algorithms.
-   Health checking and failover.
-   Backpressure, timeouts, and resource limits.
-   Caching and rate limiting.
-   Metrics, observability, and performance testing.

### Non-goals

The first versions will not attempt to: - Match NGINX's production
performance. - Implement HTTP/2 or HTTP/3. - Support every HTTP
extension. - Provide a production-grade WAF. - Replace a mature
production reverse proxy. - Provide distributed configuration or
multi-node clustering.

------------------------------------------------------------------------

## 3. Technology choices

  -----------------------------------------------------------------------
  Area                                Technology
  ----------------------------------- -----------------------------------
  Language                            Python 3.12+

  Async networking                    `asyncio`

  TCP server                          `asyncio.start_server` / raw socket
                                      APIs

  TLS                                 Standard-library `ssl`

  HTTP protocol                       Project-owned HTTP/1.1 parser and
                                      serializer

  Configuration                       YAML via PyYAML

  Backend demo services               FastAPI (test/demo backends only)

  Outbound test client                `httpx` for tests; core upstream
                                      transport should be project-owned

  Tests                               pytest, pytest-asyncio

  Load testing                        Locust

  Metrics                             Prometheus client library or a
                                      minimal internal metrics registry

  Packaging                           `pyproject.toml`

  Containers                          Docker, optional

  Version control                     Git and GitHub
  -----------------------------------------------------------------------

### Dependency policy

Keep the core small. Prefer Python standard-library modules for
networking, TLS, parsing, synchronization, and data structures.

Do not add dependencies without explaining: - Why the dependency is
needed. - Whether the standard library can reasonably do the same job. -
Whether it is runtime-only or development-only.

All dependencies must be free and installable locally.

------------------------------------------------------------------------

## 4. High-level architecture

``` text
                         CLIENTS
                 Browser / curl / API client
                            |
                            | HTTPS
                            v
                  +--------------------+
                  | TLS Termination    |
                  | ssl.SSLContext     |
                  +--------------------+
                            |
                            v
                  +--------------------+
                  | TCP Connection     |
                  | Manager            |
                  +--------------------+
                            |
                            v
                  +--------------------+
                  | HTTP/1.1 Parser     |
                  | Framing + Validation|
                  +--------------------+
                            |
                            v
                  +--------------------+
                  | Request Pipeline   |
                  | Routing / Policies |
                  +--------------------+
                            |
              +-------------+-------------+
              |             |             |
              v             v             v
        +-----------+ +-----------+ +-----------+
        | Rate      | | Cache     | | Access    |
        | Limiter   | | (later)   | | Policy    |
        +-----------+ +-----------+ +-----------+
                            |
                            v
                  +--------------------+
                  | Load Balancer      |
                  | RR / Weighted / LC |
                  +--------------------+
                            |
                            v
                  +--------------------+
                  | Upstream Manager   |
                  | Connect / Pool     |
                  +--------------------+
                            |
                +-----------+-----------+
                |           |           |
                v           v           v
             Backend 1   Backend 2   Backend 3
                |
                v
          Response handling
                |
                v
          Client HTTPS response

      Supporting components:
      - Health checker
      - Structured access/error logging
      - Metrics endpoint
      - YAML configuration
      - Graceful shutdown
```

### Important architecture principles

1.  Keep the event loop responsive. Do not perform blocking disk,
    network, or CPU-heavy operations in request handlers.
2.  Use bounded buffers and explicit size limits.
3.  Use timeouts for TLS handshakes, client reads, upstream connects,
    upstream reads, and writes.
4.  Keep request parsing separate from routing and forwarding.
5.  Keep load-balancing algorithms independent from the network server.
6.  Do not allow multiple tasks to mutate shared backend state without
    synchronization.
7.  Track active upstream connections accurately, including failures and
    cancellation.
8.  Do not retry non-idempotent requests by default.
9.  Use structured error types and predictable HTTP error responses.
10. Prefer streaming request and response bodies over unbounded
    buffering.

------------------------------------------------------------------------

## 5. Repository structure

Use this structure as the target. Create directories as each phase needs
them; avoid empty placeholder modules.

``` text
pynginx/
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── config/
│   └── pynginx.example.yaml
├── certs/
│   └── README.md
├── src/
│   └── pynginx/
│       ├── __init__.py
│       ├── main.py
│       ├── cli.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── loader.py
│       │   └── schema.py
│       ├── network/
│       │   ├── __init__.py
│       │   ├── server.py
│       │   ├── connection.py
│       │   └── tls.py
│       ├── protocol/
│       │   ├── __init__.py
│       │   ├── http_parser.py
│       │   ├── http_models.py
│       │   ├── framing.py
│       │   └── serializer.py
│       ├── proxy/
│       │   ├── __init__.py
│       │   ├── handler.py
│       │   ├── router.py
│       │   ├── upstream.py
│       │   └── headers.py
│       ├── load_balancer/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── round_robin.py
│       │   ├── weighted_round_robin.py
│       │   └── least_connections.py
│       ├── health/
│       │   ├── __init__.py
│       │   └── checker.py
│       ├── middleware/
│       │   ├── __init__.py
│       │   ├── rate_limiter.py
│       │   └── cache.py
│       ├── observability/
│       │   ├── __init__.py
│       │   ├── logging.py
│       │   └── metrics.py
│       └── errors.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   └── performance/
├── examples/
│   └── demo_backends/
├── scripts/
│   ├── generate_dev_cert.sh
│   └── run_demo.sh
├── benchmarks/
├── docs/
│   ├── architecture.md
│   ├── protocol-support.md
│   └── benchmark-results.md
└── docker/
    └── Dockerfile
```

------------------------------------------------------------------------

## 6. Functional requirements

### 6.1 Listener and TLS

-   Listen on a configurable host and port.
-   Support TLS termination for client HTTPS connections.
-   Load certificate and private key from configuration.
-   Require TLS 1.2 or newer by default.
-   Set a TLS handshake timeout.
-   Report certificate loading errors clearly.
-   Support local self-signed certificates for development.
-   Never commit private keys.
-   Later support TLS to upstream backends with certificate verification
    enabled by default.

### 6.2 HTTP/1.1 protocol handling

Implement a deliberately scoped HTTP/1.1 parser.

Required: - Request line parsing. - Header parsing. - Header-name
case-insensitivity. - Header value validation. - `Content-Length` body
framing. - `Transfer-Encoding: chunked` decoding. - Persistent
connections. - Multiple requests on a single connection. -
`Connection: close` behavior. - Correct response serialization. -
Bounded request-line, header, trailer, and body sizes. - Read and idle
timeouts.

Reject or safely handle: - Malformed request lines. - Invalid header
names. - Conflicting or duplicate framing headers. - Invalid
`Content-Length`. - Unsupported transfer codings. - Invalid chunk
sizes. - Incomplete request bodies. - Oversized headers or bodies. -
Unsupported HTTP versions. - Requests with ambiguous message framing.

Do not treat this initial parser as production-safe until the security
tests pass.

### 6.3 Reverse proxy

-   Forward requests to configured upstream servers.
-   Preserve method, path, query string, and body.
-   Reconstruct hop-by-hop headers correctly.
-   Remove or process headers named by the `Connection` header.
-   Set `Via` and `X-Forwarded-For` carefully.
-   Avoid trusting client-supplied forwarding headers by default.
-   Preserve end-to-end response headers.
-   Stream response bodies where practical.
-   Return useful gateway errors for upstream failures.
-   Enforce upstream connect and response timeouts.

### 6.4 Load balancing

Implement independently testable strategies:

1.  Round Robin.
2.  Weighted Round Robin.
3.  Least Connections.

Requirements: - Exclude unhealthy backends. - Avoid selecting a backend
marked unavailable. - Maintain active connection counts correctly. -
Define behavior when all backends are unhealthy. - Make selection
deterministic in unit tests where possible.

### 6.5 Health checking

-   Configurable health-check interval.
-   Configurable health-check path.
-   Connect and response timeouts.
-   Consecutive failure threshold.
-   Recovery after successful checks.
-   Health status visible through logs and metrics.

### 6.6 Rate limiting

Implement a token-bucket limiter initially.

-   Configurable request rate and burst.
-   Configurable identity key (initially client IP).
-   Return HTTP 429 when limited.
-   Avoid unbounded storage of client identities.
-   Add expiry/cleanup for inactive buckets.
-   Document that an in-memory limiter is per-process.

### 6.7 Response caching

Add caching only after proxy correctness is established.

-   Cache only explicitly eligible responses.
-   Respect relevant HTTP cache headers.
-   Do not cache authenticated or personalized responses by default.
-   Include method and URL in the cache key.
-   Enforce maximum object size and total cache size.
-   Implement TTL and eviction.
-   Avoid serving stale or unsafe content.

### 6.8 Observability

Provide: - Access logs. - Error logs. - Request count. - Response status
counts. - Request duration histogram. - Active client connections. -
Active upstream connections. - Backend health state. - Upstream error
count.

Do not log passwords, authorization tokens, cookies, or sensitive
request bodies.

------------------------------------------------------------------------

## 7. Configuration design

Use YAML. Begin with a small configuration and expand it as features
arrive.

Example target configuration:

``` yaml
server:
  host: "127.0.0.1"
  port: 8443
  tls:
    enabled: true
    certificate: "certs/server.crt"
    private_key: "certs/server.key"
    minimum_version: "TLSv1.2"
  limits:
    max_connections: 1000
    max_header_bytes: 65536
    max_body_bytes: 1048576
    request_timeout_seconds: 15
    idle_timeout_seconds: 30

upstreams:
  - name: "api_pool"
    strategy: "round_robin"
    servers:
      - url: "http://127.0.0.1:8001"
        weight: 1
      - url: "http://127.0.0.1:8002"
        weight: 1
      - url: "http://127.0.0.1:8003"
        weight: 1

health_check:
  enabled: true
  path: "/health"
  interval_seconds: 5
  timeout_seconds: 2
  failure_threshold: 3
  recovery_threshold: 2

rate_limit:
  enabled: true
  requests_per_second: 20
  burst: 40

logging:
  level: "INFO"
  access_log: true

metrics:
  enabled: true
  host: "127.0.0.1"
  port: 9100
```

The example is a target schema, not a claim that every option exists in
the first phase. Validate configuration at startup and reject unknown or
invalid values where appropriate.

------------------------------------------------------------------------

## 8. Implementation phases and acceptance criteria

Do not skip phases. Each phase must have tests and a short
implementation report.

### Phase 0 --- Repository bootstrap

Tasks: - Inspect repository. - Create package structure. - Add
`pyproject.toml`. - Add `.gitignore`. - Configure formatting and
linting. - Add pytest configuration. - Write README with setup
instructions.

Acceptance: - Package imports successfully. - Tests run. - No secrets or
generated artifacts are tracked.

### Phase 1 --- TCP + TLS + minimal HTTP parser

Tasks: - Create an asyncio TCP listener. - Configure TLS termination
using `ssl.SSLContext`. - Load a local development certificate. - Accept
a TLS connection. - Parse a bounded HTTP request line and headers. -
Parse a bounded `Content-Length` body. - Return a valid HTTP response. -
Close the connection cleanly.

Initial implementation scope: - HTTP/1.1 request line. - Header
parsing. - `Content-Length`. - Basic GET and POST. - One request per
connection initially. - Explicitly reject unsupported transfer
encodings.

Security requirements: - Enforce header and body limits. - Reject
malformed request lines. - Reject conflicting `Content-Length` values. -
Reject `Content-Length` combined with `Transfer-Encoding`. - Apply
timeouts to incomplete requests. - Do not use unbounded `read()`
calls. - Do not trust malformed or ambiguous message framing.

Acceptance tests: - Valid HTTPS GET returns 200. - Valid HTTPS POST body
is parsed. - Missing HTTP/1.1 Host is rejected. - Malformed request line
is rejected. - Oversized headers are rejected. - Oversized body is
rejected. - Incomplete body times out or closes safely. - TLS handshake
works with the development certificate. - TLS minimum version is
enforced.

Important correction: Do not use a broad `except Exception` to turn
every failure into a 400 response. Distinguish protocol errors, timeout,
disconnect, TLS errors, and internal server errors.

### Phase 2 --- HTTP connection management

Tasks: - Persistent HTTP/1.1 connections. - Multiple requests per
connection. - Keep-alive and `Connection: close`. - Chunked request-body
decoding. - Chunked response serialization where required. - Connection
and idle timeouts. - Per-connection request limits. - Graceful shutdown.

Acceptance: - Multiple sequential requests on one TLS connection work. -
Connection close semantics are correct. - Chunked bodies are parsed
correctly. - Malformed chunk framing is rejected. - Slow clients cannot
hold resources indefinitely.

### Phase 3 --- Reverse proxy

Tasks: - Configure one upstream. - Forward request method, target,
headers, and body. - Read upstream response. - Forward status, headers,
and body. - Handle hop-by-hop headers. - Add forwarding metadata
safely. - Add upstream connection and read timeouts. - Return
502/503/504 as appropriate.

Acceptance: - GET and POST pass through correctly. - Query strings and
bodies are preserved. - Backend errors are handled. - Client disconnects
do not leak upstream connections. - Hop-by-hop headers are not
incorrectly forwarded.

### Phase 4 --- Load balancing

Tasks: - Multiple upstreams. - Round Robin. - Weighted Round Robin. -
Least Connections. - Active connection accounting. - Backend
availability filtering.

Acceptance: - Round Robin distributes requests as expected. - Weighted
strategy respects configured weights over a sample. - Least Connections
chooses the least-loaded eligible backend. - Failed requests do not
leave counters incorrect.

### Phase 5 --- Health checks and failover

Tasks: - Periodic health probes. - Healthy/unhealthy state. - Failure
and recovery thresholds. - Exclude unhealthy backends. - Safe retry
policy.

Acceptance: - Stopped backend becomes unhealthy. - Healthy backends
continue receiving traffic. - Recovered backend returns to rotation. -
Non-idempotent requests are not retried automatically.

### Phase 6 --- Connection management and performance

Tasks: - Upstream connection pooling. - Bounded queues and semaphores. -
Backpressure. - Cancellation safety. - Graceful draining. - Memory
profiling.

Acceptance: - Concurrent load does not exceed configured limits. -
Connections are released on success, timeout, cancellation, and error. -
Memory use remains bounded under sustained test load.

### Phase 7 --- Rate limiting and caching

Implement token bucket first, then conservative response caching.

Acceptance: - Rate limit returns 429 after burst is exhausted. - Bucket
state is bounded and cleaned up. - Cache respects eligibility and safety
rules. - Cache hit/miss metrics are available.

### Phase 8 --- Metrics and logs

Acceptance: - Access and error logs are useful and redact secrets. -
Metrics endpoint exposes request counts, latency, active connections,
and upstream errors. - Monitoring endpoint is not publicly exposed by
default.

### Phase 9 --- Packaging and deployment

Tasks: - CLI entry point. - YAML config validation. - Dockerfile. - Demo
backend services. - Example configuration. - Integration test script. -
Benchmark instructions. - Architecture and protocol documentation.

Acceptance: - A new developer can run the project locally using README
instructions. - Demo works without paid services. - Tests can run
locally. - Docker deployment works if Docker is installed.

------------------------------------------------------------------------

## 9. Phase 1 implementation details

### 9.1 Development certificate

For local testing only, create a self-signed certificate with a Subject
Alternative Name for localhost.

Example OpenSSL command:

``` bash
mkdir -p certs

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout certs/server.key \
  -out certs/server.crt \
  -days 365 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

Add these to `.gitignore`:

``` gitignore
certs/*.key
certs/*.crt
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
*.log
.env
```

Commit a `certs/README.md` explaining how to generate local
certificates, not the private key itself.

### 9.2 Initial HTTP request model

Use a typed model, for example:

``` python
from dataclasses import dataclass

@dataclass(slots=True)
class HTTPRequest:
    method: str
    target: str
    version: str
    headers: dict[str, str]
    body: bytes
```

Keep parsing functions independent from the TCP server so they can be
tested using in-memory streams or controlled reader/writer fakes.

### 9.3 Parser implementation requirements

The first parser must: - Read through the header terminator with a
strict limit. - Validate the request line. - Validate header names. -
Preserve or safely normalize header values. - Reject conflicting
duplicate `Content-Length`. - Reject `Transfer-Encoding` in Phase 1
rather than silently misparse it. - Reject `Content-Length` combined
with `Transfer-Encoding`. - Require Host for HTTP/1.1. - Read exactly
the declared body length. - Apply a timeout. - Never allocate based on
an unchecked client-provided length.

Do not use simplistic `split(" ")` parsing without validating the number
of fields and allowed characters.

### 9.4 TLS server requirements

Use: - `ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)`. -
`minimum_version = ssl.TLSVersion.TLSv1_2`. - `load_cert_chain(...)`. -
`asyncio.start_server(..., ssl=context, ssl_handshake_timeout=...)`.

Keep certificate paths configurable. Do not disable TLS verification for
outbound HTTPS backends.

### 9.5 Response requirements

For the initial response: - Use a valid status line. - Include
`Content-Length`. - Include `Content-Type`. - Use `Connection: close`
while one-request-per-connection is the current scope. - Terminate
headers with `\r\n\r\n`. - Encode the body as bytes.

------------------------------------------------------------------------

## 10. Testing strategy

Use three layers of tests.

### Unit tests

-   HTTP request-line parsing.
-   Header parsing.
-   Header validation.
-   Content-Length validation.
-   Body framing.
-   HTTP response serialization.
-   Load-balancer selection.
-   Rate limiter behavior.

### Integration tests

-   Start PyNGINX on a local ephemeral port.
-   Establish a TLS client connection.
-   Send valid and invalid requests.
-   Verify status codes and response framing.
-   Start local backend services for proxy tests.
-   Simulate backend shutdown and recovery.

### Security tests

At minimum: - Header too large. - Body too large. - Invalid header
names. - Duplicate Content-Length. - Conflicting Content-Length. -
Content-Length plus Transfer-Encoding. - Invalid chunk size. -
Incomplete body. - Slowloris-style slow headers. - Invalid request
target. - Unsupported transfer coding. - Client disconnect during body
upload. - Upstream timeout. - Malformed upstream response.

Never claim the proxy is secure merely because these tests pass.
Document known limitations.

------------------------------------------------------------------------

## 11. Benchmarking plan

Benchmark only after functional correctness is established.

Measure: - Requests per second. - p50, p95, and p99 latency. - Error
rate. - Concurrent active connections. - CPU usage. - Memory usage. -
Throughput in bytes per second.

Compare: 1. Direct request to backend. 2. Request through PyNGINX. 3.
Request through a locally installed NGINX instance, if available.

Use the same machine, payload, concurrency, and test duration for fair
comparisons.

Do not invent benchmark numbers. Save raw results and record machine
specs, Python version, configuration, and test command.

------------------------------------------------------------------------

## 12. Free local development setup

No paid services are required.

Suggested setup:

``` bash
python -m venv .venv
```

Windows PowerShell:

``` powershell
.venv\Scripts\Activate.ps1
```

Linux/macOS:

``` bash
source .venv/bin/activate
```

Install development dependencies after creating `pyproject.toml`:

``` bash
pip install -e ".[dev]"
```

Use local loopback addresses and local backend processes. Docker is
optional; the project must remain runnable without Docker.

------------------------------------------------------------------------

## 13. Definition of done

The project is considered complete when:

-   [ ] HTTPS listener works with TLS 1.2+.
-   [ ] HTTP/1.1 parser handles supported framing correctly.
-   [ ] Persistent connections work.
-   [ ] Reverse proxy forwards requests and responses.
-   [ ] Round Robin, Weighted Round Robin, and Least Connections work.
-   [ ] Backend health checks and failover work.
-   [ ] Timeouts and connection limits are enforced.
-   [ ] Rate limiting works.
-   [ ] Safe response caching works.
-   [ ] Metrics and logs are available.
-   [ ] Unit, integration, and security tests pass.
-   [ ] Benchmarks are reproducible.
-   [ ] README and architecture documentation are complete.
-   [ ] No paid services are required.
-   [ ] No private keys or secrets are committed.

------------------------------------------------------------------------

## 14. First task for Antigravity

Start with **Phase 0 and Phase 1 only**.

1.  Inspect the workspace and existing files.
2.  Report the detected Python version and environment.
3.  Create or adapt the project structure without overwriting existing
    work.
4.  Set up `pyproject.toml`, `.gitignore`, and pytest.
5.  Implement the minimal TLS-enabled asyncio TCP server.
6.  Implement the initial bounded HTTP/1.1 request parser for request
    line, headers, and Content-Length.
7.  Implement a valid JSON HTTP response.
8.  Add unit and integration tests for Phase 1.
9.  Generate a local development certificate using the documented script
    or instructions.
10. Run the tests and report exact results.

### Required final report after Phase 1

Provide: - Files created or modified. - Architecture implemented. -
Commands to install and run. - Commands to generate the certificate. -
Exact test results. - Known limitations. - Any security concerns. -
Confirmation that no paid service was used.

**Do not start Phase 2 automatically. Stop and wait for approval after
Phase 1 passes.**

------------------------------------------------------------------------

## 15. Engineering references

Use official documentation as the primary reference:

-   Python asyncio: https://docs.python.org/3/library/asyncio.html
-   Python SSL: https://docs.python.org/3/library/ssl.html
-   Python socket: https://docs.python.org/3/library/socket.html
-   HTTP Semantics (RFC 9110): https://www.rfc-editor.org/rfc/rfc9110
-   HTTP/1.1 (RFC 9112): https://www.rfc-editor.org/rfc/rfc9112
-   NGINX documentation: https://nginx.org/en/docs/
-   Pytest: https://docs.pytest.org/
-   Locust: https://docs.locust.io/

**Project principle:** Correct protocol behavior, bounded resource use,
deterministic tests, and clear architecture are more important than
adding features quickly.
