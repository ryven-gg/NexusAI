from flask import Flask, request, jsonify, send_from_directory, Response
from groq import Groq
import os, json, base64, uuid
from datetime import datetime
import threading

app = Flask(__name__, static_folder='.')

# Config
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
client = Groq(api_key=GROQ_API_KEY)
sessions = {}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json')

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    result = [{"id": k, "title": v.get("title", "New"), "created": v.get("created", ""), "message_count": len(v.get("messages", 0))} for k, v in sessions.items()]
    return jsonify(result)

@app.route('/api/chat/<sid>', methods=['POST'])
def chat(sid):
    data = request.get_json() or {}
    message = data.get('message', 'Hello')
    
    try:
        chat_completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": message}]
        )
        return jsonify({"reply": chat_completion.choices[0].message.content})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/health')
def health():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    app.run()
