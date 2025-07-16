FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN apt-get update && apt-get install -y git && \
    pip install --upgrade pip && \
    pip install --no-cache-dir .

# Document the port your app listens on
EXPOSE 8001

# Start the Qualibrate server
CMD ["qualibrate", "start"]
