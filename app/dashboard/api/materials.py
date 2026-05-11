"""
Materials API Blueprint.

Endpoints:
  GET    /api/materials/             list materials (optional ?type= & ?tag= filter)
  POST   /api/materials/             create a text / metadata material record
  DELETE /api/materials/<id>         delete a material
  POST   /api/materials/upload       upload a file (image / document / audio / video)
  POST   /api/materials/generate     AI-generate an image via LLM or image-gen API
  GET    /api/materials/templates    list message templates
  POST   /api/materials/templates    create a message template
  PUT    /api/materials/templates/<id>  update a template
  DELETE /api/materials/templates/<id> delete a template
"""

import json
import logging
import os
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from app.dashboard.api.auth import check_bearer
from app.dashboard.api.rate_limit import limiter
from app.dashboard.utils.db_init import get_db_connection

materials_bp = Blueprint("materials", __name__)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

@materials_bp.before_request
def _check_auth():
    return check_bearer()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
    "audio/mpeg", "audio/ogg", "audio/wav",
    "video/mp4", "video/ogg",
}

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


def _materials_dir() -> Path:
    """Return the directory where uploaded material files are stored."""
    db_path = current_app.config["DASHBOARD_DB_PATH"]
    base = Path(db_path).parent / "materials"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _row_to_dict(row) -> dict:
    d = dict(row)
    if d.get("tags"):
        try:
            d["tags"] = json.loads(d["tags"])
        except Exception:
            d["tags"] = []
    else:
        d["tags"] = []
    return d


def _template_row_to_dict(row) -> dict:
    d = dict(row)
    if d.get("tags"):
        try:
            d["tags"] = json.loads(d["tags"])
        except Exception:
            d["tags"] = []
    else:
        d["tags"] = []
    if d.get("content_json"):
        try:
            d["content_json"] = json.loads(d["content_json"])
        except Exception:
            pass
    return d


# ---------------------------------------------------------------------------
# GET /api/materials/
# ---------------------------------------------------------------------------

@materials_bp.route("/", methods=["GET"])
@limiter.limit("60/minute")
def list_materials():
    db_path = current_app.config["DASHBOARD_DB_PATH"]
    type_filter = request.args.get("type")
    tag_filter = request.args.get("tag")

    query = "SELECT * FROM materials"
    params: list = []
    clauses: list[str] = []

    if type_filter:
        clauses.append("type = ?")
        params.append(type_filter)
    if tag_filter:
        clauses.append("tags LIKE ?")
        params.append(f'%"{tag_filter}"%')

    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"

    with get_db_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()

    return jsonify({"materials": [_row_to_dict(r) for r in rows]})


# ---------------------------------------------------------------------------
# POST /api/materials/  — create text material
# ---------------------------------------------------------------------------

