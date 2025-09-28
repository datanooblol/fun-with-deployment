# Below just my plan, you can make it better
FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml .
COPY main.py .

RUN uv sync

CMD [ "uv", "run", "main.py"]