# ----------------------------------------------------
# 1. BASE IMAGE: **FIXED** to use the active 'bullseye' release
# ----------------------------------------------------
FROM python:3.11-slim-bullseye 

# ----------------------------------------------------
# 2. ENVIRONMENT SETUP
# ----------------------------------------------------
WORKDIR /app

# ----------------------------------------------------
# 3. FIX: INSTALL SYSTEM DEPENDENCIES FOR PLAYWRIGHT
# This is the step that failed, but it will now succeed with the new base image.
# ----------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libnspr4 \
        libnss3 \
        libdbus-1-3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libatspi2.0-0 \
        libx11-6 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libxcb1 \
        libxkbcommon0 \
        libasound2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ----------------------------------------------------
# 4. INSTALL PYTHON DEPENDENCIES
# ----------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------
# 5. COPY APPLICATION CODE
# ----------------------------------------------------
COPY . /app/

# ----------------------------------------------------
# 6. DEFINE THE START COMMAND (CMD)
# ----------------------------------------------------
CMD ["python", "-u", "worker/main.py"]
