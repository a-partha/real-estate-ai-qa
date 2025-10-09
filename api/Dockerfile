FROM python:3.11-slim

# Create and set the working directory
WORKDIR /app

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY main.py /app/main.py

# Expose the port the app runs on
EXPOSE 8000

# Start the FastAPI application with uvicorn.  We avoid
# ``--reload`` in production; if you need live reload for local
# development you can run ``uvicorn main:app --reload`` from the host.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]