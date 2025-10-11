from flask import Flask, render_template, request, jsonify
from g4f.client import Client
import requests
import json
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import base64  # Ensure this import is present

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Create g4f client once (global for reuse)
client = Client()

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
        # Try to get JSON data, fallback to form data
        data = request.get_json(silent=True)
        if data is None:
            data = request.form.to_dict()
        
        messages = data.get('messages')
        print(messages)  # Debugging line to check incoming messages
        
        if not messages:
            # Fallback to single message for simple forms
            single_message = data.get('message') or data.get('prompt')
            if single_message:
                messages = [{"role": "user", "content": single_message}]
            else:
                return jsonify({'error': 'No messages or message provided'}), 400
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                web_search=False
            )
            print(response)  # Debugging line to check the response
            bot_response = response.choices[0].message.content.strip()
            return jsonify({'response': bot_response})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

# Image generation endpoint
@app.route('/image', methods=['GET', 'POST'])
def image():
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
        # Check if images were uploaded
        if 'images' not in request.files:
            return jsonify({'error': 'No image files provided'}), 400
        
        files = request.files.getlist('images')
        if not files:
            return jsonify({'error': 'No selected files'}), 400
        
        results = []
        for file in files:
            if file:
                # Save the uploaded file
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                # Process the image with the OpenRouter API
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
                                            "text": "Please extract and read all text from this image."
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
                    
                    result = response.json()
                    extracted_text = result['choices'][0]['message']['content']
                    results.append({'filename': filename, 'text': extracted_text})

                except Exception as e:
                    return jsonify({'error': str(e)}), 500

                # Clean up uploaded file
                os.remove(filepath)

        return jsonify({'results': results})

if __name__ == '__main__':
    app.run(debug=True)