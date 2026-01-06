<img width="1337" height="271" alt="image" src="https://github.com/user-attachments/assets/d47aa55f-d0b9-495b-a6b1-19f21ea855c6" />[Temporarily paused] NYC Property Deeds Q&A with Integrated AI
================================================

## Description

Deployed a scalable  web app with LLM integration on GCP, containerizing a full-stack solution with Docker via REST API to deliver Pinecone-based vector search (lexical and semantic) over 500k+ property records with BigQuery-powered access control.

**Link:** [http://34.86.83.238:8000/](http://34.86.83.238:8000/)

## System Overview

React UI (built with Node/Vite) sends a question to a Python FastAPI service, which triggers Airflow to run data/AI steps; Airflow produces a natural-language answer (using DuckDB/dbt + Pinecone + Gemini), FastAPI returns it, React shows it. Everything runs in Docker containers on a GCP Compute Engine (VM: e2-standard-2 with 2 vCPUs and 8 GB Memory, OS: Debian GNU/Linux 12) with BigQuery access control enforcing 3 queries per day per IP and top ranked record matches ≤ 100 limits.

## Process Overview

1. User types a question in the React page.
2. The page sends the question to the Python FastAPI server.
3. FastAPI checks BigQuery for IP-based query limits (3 queries/day) and validates top_k ≤ 100.
4. If limits exceeded, FastAPI returns 429/400 error without triggering DAG.
5. If allowed, FastAPI calls the Airflow REST API to trigger a DAG run.
6. Airflow runs tasks in Docker containers:
   - Build dbt models
   - Upsert and search vectors using the VectorDB's integrated embedding models
   - Call the Gemini API to route the question and generate an answer
7. FastAPI polls the Airflow REST API to get the result.
8. FastAPI logs the successful query to BigQuery for access control tracking.
9. FastAPI sends the result back to the browser.
10. React displays the answer to the user.

## Tech Stack

- **React.js**: UI in the browser.
- **Node.js/Vite**: builds the React app.
- **FastAPI**: main backend that coordinates and returns answers.
- **Airflow**: orchestrates the  workflow.
- **Docker**: runs each task in its own container.
- **Compose**: defines setup and runs Docker containers together as one stack.
- **PostgresSQL**: stores Airflow metadata.
- **Redis**: handles task queuing used by Airflow's Celery executor.
- **DuckDB + dbt**: quick lightweight db + data transformation.
- **Pinecone VectorDB**: serverless vector database with integrated embedding to upsert and search text
- **BigQuery**: cloud data warehouse for access control and query logging.
- **Gemini 2.5 Flash Lite**: LLM that routes queries + creates the final answer.
- **GCP VM**: server host (machine/IP) where containers run. 

## DevOps/SRE Features

- Containerization of each service.
- BigQuery access control: IP-based rate limiting and resource validation.
- Query logging: All successful requests logged to BigQuery for governance tracking.
- Health checks in Compose:
  - **Postgres check** (every 5s, 5 retries): *Checks if the database is accepting connections.*
  - **Redis** (every 5s, 5 retries): *Sends a ping to Redis, expects pong back.*
  - **Airflow webserver** (every 30s, 30s start period, 5 retries): *Makes an HTTP request to Airflow's health endpoint.*
- Startup dependencies in Compose:
  - `airflow-init` waits for Postgres/Redis healthy.
  - Webserver/Scheduler/Worker wait for `airflow-init` success.
  - `api` waits for webserver healthy.
- Env variables for credentials/URLs.



## Suggested Expansion

### a. Logging and metrics

- **Tracing/metrics**: use OpenTelemetry SDKs for FastAPI and Airflow to capture request timing and failures.
- **Dashboards/alerts**: Cloud Monitoring for error rates, latency, task failures.
- **BigQuery analytics**: Create dashboards showing query patterns, user behavior, and access control metrics.
- **Cost optimization**: Add query cost tracking and automatic throttling for expensive operations.

### b. CI/CD

- **CI**: on git push, run tests, build images.
- **Security**: scan Docker images for vulnerabilities.
- **CD**: to deploy new images to the GCP VM if CI passes,
- **Rollback**: keep last known good image/version.

