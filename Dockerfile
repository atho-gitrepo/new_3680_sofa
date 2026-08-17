# ----------------------------------------------------
# 1. BASE IMAGE - Using Debian 12 (bookworm)
# ----------------------------------------------------
FROM python:3.11-slim-bookworm 

# ----------------------------------------------------
# 2. WORKDIR
# ----------------------------------------------------
WORKDIR /app

# ----------------------------------------------------
# 3. SYSTEM DEPENDENCIES
# ----------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        curl \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------------------------------
# 4. INSTALL PYTHON DEPENDENCIES
# ----------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------
# 5. INSTALL PLAYWRIGHT BROWSERS
# ----------------------------------------------------
RUN playwright install-deps && \
    playwright install chromium

# ----------------------------------------------------
# 6. COPY APP
# ----------------------------------------------------
COPY . /app/

# ----------------------------------------------------
# 7. START COMMAND
# ----------------------------------------------------
ENV PYTHONUNBUFFERED=1

CMD ["python", "worker/main.py"]