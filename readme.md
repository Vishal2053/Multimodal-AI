# Advanced Multimodal AI

A professional, production-minded web application that unifies multiple AI capabilities — chat, document QA (RAG), image generation, OCR, transcription and TTS — into a single, extensible platform.

## Key Features

- Document Question Answering (RAG) — upload PDF/DOCX/TXT, create embeddings, semantic search with citations  
- Conversational Chat — Groq / LLM-backed chat UI  
- Image Generation — prompt→image generation with preview  
- OCR — extract text from images (batch support)  
- Audio/Video Transcription — speaker separation & timestamps (where supported)  
- Text-to-Speech — multi-voice TTS generation and download  
- YouTube Explorer — search and preview YouTube content  
- Optional Google SSO (Authlib + Flask-Login)  
- Chroma-backed persistent vector store with migration guidance

---

## Project file structure

```
multimodal/
├── app.py                       # Flask frontend + API proxy (uploads, ask forwarding, UI endpoints)
├── rag_chat.py                  # RAG FastAPI service (document processing, embeddings, query)
├── readme.md                    # Project documentation (this file)
├── requirements.txt             # Python dependencies
├── .env                         # Local environment variables (DO NOT COMMIT)
├── templates/                   # Jinja2 HTML templates (site UI)
│   ├── layout.html
│   ├── index.html
│   ├── chat.html
│   ├── chatdoc.html
│   ├── transcribe.html
│   ├── tts.html
│   ├── image.html
│   └── youtube.html
├── static/                      # Static assets (CSS / JS / images)
│   ├── css/
│   └── js/
├── uploads/                     # Temporary upload folder (audio/images/docs)
├── chroma_store/                # Persisted Chroma DB (created at runtime)
├── transcription.py             # Helpers for audio/video transcription
├── website_builder.py           # Utility to scaffold simple sites (optional)
├── rag_utils/                   # (optional) helpers for RAG processing, loaders, splitters
│   └── ...
├── tests/                       # Unit/integration tests (recommended)
│   └── test_uploads.py
└── docs/                        # Additional docs, deployment scripts, diagrams
    └── deployment.md
```

Brief file notes
- app.py — main Flask app that serves UI and proxies /upload_doc and /ask_doc to the RAG FastAPI service (RAG_API_URL).  
- rag_chat.py — document loader → splitter → embeddings → Chroma → retrieval chain. Can run separately (uvicorn).  
- templates/ & static/ — frontend UI. Modify to customize pages.  
- chroma_store/ — persistent vector store; must be writable by the app. Use chroma-migrate if migrating older data.  
- transcription.py — contains transcribe_file and any language-specific cleaning functions.  
- requirements.txt — pin and install required packages in a venv.

---

## Quickstart (Windows)

1. Create virtual env and activate
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

2. Create `.env` (example keys)
```
OPENROUTER_API_KEY=...
GROQ_API_KEY=...
SARVAM_API_KEY=...
RAG_API_URL=http://127.0.0.1:8000
YOUTUBE_API_KEY=...
```

3. Start RAG FastAPI (if using separate service)
```powershell
uvicorn rag_chat:app --reload --host 127.0.0.1 --port 8000
```

4. Start Flask frontend
```powershell
python app.py
```

Open http://127.0.0.1:5000

---

## Environment & configuration

- RAG_API_URL — URL of rag_chat service (frontend forwards uploads & questions)  
- CHROMA_PATH — path for Chroma persistence (default `./chroma_store`)  
- GROQ_API_KEY, OPENROUTER_API_KEY, SARVAM_API_KEY, YOUTUBE_API_KEY — service keys  
- DISABLE_TELEMETRY=1 — optional to silence chromadb telemetry during debugging

---

## Troubleshooting (common issues)

- "Please upload a document first" — ensure rag_chat persisted a Chroma collection; check `chroma_store/` contents and rag service logs.  
- langchain/langchain-core import errors — install compatible packages: `pip install --upgrade langchain langchain-core langchain-huggingface langchain_community`  
- pdfminer PSSyntaxError — pin `pdfminer.six` or fall back to PyPDF2 extraction.  
- NLTK missing tokenizer — run `python -c "import nltk; nltk.download('punkt_tab')"` in the venv.  
- pip hash mismatch — clear pip cache: `python -m pip cache purge` and retry with `--no-cache-dir`.

---

## Deployment notes

- Use Gunicorn / Uvicorn behind a reverse proxy (NGINX) for production.  
- Serve over HTTPS, secure environment variables, rotate keys.  
- For Chroma data migration: `pip install chroma-migrate` then `chroma-migrate` (follow Chroma docs).  
- Replace in-memory user store with persistent DB when enabling SSO.

---

## Contribution

- Fork → branch → PR; include tests for new features.  
- Prefer small, focused commits and update README/docs for any structural changes.

---

## License

MIT — see LICENSE file.

---