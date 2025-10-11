# Advanced Multimodal AI

A powerful web application that combines multiple AI capabilities including chat, image generation, and OCR (Optical Character Recognition) in one unified platform.

## 🌟 Features

- **💬 AI Chat Interface**
  - Real-time conversation with advanced language models
  - Full conversation history support
  - Clean and responsive chat UI

- **🎨 Image Generation**
  - Generate images from text descriptions
  - Powered by state-of-the-art image generation models
  - Real-time preview and generation

- **📄 OCR (Optical Character Recognition)**
  - Extract text from images
  - Support for multiple image uploads
  - Drag and drop interface
  - Preview uploaded images
  - Real-time text extraction

## 🚀 Technologies Used

- **Backend**
  - Python 3.x
  - Flask
  - OpenRouter AI API
  - G4F Client

- **Frontend**
  - HTML5
  - CSS3
  - JavaScript
  - Responsive Design

## 📋 Prerequisites

- Python 3.x
- pip (Python package manager)
- OpenRouter API key

## ⚙️ Installation

1. Clone the repository
```bash
git clone https://github.com/Vishal2053/Multimodal-AI.git
cd Multimodal-AI
```

2. Install required dependencies
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root and add your API key
```env
OPENROUTER_API_KEY=your_api_key_here
SITE_URL=your_site_url
SITE_NAME=your_site_name
```

4. Run the application
```bash
python app.py
```

## 📁 Project Structure

```
multimodal/
├── app.py              # Main Flask application
├── static/
│   └── style.css      # Global styles
├── templates/
│   ├── layout.html    # Base template
│   ├── index.html     # Home page
│   ├── chat.html      # Chat interface
│   ├── image.html     # Image generation
│   └── ocr.html       # OCR interface
├── uploads/           # Temporary file storage
└── .env              # Environment variables
```

## 🖥️ Usage

1. Start the server:
   - Run `python app.py`
   - Access the application at `http://localhost:5000`

2. Available endpoints:
   - `/` - Home page
   - `/chat` - Chat interface
   - `/image` - Image generation
   - `/ocr` - OCR text extraction

## 🛠️ API Integration

The application integrates with the OpenRouter AI API for:
- Text generation (Chat)
- Image generation
- OCR processing

## 🎨 UI Features

- Responsive design
- Dark mode interface
- Animated transitions
- Interactive elements
- Modern gradient styling
- Professional typography

## 🔒 Security

- Secure file handling
- Environment variable protection
- File size limitations
- Temporary file cleanup
- Secure API communication

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Important Notes

- Ensure your OpenRouter API key is kept secure
- Maximum file upload size is 16MB
- Supported image formats: JPEG, PNG, GIF
- Temporary files are automatically cleaned up after processing

## 📧 Contact

For any queries or support, please create an issue in the repository.

---
Built with ❤️ using Flask and OpenRouter AI