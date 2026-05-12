import webview
import threading
import json
import os
import base64
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
from groq import Groq

# ═══════════════════════════════════════════════
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
MODEL_NAME   = "llama-3.3-70b-versatile"
# ═══════════════════════════════════════════════

MEMORY_FILE = "sessions.json"

app = Flask(__name__, static_folder=".", static_url_path='')
client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """Anda adalah asisten AI profesional yang cerdas dan serba bisa.

ATURAN FORMAT:
- Gunakan Markdown untuk semua jawaban: **bold**, *italic*, `code`, heading, list, tabel.
- Untuk kode program, selalu gunakan fenced code block dengan bahasa: ```python, ```js, dll.
- Untuk diagram, gunakan blok Mermaid:
  ```mermaid
  graph TD
      A --> B
