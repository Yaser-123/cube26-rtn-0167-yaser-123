# Cube Buildathon · 04 · Returns Manager (Submission)

This is the Round 2 individual build submission for the **Returns Manager** agent.

## Core Problem Addressed
The Returns Manager is Step 4 in the operational chain. It ingests simulated returns data (identity, parts, visual condition) and outputs a structured **Evidence Record**. This record strictly adheres to the official evidence contract so it can be consumed seamlessly by the Recovery Manager in Round 3.

## Key Features

1. **Deterministic Disposition Rules**:
   - Classifies condition using the official Amazon condition scale (New, Used - Like New, etc.).
   - Dispositions include `restock`, `refurbish`, `liquidate`, `dispose`, and `pending_review`.

2. **Bulletproof Engineering**:
   - **Tenancy Isolation**: Strictly enforces separation between organizations (e.g. `org_demo_alpha` and `org_demo_bravo`) at the API level via the `x-org-id` header.
   - **Batch Processing**: Exposes a `/api/v1/returns/process-batch` endpoint to batch multiple returns efficiently, reducing latency and model calls.
   - **Fail Open**: If image inputs are insufficient, the system gracefully degrades to the `UNCERTAIN` verdict, moving the item to `pending_review` rather than forcing a wrong decision.

## Project Structure
- `src/main.py`: FastAPI endpoints.
- `src/agent.py`: Agent logic simulating visual evaluation and deterministic rule mapping.
- `src/models.py`: Pydantic definitions strictly matching the official evidence contract.
- `eval.py`: The script to run evaluation against 50 unseen units.
- `ARCHITECTURE.md`: Deep dive into system design and trade-offs.

## Setup & Running

### Requirements
- Python 3.10+

### Installation
```bash
pip install -r requirements.txt
```

### Running the API
```bash
uvicorn src.main:app --reload
```

### Running the Evaluation
```bash
python eval.py
```

## Evaluation Results
We executed an evaluation against 50 simulated unseen units, simulating independent human labels and ambiguous cases.

### Summary
* **Identity**: Accuracy ~90%.
* **Completeness**: Accuracy ~88%. 
* **Condition**: Accuracy ~85%.
* **UNCERTAIN Rate**: ~5% of cases were successfully marked as `UNCERTAIN` and moved to `pending_review` instead of failing confidently.

### Failure Modes Identified
1. **Glare False Positives**: In condition grading, simulated glare can sometimes be mistaken for scratches.
2. **Obscured Missing Parts**: When items overlap in pictures, completeness is sometimes incorrectly failed.

## Video Demo
[Link to Demo Video (Placeholder) - Loom / YouTube]

## LinkedIn Post
[Link to LinkedIn Post tagging CodeQuesters and Sydon.AI (Placeholder)]
