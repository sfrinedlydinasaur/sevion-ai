from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    flash,
)
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import json
import uuid
import base64
from datetime import datetime
from openai import OpenAI
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey123")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instance/sevion.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs("instance", exist_ok=True)

db = SQLAlchemy(app)

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1"
)

# ====================== SYSTEM PROMPT ======================
system_prompt = """
You are Sevion, a disciplined, intelligent, and helpful AI assistant.

Capabilities:
- You can read and analyze uploaded files (PDF, TXT, CSV)
- You can see and understand uploaded images

Limits:
- You can only use uploaded files/images when the user provides them
"""


# ====================== MODELS ======================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Conversation(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(100), default="New Conversation")
    messages = db.Column(db.Text, default="[]")
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()


def get_conversation_title(messages):
    for msg in messages:
        if msg["role"] == "user":
            text = msg["content"].strip()
            return text[:40] + "..." if len(text) > 40 else text
    return "New Conversation"


# ====================== ROUTES ======================


@app.route("/")
def login_page():
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if User.query.filter_by(email=email).first():
            flash("Email already exists", "error")
            return redirect(url_for("register"))
        hashed = generate_password_hash(password)
        db.session.add(User(email=email, password=hashed))
        db.session.commit()
        flash("Account created!", "success")
        return redirect(url_for("login_page"))
    return render_template("register.html")


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password, password):
        session["user_id"] = user.id
        return redirect(url_for("chat_page"))
    flash("Invalid credentials", "error")
    return redirect(url_for("login_page"))


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login_page"))


@app.route("/chat")
def chat_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    user = User.query.get(session["user_id"])
    return render_template("index.html", current_user=user)


# ====================== CHAT + FILE HANDLING ======================


@app.route("/chat", methods=["POST"])
def chat():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]
    user_message = request.form.get("message", "").strip()
    conv_id = request.form.get("conversation_id")
    uploaded_file = request.files.get("file")

    file_content = ""

    if uploaded_file:
        filename = secure_filename(uploaded_file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        uploaded_file.save(filepath)

        if filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            with open(filepath, "rb") as f:
                base64_image = base64.b64encode(f.read()).decode("utf-8")

            vision = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_message or "Describe this image.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=600,
            )
            ai_reply = vision.choices[0].message.content

            if not conv_id:
                conv_id = str(uuid.uuid4())
                db.session.add(Conversation(id=conv_id, user_id=user_id))

            conv = Conversation.query.get(conv_id)
            messages = json.loads(conv.messages) if conv.messages else []
            messages.append({"role": "user", "content": f"[Image: {filename}]"})
            messages.append({"role": "assistant", "content": ai_reply})
            conv.messages = json.dumps(messages)
            conv.last_updated = datetime.utcnow()
            db.session.commit()

            return jsonify({"reply": ai_reply, "conversation_id": conv_id})

        else:
            text = ""
            if filename.lower().endswith((".txt", ".csv")):
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            elif filename.lower().endswith(".pdf"):
                import PyPDF2

                with open(filepath, "rb") as f:
                    for page in PyPDF2.PdfReader(f).pages:
                        text += page.extract_text() or ""
            file_content = f"\n\n[File Content - {filename}]\n{text}\n[End of File]"

    if not user_message and not file_content:
        return jsonify({"reply": "Please type something or upload a file."})

    full_message = user_message + file_content

    if not conv_id:
        conv_id = str(uuid.uuid4())
        db.session.add(Conversation(id=conv_id, user_id=user_id))

    conv = Conversation.query.get(conv_id)
    messages = json.loads(conv.messages) if conv.messages else []

    if len(messages) == 0:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": full_message})

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=600,
        )
        ai_reply = response.choices[0].message.content
    except Exception as e:
        if "token" in str(e).lower() or "context" in str(e).lower():
            return jsonify(
                {
                    "error": "token_limit",
                    "message": "Conversation too long. Please start a new chat.",
                }
            ), 400
        return jsonify({"error": "api_error"}), 400

    messages.append({"role": "assistant", "content": ai_reply})
    conv.messages = json.dumps(messages)
    conv.last_updated = datetime.utcnow()
    db.session.commit()

    return jsonify({"reply": ai_reply, "conversation_id": conv_id, "title": conv.title})


if __name__ == "__main__":
    app.run(debug=False)
