# Technology Stack

## Language & Runtime

### Primary Reference Implementation
- **Python 3.11+**
  - Used as the initial implementation language
  - Suitable for orchestration, reasoning, planning logic, and rapid iteration

### Alternative / Complementary Runtimes
- **Go**
  - Recommended for high-performance APIs, workers, and event processors
  - Low memory footprint and strong concurrency model

- **Node.js (18+)**
  - Suitable for webhook-heavy services, real-time integrations, and glue services
  - Strong ecosystem for API tooling and agent/MCP integration

> Language choice is not fixed. Each component may use the runtime that best fits its purpose.

---

## Architectural Style

- **API-First**
  - All core functionality must be exposed via a versioned HTTP API
  - CLI and other interfaces are thin clients over the API
  - No business logic is allowed exclusively in the CLI

- **Event-Driven & Reactive**
  - Prefer asynchronous communication over polling
  - Support pub/sub and webhooks as first-class mechanisms

- **Cloud & Serverless Ready**
  - Components must be stateless
  - Compatible with container-based and serverless platforms

- **Local-First with Docker**
  - Full system must be runnable locally using Docker
  - Local setup must mirror production behavior as closely as possible

---

## Core API Layer

- **HTTP REST API**
  - OpenAPI 3.1 specification
  - Versioned endpoints (`/api/v1/...`)
  - JSON as primary data format

- **Authentication**
  - API token / bearer token authentication
  - Designed for server-to-server usage
  - Extensible to OAuth2 / OIDC if required

---

## Core Dependencies (Python Reference Stack)

- **httpx**
  - Async HTTP client for external integrations

- **pydantic v2**
  - Data validation and schema definition
  - Used for API contracts and OpenAPI generation

- **pytest**
  - Unit and integration testing framework

- **hypothesis**
  - Property-based testing library

- **python-markdown**
  - Markdown parsing and validation

---

## Eventing & Communication

### Supported Patterns
- **Pub/Sub**
  - Cloud-native: SNS/SQS, EventBridge, GCP Pub/Sub
  - Self-hosted: NATS, Redis Streams

- **Webhooks**
  - Outbound events:
    - Task classified
    - Plan generated
    - Approval requested / resolved
  - Inbound hooks for:
    - External triggers
    - JIRA events
    - Manual overrides

- **Polling**
  - Allowed only when push-based mechanisms are unavailable
  - Fully configurable and minimized

---

## Testing Strategy

### Unit Tests
- Deterministic logic and edge cases
- Task classification rules
- Planning and scheduling logic
- Markdown output generation

### Property-Based Tests
- Hypothesis-driven invariant validation
- Minimum 100 iterations per property
- Naming convention:
  - `Feature: ai-secretary, Property {N}: {property_text}`
- Custom generators:
  - JiraIssue
  - TaskClassification
  - DailyPlan

### Integration Tests
- JIRA test instance or mock server
- Full API workflows end-to-end
- Event emission and webhook delivery

---

## External Integrations

- **JIRA REST API**
  - Task ingestion and synchronization
  - Webhook consumption when available

- **Authentication**
  - Email + API token
  - Stored via environment variables or secret managers

---

## CLI

- Optional and secondary interface
- Strictly an API client
- No domain logic inside the CLI

Example:
```bash
ai-secretary generate-plan --date today
```

---

## Containerization & Deployment

- **Docker**
  - Mandatory for all services
  - Multi-stage builds where applicable

- **Docker Compose**
  - Local development and prototyping
  - Full stack simulation

- **Serverless Compatibility**
  - AWS Lambda + API Gateway
  - GCP Cloud Run / Functions
  - Azure Functions

---

## MCP (Model Context Protocol) Readiness

- API and schemas must allow:
  - Automatic MCP generation from OpenAPI
  - Exposure of tools, actions, and resources
- Enables AI agent and LLM orchestration

---

## Configuration

- Environment variables as primary mechanism
- Optional config file (YAML or TOML)
- Configurable:
  - JIRA credentials
  - Event backend
  - Webhook endpoints
  - Polling intervals
  - Approval timeouts (default: 24h)
  - Energy / focus windows

## Mandatory 

- To add in all the files this header:
```
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)
```
- Remember to use uv instead of pip to manage and install packages
- Put all the demos into examples folder and all the documents to clarify or audit something into docs folder
- All the comments and texts for documentation shuold be in english
- Use always the commands created in the makefile instead of running native commands
- Remember that the docker project is named "triage"