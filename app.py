from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from g4f.client import Client
from sarvamai import SarvamAI
import requests
import json
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import base64  # Ensure this import is present
from groq import Groq
from transcription import transcribe_file, clean_marathi_text
from googleapiclient.discovery import build
import random


# Load environment variables
load_dotenv()

# YouTube API setup
API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE = build("youtube", "v3", developerKey=API_KEY)


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
key = os.getenv("GROQ_API_KEY")
print(key)
sarvam_client = SarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))
client = Groq(default_headers={"Groq-Model-Version": "latest"}, api_key=os.getenv("GROQ_API_KEY"))



# Home page with links to both features
@app.route('/')
def index():
    return render_template('index.html')

# Chatbot endpoint (now handles full conversation history)
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'GET':
        return render_template('chat.html')

    if request.method == 'POST':
        try:
            data = request.get_json(silent=True)
            if data is None:
                data = request.form.to_dict()

            messages = data.get('messages')
            if not messages and data.get('message'):
                messages = [{"role": "user", "content": data['message']}]

            if not messages:
                return jsonify({'error': 'No message content provided'}), 400

            # ✅ Groq API call (no compound_custom)
            completion = client.chat.completions.create(
                model="groq/compound-mini",   # or try "mixtral-8x7b-32768" for larger model
                messages=messages,
                temperature=1,
                max_completion_tokens=1024,
                top_p=1,
                stream=False  # You can enable streaming later
            )

            # ✅ Extract assistant’s reply
            if completion and completion.choices:
                bot_response = completion.choices[0].message.content
                return jsonify({'response': bot_response})
            else:
                return jsonify({'error': 'No response generated'}), 500

        except Exception as e:
            print(f"Error in chat endpoint: {str(e)}")
            return jsonify({'error': f'Chat processing error: {str(e)}'}), 500


# Image generation endpoint
@app.route('/image', methods=['GET', 'POST'])
def image():
    client = Client()
    if request.method == 'GET':
        return render_template('image.html')
    
    if request.method == 'POST':
        prompt = request.form.get('prompt')
        if not prompt:
            return jsonify({'error': 'No prompt provided'}), 400
        
        try:
            response = client.images.generate(
                model="flux",
                prompt=prompt,
                response_format="url"
            )
            image_url = response.data[0].url
            return jsonify({'image_url': image_url})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        

@app.route('/ocr', methods=['GET', 'POST'])
def ocr():
    if request.method == 'GET':
        return render_template('ocr.html')
    
    if request.method == 'POST':
        if 'images' not in request.files:
            return jsonify({'error': 'No image files provided'}), 400
        
        files = request.files.getlist('images')
        if not files:
            return jsonify({'error': 'No selected files'}), 400
        
        results = []
        for file in files:
            if file:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                try:
                    with open(filepath, 'rb') as img_file:
                        img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                    
                    response = requests.post(
                        url="https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": os.getenv('SITE_URL'),
                            "X-Title": os.getenv('SITE_NAME'),
                        },
                        json={
                            "model": "mistralai/mistral-small-3.2-24b-instruct:free",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "Extract all visible text clearly from this image and return plain text only."
                                        },
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/jpeg;base64,{img_base64}"
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    )
                    print(response) 
                    result = response.json()

                    # ✅ Handle both success and error cases properly
                    if response.status_code != 200:
                        error_msg = result.get("error", {}).get("message", "API request failed.")
                        results.append({'filename': filename, 'text': f"❌ Error: {error_msg}"})
                    elif "choices" in result and result["choices"]:
                        extracted_text = result["choices"][0]["message"]["content"].strip()
                        results.append({'filename': filename, 'text': extracted_text})
                    else:
                        results.append({'filename': filename, 'text': "❌ No text extracted or empty response."})

                except Exception as e:
                    results.append({'filename': filename, 'text': f"❌ Exception: {str(e)}"})

                finally:
                    if os.path.exists(filepath):
                        os.remove(filepath)

        return jsonify({'results': results})
    
