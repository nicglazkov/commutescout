FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Every module, not a list of them. The list was wrong once already:
# clientip.py was added and not listed, every test passed because tests run
# against the repository rather than the image, and the container died on
# import at deploy time. A glob cannot forget.
COPY *.py ./
COPY waze ./waze

# Nothing in the image needs write access.
RUN useradd --create-home --uid 1001 app
USER app

ENV PORT=8080
EXPOSE 8080

CMD ["python", "server.py"]
