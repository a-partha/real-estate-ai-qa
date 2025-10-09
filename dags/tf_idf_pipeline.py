# tf_idf_property_pipeline.py
import os
import re
import json
import duckdb
import pandas as pd
from datetime import datetime
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
import google.generativeai as genai
from docx import Document

from airflow.decorators import dag, task


@dag(
    dag_id="tf_idf_property_pipeline",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["vector_search"]
)
def legal_property_pipeline():
    """
    Build dbt models, create a sampled vector index for semantic QA,
    and answer queries with an LLM router:
      - sql_count_full: dataset size questions
      - sql_agg_full_distinct: distinct counts like boroughs
      - semantic: vector context + Gemini
    """

    @task
    def build_dbt_models() -> None:
        dbt_path = "/opt/airflow/dbt"
        os.system(f"cd {dbt_path} && dbt run --profiles-dir {dbt_path}")

    @task
    def build_vector_index() -> None:
        db_path = "/opt/airflow/data/legal_demo.duckdb"
        conn = duckdb.connect(db_path)
        df = conn.execute("SELECT * FROM acris_clean").fetch_df()

        # sample for speed
        df = df.sample(n=1000, random_state=42).reset_index(drop=True)

        # Load metadata from Excel and Word files
        try:
            # Load specific sheets from Excel
            data_dict_path = "/opt/airflow/data/ACRIS_-_Real_Property_Legals_Data_Dictionary.xlsx"
            excel_sheets = pd.read_excel(data_dict_path, sheet_name=['Dataset Info', 'Column Info'])
            print(f"Loaded Excel sheets: {list(excel_sheets.keys())}")
            
            dataset_info = excel_sheets['Dataset Info']
            column_info = excel_sheets['Column Info']
            print(f"Dataset Info sheet: {dataset_info.shape}")
            print(f"Column Info sheet: {column_info.shape}")
        except Exception as e:
            print(f"Could not load data dictionary: {e}")
            dataset_info = pd.DataFrame()
            column_info = pd.DataFrame()

        try:
            # Load documentation from both Word files
            doc_paths = [
                "/opt/airflow/data/ACRIS_Public_OpenData_Guide.docx",
                "/opt/airflow/data/NYC_OpenData_ACRIS_Datasets.docx"
            ]
            doc_texts = []
            for doc_path in doc_paths:
                try:
                    doc = Document(doc_path)
                    raw_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
                    
                    # Clean problematic Unicode characters
                    cleaned_text = raw_text
                    cleaned_text = cleaned_text.replace('\xa0', ' ')  # Non-breaking space
                    cleaned_text = cleaned_text.replace('\u201c', '"')  # Left double quotation mark
                    cleaned_text = cleaned_text.replace('\u201d', '"')  # Right double quotation mark
                    cleaned_text = cleaned_text.replace('\u2018', "'")  # Left single quotation mark
                    cleaned_text = cleaned_text.replace('\u2019', "'")  # Right single quotation mark
                    
                    doc_texts.append(cleaned_text)
                    print(f"Loaded {doc_path.split('/')[-1]} with {len(cleaned_text)} characters (cleaned from {len(raw_text)})")
                except Exception as e:
                    print(f"Could not load {doc_path}: {e}")
            doc_text = "\n\n".join(doc_texts) if doc_texts else ""
            print(f"Combined documentation has {len(doc_text)} total characters")
        except Exception as e:
            print(f"Could not load documentation: {e}")
            doc_text = ""

        borough_map = {
            "1": "Manhattan", "2": "Bronx", "3": "Brooklyn",
            "4": "Queens", "5": "Staten Island"
        }

        # Create lookup dictionaries from actual Excel data
        record_type_descriptions = {}
        property_type_descriptions = {}
        dataset_context = ""
        
        # Parse Dataset Info sheet for general context
        if not dataset_info.empty:
            for _, row in dataset_info.iterrows():
                if pd.notna(row.iloc[0]) and pd.notna(row.iloc[1]):
                    field_name = str(row.iloc[0]).strip()
                    field_value = str(row.iloc[1]).strip()
                    
                    if field_name.lower() == 'dataset description':
                        dataset_context = field_value
                    elif field_name.lower() == 'detailed description':
                        if field_value and field_value != 'nan':
                            dataset_context += f" {field_value}"
        
        # Parse Column Info sheet for field descriptions
        if not column_info.empty:
            for i, row in column_info.iterrows():
                if pd.notna(row.iloc[0]):
                    field_name = str(row.iloc[0]).strip()
                    field_desc = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
                    
                    # Extract Record Type description
                    if field_name.lower() == 'record type' and field_desc:
                        # Parse description like "'L' for lot record" (handle Unicode quotes)
                        if "for" in field_desc:
                            parts = field_desc.split("for")
                            if len(parts) == 2:
                                code_part = parts[0].strip()
                                desc_part = parts[1].strip()
                                # Extract the letter from the code part
                                for char in code_part:
                                    if char.isalpha():
                                        code = char
                                        record_type_descriptions[code] = desc_part
                                        break
                    
                    # Extract Property Type description
                    elif field_name.lower() == 'property type' and field_desc:
                        # Property type description is in the description field
                        property_type_descriptions['info'] = field_desc
                    
                    # Extract Borough descriptions
                    elif field_name.lower() == 'borough' and pd.notna(row.iloc[3]):
                        borough_notes = str(row.iloc[3])
                        if "=" in borough_notes:
                            # Parse "1 = Manhattan\n2 = Bronx\n3 = Brooklyn\n4 = Queens"
                            lines = borough_notes.split('\n')
                            for line in lines:
                                if '=' in line:
                                    parts = line.split('=')
                                    if len(parts) == 2:
                                        code = parts[0].strip()
                                        desc = parts[1].strip()
                                        if code.isdigit():
                                            borough_map[code] = desc
        
        print(f"Dataset context: {dataset_context[:100]}...")
        print(f"Found {len(record_type_descriptions)} record type descriptions: {record_type_descriptions}")
        print(f"Found {len(property_type_descriptions)} property type descriptions: {property_type_descriptions}")

        def row_to_text(row):
            # Enhanced text with descriptions from actual Excel data
            record_type = row['record_type']
            record_desc = record_type_descriptions.get(record_type, "")
            record_text = f"Record type {record_type}" + (f" ({record_desc})" if record_desc else "")
            
            property_type = row.get('property_type', '')
            prop_desc = property_type_descriptions.get(property_type, "")
            prop_text = f"Property type {property_type}" + (f" ({prop_desc})" if prop_desc else "")
            
            parts = [
                f"Document ID {row['document_id']}",
                record_text,
                f"Borough {borough_map.get(str(row['borough']), row['borough'])}",
                f"Block {row['block']}",
                f"Lot {row['lot']}",
                prop_text,
                f"Street number {row.get('street_number', '')}",
                f"Street name {row.get('street_name', '')}",
                f"Unit {row.get('unit', '')}",
                f"Good through date {row.get('good_through_date', '')}",
            ]
            
            # Add additional context from Excel dataset info and Word documentation
            if dataset_context:
                parts.append(f"Dataset: {dataset_context[:100]}...")
            elif doc_text and len(doc_text) > 100:
                parts.append(f"Context: ACRIS property records system")
            
            return ", ".join(p for p in parts if str(p).strip())

        df["text"] = df.apply(row_to_text, axis=1)

        vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        X = vectorizer.fit_transform(df["text"])

        nn_model = NearestNeighbors(n_neighbors=50, metric="cosine")
        nn_model.fit(X)

        os.makedirs("/opt/airflow/artifacts", exist_ok=True)
        joblib.dump(vectorizer, "/opt/airflow/artifacts/vectorizer.pkl")
        joblib.dump(nn_model, "/opt/airflow/artifacts/nn_model.pkl")
        joblib.dump(df, "/opt/airflow/artifacts/acris_df.pkl")

    @task
    def ask_gemini_with_vector_context(**context) -> str:
        # Read run config
        dag_run_conf = context.get("dag_run").conf if context.get("dag_run") else {}
        prompt = (dag_run_conf.get("prompt") or "").strip()

        # Safe parse with default 50
        def parse_top_k(v, default=50):
            try:
                k = int(v)
                return k if k > 0 else default
            except (TypeError, ValueError):
                return default

        top_k = parse_top_k(dag_run_conf.get("top_k"))

        # LLM router
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is missing")
        genai.configure(api_key=api_key)

        router_system = (
            "You are a routing assistant. Choose exactly one tool:\n"
            " - sql_count_full: dataset-wide total rows\n"
            " - sql_agg_full_distinct: count distinct values for a single column\n"
            " - semantic: use vector context + LLM\n"
            "Return strict JSON: {\"tool\": \"...\", \"arguments\": {...}, \"confidence\": 0..1, \"reason\": \"...\"}\n"
            "If the user asks about totals, counts, number of entries or dataset size, prefer sql_count_full.\n"
            "If the user asks 'how many boroughs' or distinct categories, prefer sql_agg_full_distinct with a column.\n"
            "Otherwise choose semantic."
        )

        few_shots = [
            {
                "q": "How many entries are in the dataset?",
                "a": {"tool": "sql_count_full", "arguments": {}, "confidence": 0.95, "reason": "dataset size"},
            },
            {
                "q": "How many boroughs are there?",
                "a": {"tool": "sql_agg_full_distinct", "arguments": {"column": "borough"}, "confidence": 0.9, "reason": "distinct boroughs"},
            },
            {
                "q": "Summarize common record types you see.",
                "a": {"tool": "semantic", "arguments": {}, "confidence": 0.8, "reason": "textual synthesis"},
            },
            {
                "q": "What is the total number of records?",
                "a": {"tool": "sql_count_full", "arguments": {}, "confidence": 0.95, "reason": "total records"},
            },
        ]

        routing_prompt = (
            router_system
            + "\n\nExamples:\n"
            + "\n".join([f"User: {ex['q']}\nReturn: {json.dumps(ex['a'])}" for ex in few_shots])
            + f"\n\nUser: {prompt}\nReturn:"
        )

        try:
            router_model = genai.GenerativeModel("gemini-2.5-flash-lite")
            r = router_model.generate_content(routing_prompt)
            raw = getattr(r, "text", str(r)) or ""
            # strip code fences if any
            cleaned = raw.strip().strip("`")
            # find first JSON object
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            router_out = {}
            if start != -1 and end != -1 and end > start:
                router_out = json.loads(cleaned[start : end + 1])
        except Exception:
            router_out = {}

        tool = (router_out.get("tool") or "").strip()
        arguments = router_out.get("arguments") or {}
        confidence = router_out.get("confidence")
        reason = router_out.get("reason")

        # Optional lightweight rule safety net if router is unsure
        lower = prompt.lower()
        if not tool:
            if re.search(r"\b(total number|dataset size|how many (entries|rows|records|documents))\b", lower):
                tool = "sql_count_full"
            elif re.search(r"\bhow many boroughs?\b", lower):
                tool = "sql_agg_full_distinct"
                arguments = {"column": "borough"}
            else:
                tool = "semantic"

        # Execute the routed tool
        ti = context["ti"]

        if tool == "sql_count_full":
            conn = duckdb.connect("/opt/airflow/data/legal_demo.duckdb")
            total = conn.execute("SELECT COUNT(*) FROM acris_clean").fetchone()[0]
            answer = f"The dataset has {total:,} entries."
            ctx = "Answered from full table: SELECT COUNT(*) FROM acris_clean"
            ti.xcom_push(key="answer", value=answer)
            ti.xcom_push(key="context", value=ctx)
            ti.xcom_push(key="route", value=tool)
            if confidence is not None:
                ti.xcom_push(key="confidence", value=str(confidence))
            return answer

        if tool == "sql_agg_full_distinct":
            # allowlist of distinct-countable columns
            safe_columns = {"borough", "record_type"}
            col = (arguments.get("column") or "").strip().lower()
            # simple synonyms
            if col in {"boroughs", "boro", "boros"}:
                col = "borough"
            if col not in safe_columns:
                # fallback if router gave unknown column
                col = "borough"
            conn = duckdb.connect("/opt/airflow/data/legal_demo.duckdb")
            n_distinct = conn.execute(f"SELECT COUNT(DISTINCT {col}) FROM acris_clean").fetchone()[0]
            answer = f"There are {n_distinct} distinct {col}(s) in the dataset."
            ctx = f"Answered from full table: SELECT COUNT(DISTINCT {col}) FROM acris_clean"
            ti.xcom_push(key="answer", value=answer)
            ti.xcom_push(key="context", value=ctx)
            ti.xcom_push(key="route", value=tool)
            if confidence is not None:
                ti.xcom_push(key="confidence", value=str(confidence))
            return answer

        # semantic default
        vectorizer = joblib.load("/opt/airflow/artifacts/vectorizer.pkl")
        nn_model = joblib.load("/opt/airflow/artifacts/nn_model.pkl")
        df = joblib.load("/opt/airflow/artifacts/acris_df.pkl")

        query_vec = vectorizer.transform([prompt])
        n_neighbors = max(1, min(top_k, len(df)))
        _, idxs = nn_model.kneighbors(query_vec, n_neighbors=n_neighbors)
        idxs = idxs.flatten()
        context_docs = "\n".join(df.iloc[idxs]["text"].tolist())

        # generate final answer
        qa_model = genai.GenerativeModel("gemini-2.5-flash-lite")
        message = (
            "You are given the following context from a property deeds dataset:\n\n"
            f"{context_docs}\n\n"
            f"Question: {prompt}\n\nAnswer:"
        )
        try:
            response = qa_model.generate_content(message)
            answer = getattr(response, "text", str(response))
        except Exception as exc:
            answer = f"Error generating answer: {exc}"

        ti.xcom_push(key="answer", value=answer)
        ti.xcom_push(key="context", value=context_docs)
        ti.xcom_push(key="route", value="semantic")
        if confidence is not None:
            ti.xcom_push(key="confidence", value=str(confidence))
        return answer

    build_dbt_models() >> build_vector_index() >> ask_gemini_with_vector_context()


legal_property_pipeline()
