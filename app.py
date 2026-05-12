import webview
import threading
import json
import os
import base64
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, Response, stream_with_context
from groq import Groq

# ═══════════════════════════════════════════════
#   GANTI DENGAN API KEY KAMU
GROQ_API_KEY = "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"
MODEL_NAME   = "llama-3.3-70b-versatile"
# ═══════════════════════════════════════════════

MEMORY_FILE = "sessions.json"

app = Flask(__name__, static_folder="static", template_folder=".")
client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """Anda adalah asisten AI profesional yang cerdas dan serba bisa.

ATURAN FORMAT:
- Gunakan Markdown untuk semua jawaban: **bold**, *italic*, `code`, heading, list, tabel.
- Untuk kode program, selalu gunakan fenced code block dengan bahasa: ```python, ```js, dll.
- Untuk diagram, gunakan blok Mermaid:
  ```mermaid
  graph TD
      A --> B
  ```
- Diagram yang didukung: flowchart, sequence diagram, class diagram, ER diagram, gantt, pie chart.
- Jawaban terstruktur dan langsung ke poin.
- Bahasa Indonesia yang baku, profesional, namun mudah dipahami."""

# ── Session management ────────────────────────────────────────────────────────

def load_sessions():
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_sessions(sessions):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[warn] Gagal simpan sesi: {e}")

sessions = load_sessions()

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return open("index.html", encoding="utf-8").read()

@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    result = []
    for sid, data in sessions.items():
        result.append({
            "id": sid,
            "title": data.get("title", "Percakapan Baru"),
            "created": data.get("created", ""),
            "message_count": len(data.get("messages", []))
        })
    result.sort(key=lambda x: x["created"], reverse=True)
    return jsonify(result)

@app.route("/api/sessions", methods=["POST"])
def create_session():
    sid = str(uuid.uuid4())[:8]
    sessions[sid] = {
        "title": "Percakapan Baru",
        "created": datetime.now().isoformat(),
        "messages": []
    }
    save_sessions(sessions)
    return jsonify({"id": sid})

@app.route("/api/sessions/<sid>", methods=["GET"])
def get_session(sid):
    if sid not in sessions:
        return jsonify({"error": "Sesi tidak ditemukan"}), 404
    return jsonify(sessions[sid])

@app.route("/api/sessions/<sid>", methods=["DELETE"])
def delete_session(sid):
    if sid in sessions:
        del sessions[sid]
        save_sessions(sessions)
    return jsonify({"ok": True})

@app.route("/api/sessions/<sid>/rename", methods=["POST"])
def rename_session(sid):
    data = request.json
    if sid in sessions:
        sessions[sid]["title"] = data.get("title", "Percakapan Baru")
        save_sessions(sessions)
    return jsonify({"ok": True})

@app.route("/api/chat/<sid>", methods=["POST"])
def chat(sid):
    if sid not in sessions:
        return jsonify({"error": "Sesi tidak ditemukan"}), 404

    data = request.json
    user_message = data.get("message", "").strip()
    files = data.get("files", [])  # [{name, type, data (base64)}]

    if not user_message and not files:
        return jsonify({"error": "Pesan kosong"}), 400

    # Build content
    content_parts = []
    for f in files:
        if f["type"].startswith("image/"):
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:{f['type']};base64,{f['data']}"}
            })
        elif f["type"] == "application/pdf":
            content_parts.append({
                "type": "text",
                "text": f"[File PDF diunggah: {f['name']}]\n{decode_pdf_text(f['data'])}"
            })

    if user_message:
        content_parts.append({"type": "text", "text": user_message})

    # Store user message
    user_msg = {
        "role": "user",
        "content": user_message,
        "files": [{"name": f["name"], "type": f["type"]} for f in files],
        "time": datetime.now().strftime("%H:%M")
    }
    sessions[sid]["messages"].append(user_msg)

    # Auto-title on first message
    if len(sessions[sid]["messages"]) == 1 and user_message:
        sessions[sid]["title"] = user_message[:40] + ("..." if len(user_message) > 40 else "")

    # Build messages for API
    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in sessions[sid]["messages"][-20:]:
        if m["role"] == "user":
            api_messages.append({"role": "user", "content": m["content"] or "(file diunggah)"})
        elif m["role"] == "assistant":
            api_messages.append({"role": "assistant", "content": m["content"]})

    # Override last user message with full content (including images)
    if content_parts:
        api_messages[-1]["content"] = content_parts

    def generate():
        full_reply = ""
        try:
            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=api_messages,
                temperature=0.7,
                max_tokens=2048,
                stream=True
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                full_reply += delta
                yield f"data: {json.dumps({'delta': delta})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            sessions[sid]["messages"].append({
                "role": "assistant",
                "content": full_reply,
                "time": datetime.now().strftime("%H:%M")
            })
            save_sessions(sessions)
            yield f"data: {json.dumps({'done': True})}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

def decode_pdf_text(b64data: str) -> str:
    try:
        import io
        raw = base64.b64decode(b64data)
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            return "(PyPDF tidak terinstall, konten PDF tidak dapat dibaca)"
    except Exception as e:
        return f"(Gagal membaca PDF: {e})"

# ── Entry point ───────────────────────────────────────────────────────────────

def start_flask():
    app.run(port=7860, debug=False, use_reloader=False)

if __name__ == "__main__":
    if not GROQ_API_KEY or GROQ_API_KEY == "ISI_API_KEY_KAMU_DISINI":
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk(); r.withdraw()
        messagebox.showerror("Error", "Isi GROQ_API_KEY di app.py terlebih dahulu!")
        r.destroy()
        exit(1)

    t = threading.Thread(target=start_flask, daemon=True)
    t.start()

    import time; time.sleep(1)

    webview.create_window(
        "Nexus AI",
        "http://127.0.0.1:7860",
        width=1200, height=800,
        min_size=(800, 600),
        resizable=True
    )
    webview.start()
