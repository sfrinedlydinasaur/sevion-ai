# Sevion AI

A full-stack AI chatbot built with Flask and a modern Tailwind frontend.  
Sevion supports persistent conversations, file & image uploads, and a clean, responsive UI.

## Features

- User authentication (Register / Login / Logout)
- Persistent chat history (stored in SQLite per user)
- Rename and delete conversations
- File upload support (PDF, TXT, CSV)
- Image upload with vision (GPT-4o)
- Modern UI with sidebar, collapse, mobile menu, and typing indicator
- Clean dark theme with custom frozen-style logo

## Tech Stack

- **Backend**: Flask + SQLAlchemy
- **Frontend**: Tailwind CSS + Vanilla JavaScript
- **Database**: SQLite
- **AI**: Groq (Llama 3.3 70B) + OpenAI (for vision)
- **Deployment**: Render

## Project Structure
sevion-ai/
├── sevion_web.py          # Main Flask application
├── templates/
│   ├── index.html         # Main chat interface
│   ├── login.html
│   └── register.html
├── uploads/               # Uploaded files
├── .env                   # Environment variables (not committed)
├── requirements.txt
└── README.md

Live Demo
Test the deployed version here:
https://sevion-ai.onrender.com
Future Improvements

Better mobile experience
Voice input
More file type support
Conversation search

Author
Built by Sean as a learning project to deeply understand full-stack development and AI integration.
