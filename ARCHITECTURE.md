# Architecture: Returns Manager

## Overview

The Returns Manager is a FastAPI-based AI proxy agent that processes simulated visual and text evidence to determine the disposition of a returned item. It satisfies the requirement of structured, consistent, and evidence-backed decision making in the Cube Buildathon.

## Core Components

1.  **FastAPI Application (`src/main.py`)**
    *   Exposes endpoints for processing single returns (`/api/v1/returns/process`) and batched returns (`/api/v1/returns/process-batch`).
    *   Enforces **Tenancy Isolation** strictly via `x-org-id` headers.

2.  **Returns Agent (`src/agent.py`)**
    *   Simulates an LLM Vision processing pipeline.
    *   Evaluates Identity, Completeness, and Condition (using the standard Amazon scale).
    *   Implements **Fail Open** principles. If the simulated evidence is poor or "blurry", the agent degrades gracefully to an `UNCERTAIN` state and moves the disposition to `pending_review`.

3.  **Data Models (`src/models.py`)**
    *   Implements the official Evidence Contract using `pydantic`.
    *   Ensures that every record produced includes exactly what downstream consumers (like the Recovery Manager) expect (`record_id`, `schema_version`, `checks`, `content_hash`, etc.).

## Engineering Decisions

*   **Tenancy Isolation:** Implemented at the API boundary. The model itself never crosses tenant contexts because the API layer rejects requests that try to process a unit_id outside of the caller's authorized tenant namespace.
*   **Batch Model Calls:** The `/process-batch` endpoint takes an array of items, which in a real LLM deployment would be batched into a single large prompt or parallelized inference queue to minimize latency.
*   **Handling Uncertainty:** The code explicitly checks for low-confidence conditions. Instead of forcing a guess (which causes false positives), it marks the check as `UNCERTAIN`.

## Dependencies
*   Python 3.10+
*   FastAPI
*   Pydantic

## Security
No secrets are committed. Tenant IDs act as a mock authorization mechanism in this environment.
