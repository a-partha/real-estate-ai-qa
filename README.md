# NYC ACRIS Property Deeds Q&A with Integrated LLM
Live site: [http://34.48.240.113:8000/
](http://34.86.83.238:8000/)

Overview
----------------

The goal is to build a public-facing, interactive Q&A web application. Users can ask natural language questions about the NYC ACRIS property dataset, and the system provides answers using a combination of direct database queries and a semantic search pipeline powered by a Large Language Model (LLM).

The project starts with a foundational dataset of 500,000 legal property record filings, retrieved as a CSV file from NYC's public API. This data is then ingested into an Apache Airflow pipeline for processing.

The architecture is designed to be robust, using an asynchronous task orchestrator (Airflow) to handle the heavy data processing, ensuring the user-facing API remains responsive.

### Core Pipeline Workflow

The Airflow pipeline consists of three main tasks that are triggered when a user submits a question:

1.  **dbt Model:** A dbt (data build tool) task runs to transform the raw CSV data into a clean, structured SQL table within a DuckDB database.

2.  **Vector Search Indexing:** This task fetches the clean data from DuckDB and converts it into a Pandas dataframe. It then creates a TF-IDF vector index (to weigh word importance) and a Nearest Neighbors model for efficient semantic search. These models are saved as artifacts.

3.  **API & AI Query**: The final task starts with the user's API request and their prompt. A *router step* first decides how to answer:

    -   **SQL Count** to run a direct database query for dataset size or total record questions.

    -   **SQL Distinct** to run a direct database query for "how many categories" type of questions.

    -   **Semantic Search** for all other questions, where the task retrieves the most relevant text snippets using the vector index, then passes them on to Gemini, which generates a natural-language answer.

Tech Stack
----------------

-   **Frontend:** Vite-based React.js

-   **Backend API:** FastAPI (Python)

-   **Orchestrator:** Apache Airflow

-   **Data Transformation:** dbt

-   **Application Datastore:** DuckDB

-   **Airflow Backend:**

    -   **Metadata Database:** Postgres 15

    -   **Executor:** CeleryExecutor

    -   **Message Broker:** Redis 7

-   **AI / Machine Learning:**

    -   **LLM:** Google Gemini (`gemini-1.5-flash`)

    -   **Semantic Search:** Scikit-learn (`TfidfVectorizer`, `NearestNeighbors`)

-   **Deployment:**

    -   **Containerization:** Docker & Docker Compose

    -   **Cloud Provider:** Google Cloud Platform (GCP)

    -   **Compute:** Compute Engine VM (`e2-standard-2`)

Key Components
-----------------------

This section details the role of each critical file in the project.

-   **`docker-compose.yaml` :** This file is the orchestrator for the entire application. It defines every service (Postgres, Redis, Airflow webserver/scheduler/worker, and the FastAPI `api`), how they connect via a shared network, and what environment variables they use. It also maps local directories (like `dags`, `data`, `artifacts`) into the containers so they can access the necessary files.

-   **`legal_property_pipeline.py` (DAG):** This is the heart of the data processing logic. It defines the three-task pipeline within Airflow. A critical feature of this file is that all heavy library imports and model loading (`joblib.load`) are performed *inside* the task functions, not at the top level. This ensures the DAG file is lightweight, allowing Airflow's webserver and scheduler to parse it quickly without timing out.

-   **`main.py` (The FastAPI Backend):** This script serves as the public-facing entry point with two main responsibilities:

    1.  Serving the static frontend files from `index.html` in the root and the `web/dist` directory.

    2.  Providing the `/ask` API endpoint that the frontend calls. This endpoint receives the user's prompt, triggers a new run of the Airflow DAG, polls for its completion status, and then retrieves the final answer from Airflow's XComs to send back to the user.

-   **`App.jsx` :** This is the user interface. It contains the React component that renders the input box and the chat display. Its primary logic involves managing the application state (e.g., user input, loading status, final answer). When a user submits a question, it makes an asynchronous API call (e.g., using `fetch`) to the `/ask` endpoint on the FastAPI backend and displays the response once it's received.

Instructions
-------------------------

This guide covers the full process from local project preparation to a live public deployment on GCP.

### **1\. Local Project Preparation**

This ensures all code, dependencies, and configuration are ready before deployment.

1.  **Build the Frontend:** The frontend application is in a separate folder. It must be built first, and the output (`dist` directory) must be copied into the main backend project.

    -   From your local PowerShell terminal, navigate to the frontend project directory:

        ```
        cd path/to/your/property-qa-frontend
        npm run build

        ```

    -   Next, copy the generated `dist` folder into the backend project's `web` directory, replacing the old one:

        ```
        Remove-Item -Recurse -Force path/to/your/main-project/web/dist
        Copy-Item -Recurse -Path ./dist -Destination path/to/your/main-project/web/

        ```

2.  **Prepare the Main Project:** The main project folder should now contain the backend code and the newly built frontend. All subsequent commands are run from this main project folder.

> **Note:** Always run the build and perform a hard refresh (`Ctrl + Shift + R`) in your browser to see the latest changes.

### **2\. GCP Server Setup**

1.  **Create a VM Instance:** In the GCP Console, create a Compute Engine (like `e2-standard-2`) instance using a Debian 11 or Ubuntu OS image.

2.  **Configure Firewall Rules:** During creation, in the "Firewall" section, check "Allow HTTP traffic" and "Allow HTTPS traffic." After creation, navigate to "VPC network" -> "Firewall" and add a rule to open TCP ports **`8000`** (for the public Q&A site) and **`8080`** (for the Airflow UI).

### **3\. Server Configuration & File Transfer**

1.  **Install Docker:** SSH into your new VM and run the following commands to install Docker Engine and Docker Compose.

    ```
    # Update packages and install dependencies
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg

    # Add Docker's GPG key and repository
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Install Docker Engine and Compose
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    ```

    Your frontend code needs to be aware of the public server address so that the React application knows which URL to use for API calls depending on whether it's in development or production.
    
    ```
    # In your frontend folder (on your local machine), create two new files named .env.development and .env.production
    Then, define Your API URLs:
    - Inside .env.development, add this for local testing: VITE_API_BASE_URL=http://localhost:8000
    - Inside .env.production, add: VITE_API_BASE_URL=http://[your server's public IP address]:8000    
    ```

2.  **Transfer Project Files:** From your local PowerShell terminal, copy your entire prepared main project folder to the VM.

    ```
    gcloud compute scp --recurse [YOUR_MAIN_PROJECT_FOLDER_NAME] [YOUR_VM_NAME]:~/

    ```

### **4\. Deployment**

1.  **Configure Environment Variables:** SSH into your VM. The project requires a `.env` file with API keys and credentials. Create it using a terminal editor like `nano`.

    ```
    cd [YOUR_MAIN_PROJECT_FOLDER_NAME]
    nano .env
    ```

    -   Paste the following content into the editor, adding your Google API key.

        ```
        GOOGLE_API_KEY=your_actual_google_api_key_here
        AIRFLOW_USER=your_actual_username
        AIRFLOW_PW=your_actual_password
        AIRFLOW_API_BASE_URL=http://airflow-webserver:8080/api/v1
        ```

    -   Save the file by pressing `Ctrl+O`, `Enter`, and `Ctrl+X`.

> **Note:** The `AIRFLOW_API_BASE_URL` is critical. For container-to-container communication within a Docker network, you **have to use the service name** defined in the `docker-compose.yaml` file (in this case, `airflow-webserver`).

1.  **Launch the Application:** With the `.env` file in place, launch the entire application stack.

    ```
    docker compose up -d --build
    ```

    -   The `--build` flag ensures Docker creates a fresh image with your latest frontend files. The `-d` flag runs it in the background.

2.  **Access Your Application:**

    -   **Public Q&A Site:**  `http://[YOUR-VM-EXTERNAL-IP]:8000`

    -   **Airflow UI:**  `http://[YOUR-VM-EXTERNAL-IP]:8080` (Login with your Airflow credentials)

Key Skills & Concepts Demonstrated
----------------------------------

-   **Full-Stack Development:** Integrating a React frontend with a Python FastAPI backend.

-   **Data Engineering:** Using dbt for data transformation and Airflow for orchestrating a data pipeline.

-   **MLOps (Machine Learning Operations):** Building, versioning (via artifacts), and deploying an ML model for semantic search within a larger application.

-   **Cloud Infrastructure Management:** Provisioning, configuring, and deploying to a cloud VM on GCP, including firewall management.

-   **Containerization & Microservices:** Using Docker and Docker Compose to define, build, and run a multi-service application, ensuring consistency from local development to production.

-   **API Design & Interaction:** Building a REST API that triggers and polls an asynchronous backend job.

Other Applications
------------------------

This project also serves as a template for a wide range of interactive data applications, including:

-   **"Chat with your data" applications:** Any project where a user needs to query a structured or unstructured dataset (e.g., PDFs, CSVs, databases) using natural language.

-   **Interactive data science dashboards:** Dashboards that allow users to trigger complex simulations or model runs in the background and see the results when they are ready.

-   **On-demand report generation:** A user could request a complex report via a web UI, which triggers a long-running Airflow DAG to generate and deliver the result.