@materials_bp.route("/", methods=["POST"])
@limiter.limit("30/minute")
def create_material():
    db_path = current_app.config["DASHBOARD_DB_PATH"]
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    mat_type = str(body.get("type", "text")).strip()
    content = str(body.get("content", "")).strip()
    tags = body.get("tags", [])

    if not name:
        return jsonify({"error": "name is required"}), 400
    if mat_type not in ("text", "image", "document", "video", "audio"):
        return jsonify({"error": "invalid type"}), 400

    tags_json = json.dumps(tags if isinstance(tags, list) else [])

    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO materials (name, type, content, tags)
               VALUES (?, ?, ?, ?)""",
            (name, mat_type, content, tags_json),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM materials WHERE id=?", (cur.lastrowid,)).fetchone()

    return jsonify(_row_to_dict(row)), 201


# ---------------------------------------------------------------------------
# DELETE /api/materials/<int:mat_id>
# ---------------------------------------------------------------------------

@materials_bp.route("/<int:mat_id>", methods=["DELETE"])
@limiter.limit("30/minute")
def delete_material(mat_id: int):
    db_path = current_app.config["DASHBOARD_DB_PATH"]

    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (mat_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        # Remove file if stored locally
        if row["file_path"]:
            try:
                Path(row["file_path"]).unlink(missing_ok=True)
            except Exception:
                pass
        conn.execute("DELETE FROM materials WHERE id=?", (mat_id,))
        conn.commit()

    return jsonify({"deleted": mat_id})


# ---------------------------------------------------------------------------
# POST /api/materials/upload  — file upload
# ---------------------------------------------------------------------------

@materials_bp.route("/upload", methods=["POST"])
@limiter.limit("10/minute")
def upload_material():
    db_path = current_app.config["DASHBOARD_DB_PATH"]

    if "file" not in request.files:
        return jsonify({"error": "no file in request"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "empty filename"}), 400

    mime = f.mimetype or ""
    if mime not in ALLOWED_MIME_TYPES:
        return jsonify({"error": f"mime type not allowed: {mime}"}), 400

    # Read into memory to check size before writing
    data = f.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return jsonify({"error": "file too large (max 20 MB)"}), 413

    ext = Path(f.filename).suffix.lower()
    safe_filename = uuid.uuid4().hex + ext
    dest = _materials_dir() / safe_filename
    dest.write_bytes(data)

    # Derive material type from MIME
    if mime.startswith("image/"):
        mat_type = "image"
    elif mime.startswith("audio/"):
        mat_type = "audio"
    elif mime.startswith("video/"):
        mat_type = "video"
    else:
        mat_type = "document"

    name = request.form.get("name") or Path(f.filename).stem
    tags = request.form.get("tags", "[]")
    try:
        tags_parsed = json.loads(tags)
    except Exception:
        tags_parsed = []

    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO materials (name, type, file_path, mime_type, tags)
               VALUES (?, ?, ?, ?, ?)""",
            (name, mat_type, str(dest), mime, json.dumps(tags_parsed)),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM materials WHERE id=?", (cur.lastrowid,)).fetchone()

    return jsonify(_row_to_dict(row)), 201


# ---------------------------------------------------------------------------
# POST /api/materials/generate  — AI image generation (stub + LLM path)
# ---------------------------------------------------------------------------

@materials_bp.route("/generate", methods=["POST"])
@limiter.limit("10/minute")
def generate_material():
    """
    Generate an image using a configured image-gen model.

    Body JSON:
      { "prompt": str, "name": str (optional), "tags": [] (optional) }

    Implementation:
      1. Try calling the project's AI module (OpenAI / compatible image endpoint).
      2. If not configured, returns a placeholder response with status 'pending'.
    """
    db_path = current_app.config["DASHBOARD_DB_PATH"]
    body = request.get_json(silent=True) or {}
    prompt = str(body.get("prompt", "")).strip()
    name = str(body.get("name", "")).strip() or "AI生成图片"
    tags = body.get("tags", ["ai-generated"])

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    # Try AI generation
    image_url: str | None = None
    error_msg: str | None = None
    try:
        image_url = _ai_generate_image(prompt)
    except Exception as exc:
        logger.warning("AI image generation failed: %s", exc)
        error_msg = str(exc)

    if image_url:
        # Store in DB as image material with content = URL
        tags_with_ai = list(tags) if isinstance(tags, list) else []
        if "ai-generated" not in tags_with_ai:
            tags_with_ai.append("ai-generated")

        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                """INSERT INTO materials (name, type, content, ai_prompt, tags)
                   VALUES (?, 'image', ?, ?, ?)""",
                (name, image_url, prompt, json.dumps(tags_with_ai)),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM materials WHERE id=?", (cur.lastrowid,)).fetchone()

        return jsonify({**_row_to_dict(row), "generated": True}), 201

    # AI not configured — return stub response
    return jsonify({
        "generated": False,
        "prompt": prompt,
        "error": error_msg or "AI image generation not configured. Set OPENAI_API_KEY or IMAGE_GEN_API_URL.",
    }), 202


