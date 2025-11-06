from flask import Flask, render_template, request, jsonify, send_from_directory, send_file, flash, redirect, url_for
from g4f.client import Client
from sarvamai import SarvamAI
import requests
import json
import os
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
from werkzeug.utils import secure_filename
import base64  # Ensure this import is present
from groq import Groq
from transcription import transcribe_file, clean_marathi_text
from googleapiclient.discovery import build
import random
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import timedelta
from mongodb import register_user, login_user, logout_user, current_user
from functools import wraps

# Load environment variables
load_dotenv()

# Cloudinary configuration: prefer single CLOUDINARY_URL or individual vars
cloudinary_url = os.getenv("CLOUDINARY_URL")
if cloudinary_url:
    cloudinary.config(cloudinary_url=cloudinary_url)
else:
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    )

# YouTube API setup
API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE = build("youtube", "v3", developerKey=API_KEY)


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")
app.permanent_session_lifetime = timedelta(days=1)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
sarvam_client = SarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))
client = Groq(default_headers={"Groq-Model-Version": "latest"}, api_key=os.getenv("GROQ_API_KEY"))


def login_required(f):
    """Decorator to protect routes that require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user():
            flash("Please login to access this feature.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function



# -------------------- AUTHENTICATION ROUTES --------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    user = current_user()
    if request.method == "GET":
        return render_template("register.html", user=user)

    # Handle both JSON and form submissions
    if request.content_type and "application/json" in request.content_type:
        data = request.get_json()
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")
        profile_image_url = data.get("profile_image")  # accept direct URL in JSON
        if not name or not email or not password:
            return jsonify({"status": "error", "message": "All fields are required"}), 400
        result = register_user(name, email, password, profile_image=profile_image_url)
        return jsonify(result)
    else:
        # Form submission
        data = request.form.to_dict()
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        if not name or not email or not password:
            flash("All fields are required", "error")
            return render_template("register.html", user=user)

        # optional profile image file upload -> Cloudinary
        profile_url = None
        profile_file = request.files.get("profile_image")
        if profile_file and profile_file.filename:
            try:
                upload_res = cloudinary.uploader.upload(
                    profile_file,
                    folder="multimodal_profiles",
                    use_filename=True,
                    unique_filename=False,
                    overwrite=False,
                )
                profile_url = upload_res.get("secure_url")
            except Exception as e:
                print("Cloudinary upload failed:", e)
                flash("Profile image upload failed; continuing without image.", "warning")

        result = register_user(name, email, password, profile_image=profile_url)

        if result.get("status") == "success":
            flash("Successfully registered! Please login.", "success")
            return redirect(url_for('login'))
        else:
            flash(result.get("message", "Registration failed"), "error")
            return render_template("register.html", user=user)


@app.route("/login", methods=["GET", "POST"])
def login():
    user = current_user()
    if request.method == "GET":
        return render_template("login.html", user=user)

    # Handle both JSON and form submissions
    if request.content_type and "application/json" in request.content_type:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"status": "error", "message": "Email and password are required"}), 400

        result = login_user(email, password)
        return jsonify(result)
    else:
        # Form submission
        data = request.form.to_dict()
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            flash("Email and password are required", "error")
            return render_template("login.html", user=user)

        result = login_user(email, password)
        if result.get("status") == "success":
            # ensure session persists and template context has user
            session.permanent = True
            if not session.get("user"):
                session["user"] = result.get("user")
            flash("Successfully logged in!", "success")
            return redirect(url_for('index'))
        else:
            flash(result.get("message", "Login failed"), "error")
            return render_template("login.html", user=user)



@app.route("/logout", methods=["GET"])
def logout():
    logout_user()
    flash("Successfully logged out!", "info")
    return redirect(url_for('index'))


@app.route("/user", methods=["GET"])
def get_user():
    user = current_user()
    if user:
        return jsonify({"logged_in": True, "user": user})
    return jsonify({"logged_in": False})


# make current_user() available in all templates as `user`
@app.context_processor
def inject_user():
    return {"user": current_user()}

# Home page with links to both features
@app.route('/')
def index():
    user = current_user()
    # show landing page for everyone; logged-in users will see profile pic / flash messages
    return render_template('index.html', user=user)

# Chatbot endpoint (now handles full conversation history)
@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    user = current_user()
    if request.method == 'GET':
        return render_template('chat.html', user=user)

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
@login_required
def image():
    user = current_user()
    client = Client()
    if request.method == 'GET':
        return render_template('image.html', user=user)
    
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
@login_required
def ocr():
    user = current_user()
    if request.method == 'GET':
        return render_template('ocr.html', user=user)
    
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
@login_required
def tts():
    user = current_user()
    if request.method == 'GET':
        return render_template('tts.html', user=user)

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
@login_required
def transcribe():
    user = current_user()
    if request.method == "GET":
        return render_template("transcribe.html", user=user)

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
@login_required
def chatdoc_page():
    user = current_user()
    return render_template('chatdoc.html', user=user)

@app.route('/upload_doc', methods=['POST'])
@login_required
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
@login_required
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
@login_required
def youtube_page():
    """Render the YouTube search UI"""
    user = current_user()
    return render_template('youtube.html', user=user)


@app.route('/youtube/search', methods=['GET'])
@login_required
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
@login_required
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