# Serve uploaded files (including TTS audio)
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve generated audio files."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/tts', methods=['GET', 'POST'])
def tts():
    if request.method == 'GET':
        return render_template('tts.html')

    try:
        data = request.get_json()
        text = data.get("text")
        speaker = data.get("voice", "anushka")
        language = data.get("language", "hi-IN")

        if not text:
            return jsonify({"error": "No text provided"}), 400

        # Clean up old .wav files
        for f in os.listdir(app.config['UPLOAD_FOLDER']):
            if f.endswith(".wav"):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], f))

        filename = f"tts_output_{speaker}.wav"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Generate audio
        response = sarvam_client.text_to_speech.convert(
            text=text,
            target_language_code=language,
            speaker=speaker,
            pitch=0,
            pace=1,
            loudness=1,
            speech_sample_rate=22050,
            enable_preprocessing=True,
            model="bulbul:v2"
        )

        # Decode and save the first audio file
        if hasattr(response, 'audios') and response.audios:
            audio_base64 = response.audios[0]
            # Fix: ensure we handle bytes properly
            if isinstance(audio_base64, str):
                audio_bytes = base64.b64decode(audio_base64)
            else:
                audio_bytes = audio_base64

            with open(filepath, 'wb') as f:
                f.write(audio_bytes)

            audio_url = f"/uploads/{filename}"
            return jsonify({
                "audio_url": audio_url,
                "download_url": audio_url
            })
        else:
            return jsonify({"error": "No audio generated"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/transcribe", methods=["GET", "POST"])
def transcribe():
    if request.method == "GET":
        return render_template("transcribe.html")

    # POST: handle file upload and transcription
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        transcript = clean_marathi_text(transcribe_file(filepath))
        return jsonify({"transcribed_text": transcript})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@app.route('/chatdoc', methods=['GET'])
def chatdoc_page():
    return render_template('chatdoc.html')

@app.route('/upload_doc', methods=['POST'])
def upload_doc():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    # Forward to rag_chat FastAPI
    RAG_API_URL = os.getenv("RAG_API_URL")
    try:
        file_bytes = file.read()
        files = {
            "file": (secure_filename(file.filename), file_bytes, file.content_type or "application/pdf")
        }
        resp = requests.post(f"{RAG_API_URL}/upload_doc", files=files, timeout=30)
        try:
            payload = resp.json()
        except Exception:
            payload = {"status_code": resp.status_code, "text": resp.text}
        if resp.status_code // 100 == 2:
            return jsonify(payload)
        else:
            return jsonify({"error": "RAG service error", "detail": payload}), resp.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to contact RAG service", "detail": str(e)}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/ask_doc', methods=['POST'])
def ask_doc():
    # Accept JSON body or form data
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    question = data.get("query") or data.get("question") or ""
    if not question:
        return jsonify({"error": "No question provided"}), 400

    RAG_API_URL = os.getenv("RAG_API_URL")
    try:
        # Send request to the FastAPI backend
        resp = requests.post(
            f"{RAG_API_URL}/ask",
            data={"question": question},
            headers={"Accept": "application/json"},
            timeout=30
        )

        # Try to parse JSON response
        try:
            payload = resp.json()
        except Exception:
            payload = {"text": resp.text}


        # ✅ FIX: Standardize payload structure for frontend
        answer = payload.get("answer")
        print("Answer from RAG:", answer)
        source = payload.get("source")

        # ✅ Ensure the data is clean before sending back
        if not answer:
            answer = "No answer returned from RAG service."

        return jsonify({
            "answer": answer.strip(),
            "source": source
        })

    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "Failed to contact RAG service",
            "detail": str(e)
        }), 502

    except Exception as e:
        return jsonify({
            "error": "Unexpected error",
            "detail": str(e)
        }), 500



@app.route('/youtube', methods=['GET'])
def youtube_page():
    """Render the YouTube search UI"""
    return render_template('youtube.html')


@app.route('/youtube/search', methods=['GET'])
def youtube_search():
    """Search videos by query"""
    query = request.args.get('q', 'AI')

    try:
        request_api = YOUTUBE.search().list(
            q=query,
            part="snippet",
            maxResults=10,
            type="video"
        )
        response = request_api.execute()

        videos = []
        for item in response.get("items", []):
            videos.append({
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                "video_url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                "video_id": item["id"]["videoId"]
            })

        return jsonify(videos)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/youtube/random', methods=['GET'])
def youtube_random():
    """Fetch random videos"""
    random_topics = ["music", "tech", "sports", "news", "funny", "gaming", "AI", "education", "space"]
    random_query = random.choice(random_topics)

    try:
        request_api = YOUTUBE.search().list(
            q=random_query,
            part="snippet",
            maxResults=10,
            type="video"
        )
        response = request_api.execute()

        videos = []
        for item in response.get("items", []):
            videos.append({
                "topic": random_query,
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
                "video_url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                "video_id": item["id"]["videoId"]
            })

        return jsonify(videos)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000,debug=True)