def _ai_generate_image(prompt: str) -> str:
    """
    Call the AI image generation API and return a URL.

    Reads configuration from environment variables:
      IMAGE_GEN_API_URL   — compatible OpenAI images endpoint (default: OpenAI)
      IMAGE_GEN_API_KEY   — API key (falls back to OPENAI_API_KEY)
      IMAGE_GEN_MODEL     — model name (default: dall-e-3)
    """
    import urllib.request

    api_url = os.environ.get("IMAGE_GEN_API_URL", "https://api.openai.com/v1/images/generations")
    api_key = os.environ.get("IMAGE_GEN_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("IMAGE_GEN_MODEL", "dall-e-3")

    if not api_key:
        raise RuntimeError("No API key configured (set IMAGE_GEN_API_KEY or OPENAI_API_KEY)")

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
    }).encode()

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        result = json.loads(resp.read())

    return result["data"][0]["url"]


# ---------------------------------------------------------------------------
# GET /api/materials/templates
# ---------------------------------------------------------------------------

@materials_bp.route("/templates", methods=["GET"])
@limiter.limit("60/minute")
def list_templates():
    db_path = current_app.config["DASHBOARD_DB_PATH"]
    type_filter = request.args.get("type")
    query = "SELECT * FROM message_templates"
    params: list = []
    if type_filter:
        query += " WHERE type = ?"
        params.append(type_filter)
    query += " ORDER BY created_at DESC"

    with get_db_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()

    return jsonify({"templates": [_template_row_to_dict(r) for r in rows]})


# ---------------------------------------------------------------------------
# POST /api/materials/templates
# ---------------------------------------------------------------------------

@materials_bp.route("/templates", methods=["POST"])
@limiter.limit("30/minute")
def create_template():
    db_path = current_app.config["DASHBOARD_DB_PATH"]
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    tpl_type = str(body.get("type", "text")).strip()
    content = body.get("content_json")
    description = str(body.get("description", "")).strip()
    tags = body.get("tags", [])

    if not name:
        return jsonify({"error": "name is required"}), 400
    if tpl_type not in ("text", "image", "document", "location", "buttons", "list"):
        return jsonify({"error": "invalid type"}), 400
    if content is None:
        return jsonify({"error": "content_json is required"}), 400

    content_str = json.dumps(content) if not isinstance(content, str) else content
    tags_json = json.dumps(tags if isinstance(tags, list) else [])

    with get_db_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO message_templates (name, type, content_json, description, tags)
               VALUES (?, ?, ?, ?, ?)""",
            (name, tpl_type, content_str, description, tags_json),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM message_templates WHERE id=?", (cur.lastrowid,)).fetchone()

    return jsonify(_template_row_to_dict(row)), 201


# ---------------------------------------------------------------------------
# PUT /api/materials/templates/<int:tpl_id>
# ---------------------------------------------------------------------------

@materials_bp.route("/templates/<int:tpl_id>", methods=["PUT"])
@limiter.limit("30/minute")
def update_template(tpl_id: int):
    db_path = current_app.config["DASHBOARD_DB_PATH"]
    body = request.get_json(silent=True) or {}

    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM message_templates WHERE id=?", (tpl_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404

        name = str(body.get("name", row["name"])).strip()
        tpl_type = str(body.get("type", row["type"])).strip()
        content = body.get("content_json", json.loads(row["content_json"]))
        description = str(body.get("description", row["description"] or "")).strip()
        tags = body.get("tags", json.loads(row["tags"] or "[]"))

        content_str = json.dumps(content) if not isinstance(content, str) else content
        tags_json = json.dumps(tags if isinstance(tags, list) else [])

        conn.execute(
            """UPDATE message_templates
               SET name=?, type=?, content_json=?, description=?, tags=?,
                   updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (name, tpl_type, content_str, description, tags_json, tpl_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM message_templates WHERE id=?", (tpl_id,)).fetchone()

    return jsonify(_template_row_to_dict(row))


# ---------------------------------------------------------------------------
# DELETE /api/materials/templates/<int:tpl_id>
# ---------------------------------------------------------------------------

@materials_bp.route("/templates/<int:tpl_id>", methods=["DELETE"])
@limiter.limit("30/minute")
def delete_template(tpl_id: int):
    db_path = current_app.config["DASHBOARD_DB_PATH"]

    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT id FROM message_templates WHERE id=?", (tpl_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        conn.execute("DELETE FROM message_templates WHERE id=?", (tpl_id,))
        conn.commit()

    return jsonify({"deleted": tpl_id})
