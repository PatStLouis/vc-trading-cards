# ACA-Py agent for VC Trading Cards (multitenancy)
# Uses the official Open Wallet Foundation image.
# Build: docker build -t vc-cards-acapy .
# Run: docker run --rm -p 8031:8031 -e ACAPY_JWT_SECRET=your-secret vc-cards-acapy

ARG ACAPY_IMAGE=ghcr.io/openwallet-foundation/acapy-agent:latest
FROM ${ACAPY_IMAGE}

WORKDIR /app
COPY argfile.yml /app/argfile.yml

# Override at runtime: -e ACAPY_JWT_SECRET=...
ENV ACAPY_JWT_SECRET=insecure-jwt-secret-change-in-production

EXPOSE 8031

# Args for aca-start (image entrypoint is usually aca-start). Override at run: docker run ... vc-cards-acapy --admin 0.0.0.0 8032
CMD ["--arg-file", "/app/argfile.yml"]
