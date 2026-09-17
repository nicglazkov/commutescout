FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py store.py mapping.py ./
COPY waze ./waze

# Nothing in the image needs write access.
RUN useradd --create-home --uid 1001 app
USER app

ENV PORT=8080
EXPOSE 8080

CMD ["python", "server.py"]
