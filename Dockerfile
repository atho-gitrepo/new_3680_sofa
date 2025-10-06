# ----------------------------------------------------
# 1. BASE IMAGE: Use a stable, official Python image
# We use python:3.11-slim-buster for a smaller image size
# You can adjust the Python version (e.g., 3.12) as needed
# ----------------------------------------------------
FROM python:3.11-slim-buster

# ----------------------------------------------------
# 2. ENVIRONMENT SETUP
# Set the working directory inside the container. 
# All subsequent commands (COPY, RUN, CMD) will be run from here.
# Railway often defaults to /app, so we match that.
# ----------------------------------------------------
WORKDIR /app

# ----------------------------------------------------
# 3. INSTALL DEPENDENCIES
# Copy only the requirements file first to take advantage of Docker's layer caching.
# If requirements.txt doesn't change, this step won't re-run.
# ----------------------------------------------------
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------
# 4. COPY APPLICATION CODE
# Copy the rest of the contents of your repository into the working directory (/app).
# This includes your 'worker/' folder and the 'esd/' folder.
# ----------------------------------------------------
COPY . /app/

# ----------------------------------------------------
# 5. DEFINE THE START COMMAND (ENTRYPOINT/CMD)
# This is the command that runs when the container starts.
# We explicitly call the script using the correct path: 'worker/main.py'
# The -u flag ensures logs are output immediately (unbuffered), which is 
# essential for platforms like Railway.
# ----------------------------------------------------
CMD ["python", "-u", "worker/main.py"]
