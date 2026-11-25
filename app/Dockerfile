# Part 2, Phase 1: sample application image.
# The base image is pinned by digest. Keep it identical to PYTHON_IMAGE in versions.env.
FROM python:3.13.18-slim@sha256:7249d5587b78209a006dc4a3b5340678f84ea729239193aa559962cd8c1fce50

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# A fixed, numeric, non-root user. Kubernetes can only verify "runAsNonRoot" for a numeric ID.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .

USER 10001:10001
EXPOSE 5050

# One worker, four threads. Login sessions live in this process's memory, so two worker
# processes would each hold different sessions and randomly sign people out.
#   --worker-tmp-dir /dev/shm : worker heartbeat files go to memory, so the container's
#                               filesystem can later be made read-only
#   --no-control-socket       : no admin socket (it would try to write under a home directory)
#   --access-logfile -        : request log to stdout, where "docker logs" and kubectl read it
CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "1", "--threads", "4", \
     "--worker-tmp-dir", "/dev/shm", "--no-control-socket", "--access-logfile", "-", "app:app"]
