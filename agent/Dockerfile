# ACA-Py agent for Tritone Cards (multitenancy via multitenant_provider plugin)
# Build: docker build -f agent/Dockerfile -t tritone-cards-acapy agent/
# Run: docker run --rm -p 8020:8020 -p 8022:8022 -e ACAPY_JWT_SECRET=your-secret tritone-cards-acapy
#
# Plugins: multitenancy (built-in, enabled in argfile) + multitenant_provider; traction-innkeeper (tenant/reservation management).

ARG ACAPY_IMAGE=ghcr.io/openwallet-foundation/acapy-agent:latest
FROM ${ACAPY_IMAGE}

WORKDIR /app

# Multitenancy: built-in in ACA-Py (see argfile). Plugin for JWT/tenant management:
RUN pip install --no-cache-dir git+https://github.com/openwallet-foundation/acapy-plugins@1.4.0#subdirectory=multitenant_provider

# Traction Innkeeper: tenant/reservation management (reservations, check-in, etc.) — BC Gov Traction
RUN pip install --no-cache-dir "git+https://github.com/bcgov/traction@main#subdirectory=plugins/traction_innkeeper"

COPY argfile.yml /app/argfile.yml
COPY entrypoint.py /app/entrypoint.py

# Override at runtime: -e ACAPY_JWT_SECRET=... -e INNKEEPER_WALLET_KEY=...
ENV ACAPY_JWT_SECRET=insecure-jwt-secret-change-in-production
ENV INNKEEPER_WALLET_KEY=change-me-innkeeper-in-production

EXPOSE 8020 8022

ENTRYPOINT ["python", "/app/entrypoint.py"]
CMD []
