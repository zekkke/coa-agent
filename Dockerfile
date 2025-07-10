FROM python:3.11.8-slim-bullseye

# Update and install dependencies
RUN apt-get update && apt-get upgrade -y && apt-get dist-upgrade -y && apt-get install -y curl

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install requests pytest faker tenacity firebase_admin

# Set working directory
WORKDIR /app

# Copy application files
COPY agent.py /app/agent.py
COPY tests/ /app/tests/
COPY call-of-adventure-firebase-adminsdk-fbsvc-a918936ac1.json /app/

# Run the agent
CMD ["python", "agent.py"]