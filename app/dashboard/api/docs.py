"""
app/dashboard/api/docs.py
─────────────────────────
Phase 7: Swagger UI served from CDN.

Endpoints:
  GET /api/docs        — Swagger UI HTML page
  GET /api/openapi.yaml — OpenAPI 3.0 spec file

No additional dependencies — Swagger UI is loaded from unpkg CDN.
The spec is served from docs/openapi.yaml in the project root.
"""

from pathlib import Path
from flask import Blueprint, Response, send_file

docs_bp = Blueprint("docs", __name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SPEC_PATH = _PROJECT_ROOT / "docs" / "openapi.yaml"

_SWAGGER_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Zowsup Dashboard API Docs</title>
  <link rel="stylesheet"
        href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  <style>
    body {{ margin: 0; }}
    .topbar {{ display: none; }}
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({{
      url: "/api/openapi.yaml",
      dom_id: "#swagger-ui",
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
      layout: "BaseLayout",
      deepLinking: true,
      validatorUrl: null,
    }});
  </script>
</body>
</html>
"""


@docs_bp.route("/api/docs")
def swagger_ui():
    """Serve Swagger UI HTML (no auth required — spec is public)."""
    return Response(_SWAGGER_HTML, mimetype="text/html")


@docs_bp.route("/api/openapi.yaml")
def openapi_spec():
    """Serve the raw OpenAPI YAML spec."""
    if not _SPEC_PATH.exists():
        return Response("# openapi.yaml not found", status=404, mimetype="text/plain")
    return send_file(str(_SPEC_PATH), mimetype="application/yaml")
