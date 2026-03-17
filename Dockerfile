FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy the dependency files
# We copy pyproject.toml and uv.lock (if it exists) to cache the dependencies installation
COPY pyproject.toml /app/
COPY uv.lock* /app/

# Install the dependencies into the system environment
RUN uv pip install --system -r pyproject.toml

# Copy the rest of the application
COPY app /app/app
COPY data /app/data

# Change to the app directory where main.py lives
WORKDIR /app/app

# Expose the Cloud Run port
EXPOSE 8080

# Run the FastAPI application using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
