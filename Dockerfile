ARG PYTHON_VERSION=3.13.5
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser


# Installer les dépendances
COPY requirements.txt .
RUN pip install --upgrade pip
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY . .

# Créer et donner la propriété des dossiers nécessaires
RUN mkdir -p /app/recordings /app/temp_segments \
    && touch /app/streams.json \
    && chown -R appuser:appuser /app
USER appuser
# Passer en utilisateur non privilégié

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "120", "app:app"]