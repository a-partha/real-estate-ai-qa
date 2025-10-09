NYC Property Deeds Q&A with Integrated AI
================================================

OVERVIEW
--------

A full-stack pipeline for natural language question-answering on NYC ACRIS property records using TF-IDF vector search, LLM (Gemini) integration, Apache Airflow orchestration, and a React web frontend hosted on Google Cloud Platform. Designed for easier semantic retrieval on any large dataset.

Live demo link: [http://34.86.83.238:8000/](http://34.86.83.238:8000/)

CORE PIPELINE WORKFLOW
----------------------

-   Data ingest (CSV/DuckDB) → Vectorization (TF-IDF) → LLM Query with context → Response via React frontend.

-   All backend API and pipeline steps orchestrated by Airflow.

-   Single Docker Compose file spins up database, Airflow, API, and frontend containers.

TECH STACK
----------

-   Python (API, pipelines, Airflow DAGs)

-   Docker Desktop (for Windows) or Docker Engine (for GCP Ubuntu VM)

-   Docker Compose

-   Git

-   Google Gemini (LLM, requires API Key)

-   React (web frontend)

-   DuckDB (local analytical DB, data storage)

-   DBT (data modeling)

-   GCP e2-standard-2 VM (Ubuntu 22.04 LTS, Intel Broadwell, 30GB disk)

-   Airflow (workflow orchestration)

KEY COMPONENTS
--------------

-   /api : Python FastAPI endpoints for queries

-   /dags : Airflow Directed Acyclic Graphs (DAGs) for pipeline task automation

-   /data : Property records and metadata downloaded from [NYC Open Data Portal](https://data.cityofnewyork.us/City-Government/ACRIS-Real-Property-Legals/8h5j-fqxa/about_data))

-   /web : React Single-Page Application (SPA) frontend

-   docker-compose.yaml : Orchestration for all containers/services

-   .env : Required for secret keys and configuration information

INSTRUCTIONS
------------

1.  TOOLS, SOFTWARE & PACKAGE PREREQUISITES

    -   Windows PC for local prep and SSH, GCP VM as deployment target.

    -   Docker Desktop (for local; GCP VM uses Docker Engine)

    -   PowerShell (Windows)

    -   Google Account for Gemini API Key

2.  PROJECT PREPARATION

    -   Clone the repo to your local machine

    -   Create a single `.env` file. Example content:

        `AIRFLOW_API_BASE_URL=<your airflow webserver url> AIRFLOW_USER=<your admin user> AIRFLOW_PW=<password> GOOGLE_API_KEY=<your Gemini API Key> `

    -   Do NOT commit your `.env` file.

3.  GCP VM SETUP (as provided earlier)

    -   Create a VM instance. For example:

        -   Machine Type: e2-standard-2 (2 vCPUs, 8GB RAM, Intel Broadwell)

        -   Disk: 30 GB, Ubuntu 22.04 LTS (ubuntu-minimal-2204-lts)

        -   Network: Allow HTTP/S traffic and attach an external IP

        -   Metadata: Add your SSH keys

        -   Labels (optional): goog-ops-agent-policy: v2-x86-template-1-4-0

4.  FILE TRANSFER & SERVER CONFIGURATION

    -   Use PowerShell to upload files to VM (using scp):

        `scp -i <your-ssh-key> -r .\real-estate-ai-qa <username>@<VM_EXTERNAL_IP>:~/ `

    -   SSH into your VM:

        `ssh -i <your-ssh-key> <username>@<VM_EXTERNAL_IP> `

    -   On your GCP VM, install required packages:

        `sudo apt update sudo apt install docker.io docker-compose git -y sudo usermod -aG docker $USER `

        *Log out and log back in for docker group changes to take effect.*

    -   Place your `.env` file in the project root on the VM.

    -   To obtain a Google Gemini API Key:

        -   Go to <https://aistudio.google.com/>

        -   Click API Keys > "Create API Key" and copy it.

        -   Add it to your `.env` as `GOOGLE_API_KEY=<your-key>`

5.  DEPLOYMENT

    -   From the project root on your GCP VM, run:

        `docker compose down docker build -f api/Dockerfile_TF_IDF api docker compose up -d `

    -   Access the app at `http://<YOUR_GCP_VM_PUBLIC_IP>:8000`

KEY SKILLS & CONCEPTS DEMONSTRATED
----------------------------------

-   Data pipeline orchestration (Airflow)

-   Semantic vector search (TF-IDF)

-   LLM integration (Google Gemini API calls)

-   API development (FastAPI)

-   Containerization (Docker Compose)

-   Cloud service setup (GCP VM)

-   Frontend development (React SPA)

-   Secret variable management

OTHER APPLICATIONS
------------------

-   Adapts to other large tabular record search use cases (sport, healthcare, etc.)

-   Easily portable to other cities, data sources, or LLMs.

-   Scalable for AWS/Azure, multi-cloud, or more workflow DAGs

NOTE:
-----

You must supply your own Gemini, Airflow, and DB credentials. All secrets should be managed in your personal `.env` file.
