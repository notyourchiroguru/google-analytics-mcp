FROM python:3.12-slim

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir .
RUN chmod +x /app/entrypoint.sh

ENV PYTHONUNBUFFERED=1
CMD ["/app/entrypoint.sh"]
