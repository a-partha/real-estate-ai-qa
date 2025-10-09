#pinecone_pipeline.py
import os
import json
import re
import duckdb
import pandas as pd
from datetime import datetime

# Imports for Pinecone managed embedding (serverless)
import pinecone
import google.generativeai as genai

from airflow.decorators import dag, task
from airflow.models.param import Param
from pinecone import ServerlessSpec

# --- Environment Variable Checks ---
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME", "acris-legal")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

@dag(
    dag_id="legal_property_pipeline",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["vector_search", "pinecone"],
    params={
        "prompt": Param(type="string", default="What are the most common property types in Manhattan?"),
        "top_k": Param(type="integer", default=50)
    }
)
def legal_property_pipeline():
    """
    Pinecone-based Legal Property QA Pipeline leveraging managed embeddings.
    """

    @task
    def build_dbt_models() -> None:
        """Runs dbt models to prepare the source data."""
        dbt_path = "/opt/airflow/dbt"
        os.system(f"cd {dbt_path} && dbt run --profiles-dir .")

    @task
    def build_pinecone_index() -> None:
        """
        Samples data, deletes old vectors, and upserts new data into Pinecone.
        Uses Pinecone's hosted embedding model (managed embedding).
        """
        if not PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY environment variable is not set.")

        print("Initializing Pinecone client...")
        pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(PINECONE_INDEX_NAME)
        namespace = "default"  # Customize if you use multiple namespaces in Pinecone

        print("Connecting to DuckDB to fetch data...")
        db_path = "/opt/airflow/data/legal_demo.duckdb"
        conn = duckdb.connect(db_path, read_only=True)
        df = conn.execute("SELECT * FROM acris_clean").fetch_df()
        
        # Get dataset statistics for metadata
        total_records = len(df)
        unique_boroughs = df['borough'].nunique()
        unique_property_types = df['property_type'].nunique() if 'property_type' in df.columns else 0
        unique_record_types = df['record_type'].nunique() if 'record_type' in df.columns else 0
        
        # Note: Need to read from the actual ACRIS__Property_Types_Codes.csv file later for better context
        try:
            # For now, including common ACRIS property types
            property_type_examples = [
                "A1 (ONE FAMILY HOMES)", "A4 (CONDOS)", "A5 (COOPERATIVES)", 
                "B1 (TWO FAMILY HOMES)", "C1 (WALK-UP APARTMENTS)", 
                "D1 (ELEVATOR APARTMENTS)", "K1 (STORE BUILDINGS)",
                "O1 (OFFICE BUILDINGS)", "R1 (CONDOMINIUMS)"
            ]
            # TODO: 
            # property_types_df = pd.read_csv('/path/to/ACRIS__Property_Types_Codes.csv')
            # property_type_examples = [f"{row['PROPERTY TYPE']} ({row['DESCRIPTION']})" 
            #                          for _, row in property_types_df.head(10).iterrows()]
        except Exception as e:
            print(f"Could not read property types CSV: {e}")
            property_type_examples = ["Various residential and commercial property types"]
        
        conn.close()

        print(f"Sampling 1000 rows from the dataset (total rows: {len(df)}).")
        df_sample = df.sample(n=1000, random_state=42).reset_index(drop=True)

        borough_map = {
            "1": "Manhattan", "2": "Bronx", "3": "Brooklyn",
            "4": "Queens", "5": "Staten Island"
        }
        
        def row_to_text(row):
            parts = [
                f"Document ID {row['document_id']}",
                f"Record type {row['record_type']}",
                f"Borough {borough_map.get(str(row['borough']), 'Unknown')}",
                f"Block {row['block']}",
                f"Lot {row['lot']}",
                f"Property type {row.get('property_type', 'N/A')}",
                f"Street address: {row.get('street_number', '')} {row.get('street_name', '')}",
                f"Unit {row.get('unit', 'N/A')}",
                f"Effective through {row.get('good_through_date', 'N/A')}",
            ]
            return ". ".join(p for p in parts if str(p).strip())

        df_sample["text"] = df_sample.apply(row_to_text, axis=1)

        print("Deleting all previous vectors from the index...")
        try:
            index.delete(delete_all=True, namespace=namespace)
        except Exception as e:
            print(f"Delete failed: {e}")

        print("Preparing and upserting new documents into Pinecone...")
        records_to_upsert = []
        
        # Dataset metadata records
        metadata_records = [
            {
                "id": "dataset_overview_1",
                "text": f"Automated City Register Information System (ACRIS) is the New York City Department of Finance's Automated City Register Information System, to search property records and view document images for Manhattan, Queens, Bronx, and Brooklyn from 1966 to the present.",
                "metadata": {
                    "text": f"Automated City Register Information System (ACRIS) is the New York City Department of Finance's Automated City Register Information System, to search property records and view document images for Manhattan, Queens, Bronx, and Brooklyn from 1966 to the present.",
                    "record_type": "metadata"
                }
            },
            {
                "id": "dataset_overview_2", 
                "text": f"ACRIS has two types of documents: Real Property Records (including Deeds and Other Conveyances, Mortgages & Instruments, and Other Documents) and Personal Property Records (UCC and Federal Liens). This dataset focuses on Real Property Records which impact rights to real property and follow the property rather than individuals. Each record contains a master record linked by Document ID to lot records, party records, cross-reference records, and remarks records.",
                "metadata": {
                    "text": f"ACRIS has two types of documents: Real Property Records (including Deeds and Other Conveyances, Mortgages & Instruments, and Other Documents) and Personal Property Records (UCC and Federal Liens). This dataset focuses on Real Property Records which impact rights to real property and follow the property rather than individuals. Each record contains a master record linked by Document ID to lot records, party records, cross-reference records, and remarks records.",
                    "record_type": "metadata"
                }
            },
            {
                "id": "dataset_overview_4",
                "text": f"The dataset contains detailed property information including Document IDs, record types (L for lot record), borough codes (1=Manhattan, 2=Bronx, 3=Brooklyn, 4=Queens), block and lot numbers, property types, street addresses with numbers and names, unit information, and good through dates (MM/DD/YYYY format). It covers {unique_boroughs} boroughs with {unique_property_types} different property types and {unique_record_types} different record types.",
                "metadata": {
                    "text": f"The ACRIS dataset contains detailed property information including Document IDs, record types (L for lot record), borough codes (1=Manhattan, 2=Bronx, 3=Brooklyn, 4=Queens), block and lot numbers, property types, street addresses with numbers and names, unit information, and good through dates (MM/DD/YYYY format). It covers {unique_boroughs} boroughs with {unique_property_types} different property types and {unique_record_types} different record types.",
                    "record_type": "metadata"
                }
            },
            {
                "id": "dataset_overview_3",
                "text": "This dataset is about New York City real estate and property ownership records. It contains a subset of {total_records:,} (out of 22 million) legal documents related to property transactions, deeds, mortgages, conveyances, and other real property instruments. The data includes property location details (borough, block, lot), property characteristics, document information, and transaction dates. It's used for property research, legal due diligence, real estate analysis, and property ownership verification.",
                "metadata": {
                    "text": "This dataset is about New York City real estate and property ownership records. It contains a subset of {total_records:,} (out of 22 million) legal documents related to property transactions, deeds, mortgages, conveyances, and other real property instruments. The data includes property location details (borough, block, lot), property characteristics, document information, and transaction dates. It's used for property research, legal due diligence, real estate analysis, and property ownership verification.",
                    "record_type": "metadata"
                }
            },
            {
                "id": "dataset_context_5",
                "text": f"ACRIS legal property records include fields for easements (Y or N), partial lot designations, air rights (Y or N), subterranean rights (Y or N), and property type codes. Property types include {', '.join(property_type_examples[:5])} among others. The good through date (MM/DD/YYYY format) represents the latest recording or correction date. Each property is uniquely identified by its borough-block-lot (BBL) combination where borough codes are: 1=Manhattan, 2=Bronx, 3=Brooklyn, 4=Queens.",
                "metadata": {
                    "text": f"ACRIS legal property records include fields for easements (Y or N), partial lot designations, air rights (Y or N), subterranean rights (Y or N), and property type codes. Property types include {', '.join(property_type_examples[:5])} among others. The good through date (MM/DD/YYYY format) represents the latest recording or correction date. Each property is uniquely identified by its borough-block-lot (BBL) combination where borough codes are: 1=Manhattan, 2=Bronx, 3=Brooklyn, 4=Queens.",
                    "record_type": "metadata"
                }
            },
            {
                "id": "dataset_schema_6",
                "text": "Every ACRIS dataset schema includes: Document ID (unique identifier), Record Type (L for lot record), Borough (1-4 numeric codes), Block (block number), Lot (lot number), Easement (Y/N field), Partial Lot (P=partial, E=entire), Air Rights (Y/N field), Subterranean Rights (Y/N field), Property Type (alphanumeric codes), Street Number, Street Name, Unit, and Good Through Date. This follows the official NYC Department of Finance ACRIS data structure.",
                "metadata": {
                    "text": "Every ACRIS dataset schema includes: Document ID (unique identifier), Record Type (L for lot record), Borough (1-4 numeric codes), Block (block number), Lot (lot number), Easement (Y/N field), Partial Lot (P=partial, E=entire), Air Rights (Y/N field), Subterranean Rights (Y/N field), Property Type (alphanumeric codes), Street Number, Street Name, Unit, and Good Through Date. This follows the official NYC Department of Finance ACRIS data structure.",
                    "record_type": "metadata"
                }
            }
        ]
        
        records_to_upsert.extend(metadata_records)
        
        # Property records
        for i, row in df_sample.iterrows():
            records_to_upsert.append({
                "id": str(row['document_id']),
                "text": row['text'],
                "metadata": {
                    "text": row['text'],
                    "record_type": "property_record"
                }
            })

        print(f"Upserting {len(records_to_upsert)} records (including {len(metadata_records)} metadata records)...")
        try:
            index.upsert_records(
                namespace=namespace,
                records=records_to_upsert
            )
            print("Successfully upserted all records.")
        except Exception as e:
            print(f"Upsert failed: {e}")

        print("Pinecone index build complete.")
        print(f"Index stats: {index.describe_index_stats()}")

    @task
    def ask_gemini_with_pinecone_context(**context) -> str:
        """
        Routes a prompt, queries Pinecone for semantic context, and uses Gemini to generate a final answer.
        """
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY environment variable is not set.")
        if not PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY environment variable is not set.")

        params = context["params"]
        prompt = params.get("prompt", "").strip()
        top_k = int(params.get("top_k", 50))
        if not prompt:
            return "Error: No prompt provided."

        # LLM Router
        genai.configure(api_key=GOOGLE_API_KEY)
        router_system = (
            "You are a routing assistant. Choose exactly one tool:\n"
            " - sql_count_full: For questions about total dataset size or number of entries.\n"
            " - sql_agg_full_distinct: For questions about counting distinct categories (e.g., 'how many boroughs').\n"
            " - semantic_search: For all other questions including dataset overview, content description, and specific property queries.\n"
            "Return strict JSON: {\"tool\": \"...\", \"arguments\": {...}}\n"
        )
        routing_prompt = f"{router_system}\nUser: {prompt}\nReturn:"
        try:
            router_model = genai.GenerativeModel("gemini-2.5-flash-lite")
            r = router_model.generate_content(routing_prompt)
            raw = getattr(r, "text", str(r)) or ""
            start = raw.find("{")
            end = raw.rfind("}")
            router_out = json.loads(raw[start : end + 1]) if start != -1 and end > start else {}
        except Exception as e:
            print(f"Router failed, falling back to semantic search. Error: {e}")
            router_out = {}

        tool = (router_out.get("tool") or "").strip()
        arguments = router_out.get("arguments") or {}

        # Fallback logic
        if not tool:
            lower = prompt.lower()
            if re.search(r"\btotal|how many (entries|rows|records)\b", lower):
                tool = "sql_count_full"
            elif re.search(r"\bhow many.*distinct\b|\bhow many boroughs\b", lower):
                tool = "sql_agg_full_distinct"
                arguments = {"column": "borough"}
            else:
                tool = "semantic_search"

        print(f"Routing decision: '{tool}' with arguments: {arguments}")
        ti = context["ti"]
        ti.xcom_push(key="route", value=tool)

        # Execute Routed Tool
        db_path = "/opt/airflow/data/legal_demo.duckdb"

        if tool == "sql_count_full":
            conn = duckdb.connect(db_path, read_only=True)
            total = conn.execute("SELECT COUNT(*) FROM acris_clean").fetchone()[0]
            conn.close()
            answer = f"The dataset has {total:,} entries."
            ti.xcom_push(key="answer", value=answer)
            ti.xcom_push(key="context", value="Executed: SELECT COUNT(*) FROM acris_clean")
            return answer

        if tool == "sql_agg_full_distinct":
            safe_columns = {"borough", "record_type"}
            col = (arguments.get("column") or "borough").strip().lower()
            if col not in safe_columns: col = "borough"

            conn = duckdb.connect(db_path, read_only=True)
            n_distinct = conn.execute(f"SELECT COUNT(DISTINCT {col}) FROM acris_clean").fetchone()[0]
            conn.close()
            answer = f"There are {n_distinct} distinct {col}(s) in the dataset."
            ti.xcom_push(key="answer", value=answer)
            ti.xcom_push(key="context", value=f"Executed: SELECT COUNT(DISTINCT {col}) FROM acris_clean")
            return answer

        # Default: Semantic Search with Pinecone Managed Embedding 
        print("Executing semantic search with Pinecone...")
        pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(PINECONE_INDEX_NAME)
        namespace = "default"

        print(f"Searching Pinecone index with prompt: '{prompt}'")
        response = index.search(
            namespace=namespace,
            query={
                "inputs": {"text": prompt},
                "top_k": top_k
            }
        )

        # Retrieve context from results
        matches = response.get('matches', [])
        full_context_docs = "\n".join([m.get('metadata', {}).get('text', '') for m in matches])
        texts = [
        m.get("text") or m.get("metadata", {}).get("text", "")
        for m in matches
        ]
        display_context_docs = "\n".join([t for t in texts if t and "metadata" not in t.lower()][:top_k])
        if not display_context_docs:
            display_context_docs = "No supporting context found for this query."

        # Enhanced prompt for better context understanding
        qa_model = genai.GenerativeModel("gemini-2.5-flash-lite")
        message = (
            "You are a helpful assistant for the ACRIS (Automated City Register Information System) "
            "dataset from the NYC Department of Finance. This dataset contains real property records "
            "including deeds, mortgages, conveyances, and other legal property documents from 1966 to present "
            "covering Manhattan, Queens, Bronx, and Brooklyn. Use the following context to answer the question. "
            "The context may include both dataset overview information and specific property records.\n\n"
            "--- Context ---\n"
            f"{full_context_docs}\n\n"
            "--- Question ---\n"
            f"{prompt}\n\n"
            "Answer:"
        )
        try:
            final_response = qa_model.generate_content(message)
            answer = getattr(final_response, "text", str(final_response))
        except Exception as exc:
            answer = f"Error generating final answer from Gemini: {exc}"

        ti.xcom_push(key="answer", value=answer)
        ti.xcom_push(key="context", value=display_context_docs)
        print(f"[DEBUG] Context length being pushed: {len(display_context_docs)}")
        return answer

    # --- Define Task Dependencies ---
    dbt_task = build_dbt_models()
    pinecone_task = build_pinecone_index()
    gemini_task = ask_gemini_with_pinecone_context()

    dbt_task >> pinecone_task >> gemini_task

legal_property_pipeline()