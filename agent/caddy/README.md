# Caddy reverse proxy for VC Trading Cards agent

Caddy service that reverse-proxies WebSocket and HTTP traffic to the ACA-Py agent. Exposes the agent’s admin and inbound transport through a single port.

## Environment variables

Set these when running the container:

- `CADDY_PORT` — Port Caddy listens on (e.g. `8030`)
- `AGENT_HOST` — Agent hostname or IP (e.g. `vc-cards-agent` or `localhost`)
- `AGENT_WS_PORT` — Agent WebSocket / inbound transport port (e.g. `8022`)
- `AGENT_HTTP_PORT` — Agent Admin HTTP port (e.g. `8020`)

## Build

From repo root:

```bash
docker build -f agent/caddy/Dockerfile -t vc-cards-caddy agent/caddy
```

## Run

```bash
docker run --rm -p 8030:8030 \
  -e CADDY_PORT=8030 \
  -e AGENT_HOST=vc-cards-agent \
  -e AGENT_WS_PORT=8022 \
  -e AGENT_HTTP_PORT=8020 \
  vc-cards-caddy
```

Replace `vc-cards-agent` and ports with your agent host and ports. Caddy sends WebSocket requests (`Connection: Upgrade`) to `AGENT_HOST:AGENT_WS_PORT` (inbound transport) and other HTTP to `AGENT_HOST:AGENT_HTTP_PORT` (admin API).
