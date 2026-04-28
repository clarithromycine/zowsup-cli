# Zowsup Dashboard — Monitoring, APM, and Alerting

This document covers:
- **8.11** — Sentry error tracking (code integration)
- **8.12** — Application Performance Monitoring (APM)
- **8.13** — Alerting rules

---

## 8.11 — Sentry error tracking

### Setup

1. Create a free project at https://sentry.io.
2. Install the SDK:
   ```bash
   pip install "sentry-sdk[flask]"
   ```
3. Set your DSN in `.env`:
   ```
   SENTRY_DSN=https://<key>@<org>.ingest.sentry.io/<project>
   SENTRY_ENVIRONMENT=production
   SENTRY_TRACES_SAMPLE_RATE=0.1
   ```
4. Restart the dashboard — Sentry initialises automatically inside `create_app()`.

### What is captured

| Event type | Captured? |
|-----------|-----------|
| Unhandled exceptions | ✅ automatically |
| `logging.ERROR` and above | ✅ via LoggingIntegration |
| `logging.WARNING` | as breadcrumbs |
| User PII (IP, user agent) | ✅ stripped (`send_default_pii=False`) |
| Performance traces | ✅ at `SENTRY_TRACES_SAMPLE_RATE` |

### Ignoring test traffic

In `.env` for staging:
```
SENTRY_ENVIRONMENT=staging
```
Use Sentry's **Inbound Filters → Filter localhost** to exclude dev traffic.

---

## 8.12 — Application Performance Monitoring (APM)

### Option A — Sentry Performance (built-in)

With `SENTRY_TRACES_SAMPLE_RATE > 0` Sentry automatically captures:
- HTTP transaction duration
- Database query time (via SQLAlchemy integration, if used)
- Slowest endpoints ranked by P95 latency

No extra code needed.

### Option B — Prometheus + Grafana (self-hosted)

#### Expose metrics endpoint

Install:
```bash
pip install prometheus-flask-exporter
```

Add to `create_app()` in `app/dashboard/api/app.py`:
```python
from prometheus_flask_exporter import PrometheusMetrics
PrometheusMetrics(app, default_labels={"app": "dashboard"})
```

This exposes `GET /metrics` in Prometheus text format.

#### Key metrics exposed

| Metric | Type | Description |
|--------|------|-------------|
| `flask_http_request_duration_seconds` | Histogram | Request latency by endpoint |
| `flask_http_request_total` | Counter | Total requests by status code |
| `flask_http_request_exceptions_total` | Counter | Unhandled exceptions |

#### Grafana dashboard

Import dashboard ID **9528** ("Flask" dashboard) from grafana.com.

Set the data source to your Prometheus instance and the `app` label to `dashboard`.

### Option C — Elastic APM (cloud or self-hosted)

Install:
```bash
pip install elastic-apm[flask]
```

```python
from elasticapm.contrib.flask import ElasticAPM
apm = ElasticAPM(app)
```

Set `ELASTIC_APM_SERVER_URL` and `ELASTIC_APM_SECRET_TOKEN` in `.env`.

---

## 8.13 — Alerting rules

### Sentry alerts (recommended starting point)

Go to **Alerts → Create Alert** in your Sentry project.

| Alert | Condition | Action |
|-------|-----------|--------|
| Error spike | Error events > 10 in 5 min | Email + Slack |
| P95 latency | Transaction p95 > 2 s | Email |
| New issue | Any new issue | Slack |
| Issue regression | Resolved issue re-occurs | Email |

### Prometheus / Alertmanager rules

Save to `/etc/prometheus/rules/dashboard.yml`:

```yaml
groups:
  - name: dashboard
    rules:
      - alert: HighErrorRate
        expr: |
          rate(flask_http_request_total{app="dashboard", status=~"5.."}[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Dashboard HTTP 5xx rate > 5%"

      - alert: SlowResponses
        expr: |
          histogram_quantile(0.95,
            rate(flask_http_request_duration_seconds_bucket{app="dashboard"}[5m])
          ) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Dashboard P95 latency > 2 s"

      - alert: DashboardDown
        expr: up{job="dashboard"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Dashboard is down"
```

### Simple uptime monitoring (no extra dependencies)

Use a free service like **UptimeRobot** or **Better Uptime**:
- Monitor URL: `http://your-server:5000/api/health`
- Expected keyword: `"ok"` or `"degraded"`
- Alert after 2 consecutive failures
- Notification: email / Slack / PagerDuty

### Cron-based alert script

For minimal setups, a cron job can poll the health endpoint and send an email:

```bash
#!/bin/bash
# /etc/cron.d/dashboard-health — run every minute
STATUS=$(curl -sf http://localhost:5000/api/health | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null)
if [ "$STATUS" != "ok" ] && [ "$STATUS" != "degraded" ]; then
  echo "Dashboard health check FAILED (status=$STATUS)" | mail -s "[ALERT] Dashboard down" ops@example.com
fi
```
