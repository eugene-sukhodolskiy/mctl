# Stage 1: build CSS from SCSS
FROM node:20-alpine AS frontend
WORKDIR /build
COPY package*.json gulpfile.js ./
RUN npm ci
COPY scss/ scss/
RUN npx gulp sass-build


# Stage 2: runtime
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg vainfo libva-drm2 pciutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /build/static/css/ static/css/

# Bind to all interfaces inside the container
ENV MCTL_HOST=0.0.0.0

EXPOSE 5000

CMD ["python", "app.py"]
