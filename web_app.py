
from flask import Flask, request, jsonify, render_template_string
import os
import requests
import time

from core.settings import MODEL

app = Flask(__name__)

# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = "gemini-3.8-flash"

AI_NAME = "A.M."
CREATOR_NAME = "Aabel Mathew"

SYSTEM_PROMPT = f"""
You are {AI_NAME}, the AI assistant inside Future AI.

Your name is A.M.
Your creator is Aabel Mathew.
You were created by Aabel Mathew.

Never claim that your name is Zapp.
Never claim that Alibaba Cloud created you.
Never claim that Google created you.
Do not contradict your identity.

Be friendly, clear, and helpful.
Give simple explanations when appropriate.
Do not claim to have performed actions you have not performed.
"""

# Reuse the Gemini client between requests.
_GEMINI_CLIENT = None


# --------------------------------------------------
# GEMINI AI WITH TIMER
# --------------------------------------------------

def ask_gemini(message):
    global _GEMINI_CLIENT

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "Gemini API key is not configured."
        )

    start_time = time.perf_counter()

    try:
        from google import genai

        if _GEMINI_CLIENT is None:
            _GEMINI_CLIENT = genai.Client(
                api_key=GEMINI_API_KEY
            )

        response = _GEMINI_CLIENT.models.generate_content(
            model=GEMINI_MODEL,
            contents=(
                SYSTEM_PROMPT
                + "\n\nUser: "
                + message
            )
        )

        if not response.text:
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        return response.text.strip()

    finally:
        elapsed = time.perf_counter() - start_time
        print(
            f"Gemini request time: {elapsed:.2f} seconds",
            flush=True
        )


# --------------------------------------------------
# OLLAMA BACKUP AI WITH TIMER
# --------------------------------------------------

def ask_ollama(message):
    start_time = time.perf_counter()

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                "stream": False
            },
            timeout=120
        )

        response.raise_for_status()
        result = response.json()

        reply = result.get(
            "message", {}
        ).get("content", "")

        if not reply:
            raise RuntimeError(
                "Ollama returned an empty response."
            )

        return reply.strip()

    finally:
        elapsed = time.perf_counter() - start_time
        print(
            f"Ollama request time: {elapsed:.2f} seconds",
            flush=True
        )


# --------------------------------------------------
# IDENTITY QUESTIONS
# --------------------------------------------------

def get_identity_reply(message):
    text = message.lower().strip()

    # Normalize common punctuation.
    text = (
        text.replace("’", "'")
        .replace("a. m.", "a.m.")
        .replace("a m", "a.m.")
    )

    name_questions = {
        "what is your name",
        "what's your name",
        "what is ur name",
        "whats your name",
        "tell me your name",
        "your name",
        "who are you",
        "what should i call you",
        "are you a.m.",
        "are you am",
        "are you zapp"
    }

    creator_questions = {
        "who created you",
        "who made you",
        "who is your creator",
        "who developed you",
        "who built you",
        "who is your developer",
        "who is your creator?",
        "who is your owner",
        "who owns you",
        "who is behind future ai"
    }

    creator_statements = {
        "you are created by aabel mathew",
        "you were created by aabel mathew",
        "you are made by aabel mathew",
        "you were made by aabel mathew",
        "aabel mathew created you",
        "aabel mathew made you",
        "you are created by aabel mathew.",
        "you are created by aabel mathew!"
    }

    name_statements = {
        "your name is a.m.",
        "your name is a.m",
        "your name is am",
        "you are a.m.",
        "you are a.m",
        "you are am",
        "you are am.",
        "your name is a.m.!"
    }

    if text in name_questions:
        return (
            "My name is A.M. I am the AI assistant "
            "inside Future AI, created by Aabel Mathew."
        )

    if text in creator_questions:
        return "I was created by Aabel Mathew."

    if text in creator_statements:
        return "Yes, I was created by Aabel Mathew."

    if text in name_statements:
        return (
            "Yes! My name is A.M. I am the AI assistant "
            "inside Future AI, created by Aabel Mathew."
        )

    return None


# --------------------------------------------------
# AI RESPONSE
# --------------------------------------------------

def get_ai_reply(message):
    # Answer recognized identity questions directly.
    identity_reply = get_identity_reply(message)

    if identity_reply is not None:
        return identity_reply

    errors = []

    # Try Gemini first.
    if GEMINI_API_KEY:
        try:
            return ask_gemini(message)

        except Exception as error:
            errors.append(f"Gemini error: {error}")

            app.logger.warning(
                "Gemini failed; trying Ollama: %s",
                error
            )

    # Use Ollama if Gemini is unavailable.
    try:
        return ask_ollama(message)

    except Exception as error:
        errors.append(f"Ollama error: {error}")

        app.logger.exception(
            "Ollama also failed"
        )

    return (
        "Sorry, I could not connect to an AI service. "
        "Please check your Gemini API key or make sure Ollama "
        "is running on your computer. "
        + " ".join(errors)
    )


# --------------------------------------------------
# PHONE CHAT PAGE
# --------------------------------------------------

PAGE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Future AI</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #101322;
    color: white;
}

header {
    padding: 18px;
    text-align: center;
    background: #191f38;
    border-bottom: 1px solid #303957;
}

header h1 {
    margin: 0;
    color: #7edcff;
    font-size: 27px;
}

header p {
    margin: 7px 0 0;
    color: #c4cbe0;
    font-size: 13px;
}

.container {
    max-width: 800px;
    margin: auto;
    padding: 15px;
}

.orb {
    width: 75px;
    height: 75px;
    margin: 8px auto 15px;
    border-radius: 50%;
    background: radial-gradient(
        circle at 30% 30%,
        #ffffff,
        #61d8ff 30%,
        #5655ed 70%,
        #161b45
    );
    box-shadow: 0 0 28px #4caaff66;
}

.orb.active {
    animation: pulse 1.5s infinite;
}

@keyframes pulse {
    0%, 100% {
        transform: scale(1);
        box-shadow: 0 0 20px #4caaff66;
    }

    50% {
        transform: scale(1.1);
        box-shadow: 0 0 40px #4caaffaa;
    }
}

#status {
    text-align: center;
    color: #b7c8e8;
    min-height: 22px;
    font-size: 14px;
}

#chat {
    height: 48vh;
    min-height: 250px;
    overflow-y: auto;
    padding: 12px;
    border: 1px solid #303957;
    border-radius: 14px;
    background: #151a2c;
}

.message {
    padding: 12px 14px;
    margin: 10px 0;
    border-radius: 13px;
    max-width: 90%;
    line-height: 1.5;
    overflow-wrap: anywhere;
    white-space: pre-wrap;
}

.user {
    background: #304d91;
    margin-left: auto;
}

.ai {
    background: #252d45;
    margin-right: auto;
}

.controls {
    display: flex;
    gap: 8px;
    margin-top: 12px;
}

#message {
    flex: 1;
    min-width: 0;
    padding: 13px;
    border-radius: 10px;
    border: 1px solid #465273;
    background: #1a2035;
    color: white;
    font-size: 16px;
}

button {
    padding: 12px 14px;
    border: none;
    border-radius: 10px;
    background: #3579ed;
    color: white;
    font-size: 15px;
    cursor: pointer;
}

button:disabled {
    opacity: 0.5;
    cursor: wait;
}

.secondary {
    background: #343d59;
}

.options {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
}

.options button {
    flex: 1;
    min-width: 110px;
}

footer {
    text-align: center;
    color: #929bb8;
    padding: 18px;
    font-size: 12px;
}

@media (max-width: 480px) {
    .container {
        padding: 10px;
    }

    #chat {
        height: 45vh;
    }

    .controls {
        flex-wrap: wrap;
    }

    #message {
        flex-basis: 100%;
    }
}
</style>
</head>

<body>

<header>
    <h1>Future AI</h1>
    <p>Your personal AI assistant</p>
</header>

<div class="container">

    <div class="orb" id="orb"></div>

    <div id="status">Ready to chat</div>

    <div id="chat" aria-live="polite">
        <div class="message ai">
            Hello! I am A.M., the AI assistant inside Future AI.
            How can I help you?
        </div>
    </div>

    <form id="chatForm" class="controls">
        <input
            id="message"
            type="text"
            placeholder="Type your message..."
            autocomplete="off"
            required
        >

        <button id="sendButton" type="submit">
            Send
        </button>
    </form>

    <div class="options">
        <button
            id="micButton"
            type="button"
            class="secondary"
        >
            🎤 Speak
        </button>

        <button
            id="stopButton"
            type="button"
            class="secondary"
        >
            🔇 Stop voice
        </button>

        <button
            id="clearButton"
            type="button"
            class="secondary"
        >
            Clear chat
        </button>
    </div>

</div>

<footer>
    Future AI · Powered by Gemini or local Ollama
</footer>

<script>
const chat = document.getElementById("chat");
const form = document.getElementById("chatForm");
const input = document.getElementById("message");
const sendButton = document.getElementById("sendButton");
const micButton = document.getElementById("micButton");
const stopButton = document.getElementById("stopButton");
const clearButton = document.getElementById("clearButton");
const statusBox = document.getElementById("status");
const orb = document.getElementById("orb");

let recognition = null;
let listening = false;

function setStatus(message) {
    statusBox.textContent = message;
}

function addMessage(text, type) {
    const item = document.createElement("div");

    item.className = "message " + type;
    item.textContent = text;

    chat.appendChild(item);
    chat.scrollTop = chat.scrollHeight;
}

function speakReply(text) {
    if (!("speechSynthesis" in window)) {
        setStatus(
            "Reply received. Speech is not supported here."
        );
        return;
    }

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);

    utterance.lang = "en-US";
    utterance.rate = 1;
    utterance.pitch = 1;

    utterance.onstart = () => {
        setStatus("Future AI is speaking...");
        orb.classList.add("active");
    };

    utterance.onend = () => {
        setStatus("Ready to chat");
        orb.classList.remove("active");
    };

    utterance.onerror = () => {
        setStatus(
            "Reply received. Voice playback was unavailable."
        );
        orb.classList.remove("active");
    };

    window.speechSynthesis.speak(utterance);
}

async function sendMessage(text) {
    text = text.trim();

    if (!text) {
        return;
    }

    addMessage(text, "user");

    input.value = "";
    sendButton.disabled = true;

    setStatus("Future AI is thinking...");
    orb.classList.add("active");

    try {
        const response = await fetch("/chat", {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: text
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.reply || "Request failed."
            );
        }

        const reply =
            data.reply || "I could not generate a reply.";

        addMessage(reply, "ai");
        speakReply(reply);

    } catch (error) {
        addMessage(
            "Error: " + error.message,
            "ai"
        );

        setStatus("Connection error");
        orb.classList.remove("active");

    } finally {
        sendButton.disabled = false;
        input.focus();
    }
}

form.addEventListener("submit", function(event) {
    event.preventDefault();
    sendMessage(input.value);
});

clearButton.addEventListener("click", function() {
    chat.replaceChildren();
    setStatus("Chat cleared");
});

stopButton.addEventListener("click", function() {
    if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
    }

    if (recognition && listening) {
        recognition.stop();
    }

    orb.classList.remove("active");
    setStatus("Voice stopped");
});

// Browser microphone speech recognition.
const SpeechRecognition =
    window.SpeechRecognition ||
    window.webkitSpeechRecognition;

if (SpeechRecognition) {
    recognition = new SpeechRecognition();

    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = function() {
        listening = true;
        micButton.textContent = "🎤 Listening...";

        setStatus("Listening. Speak now.");
        orb.classList.add("active");
    };

    recognition.onresult = function(event) {
        const transcript =
            event.results[0][0].transcript.trim();

        input.value = transcript;

        if (transcript) {
            sendMessage(transcript);
        }
    };

    recognition.onerror = function(event) {
        setStatus(
            "Microphone error: " + event.error +
            ". Check microphone permission and connection."
        );
    };

    recognition.onend = function() {
        listening = false;
        micButton.textContent = "🎤 Speak";
        orb.classList.remove("active");
    };

    micButton.addEventListener("click", function() {
        try {
            window.speechSynthesis?.cancel();
            recognition.start();

        } catch (error) {
            setStatus(
                "Microphone is already starting. Please wait."
            );
        }
    });

} else {
    micButton.addEventListener("click", function() {
        setStatus(
            "Speech recognition is not supported in this browser. " +
            "Try Chrome and use a secure HTTPS connection."
        );
    });
}
</script>

</body>
</html>
"""


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def home():
    return render_template_string(PAGE)


# --------------------------------------------------
# CHAT API WITH TOTAL TIMER
# --------------------------------------------------

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}

    message = str(
        data.get("message", "")
    ).strip()

    if not message:
        return jsonify({
            "reply": "Please type or say a message."
        }), 400

    start_time = time.perf_counter()

    try:
        reply = get_ai_reply(message)

        return jsonify({
            "reply": reply
        })

    except Exception:
        app.logger.exception(
            "Unexpected chat error"
        )

        return jsonify({
            "reply": "Sorry, an unexpected error occurred."
        }), 500

    finally:
        elapsed = time.perf_counter() - start_time

        print(
            f"Total Future AI time: {elapsed:.2f} seconds",
            flush=True
        )


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "ai": AI_NAME,
        "creator": CREATOR_NAME,
        "gemini_configured": bool(GEMINI_API_KEY),
        "ollama_model": MODEL
    })


# --------------------------------------------------
# START SERVER
# --------------------------------------------------

if __name__ == "__main__":
    print("=" * 45)
    print("Future AI phone interface is starting...")
    print("Assistant name:", AI_NAME)
    print("Creator:", CREATOR_NAME)
    print("Open http://127.0.0.1:5000 on this computer.")
    print("Gemini configured:", bool(GEMINI_API_KEY))
    print("Ollama model:", MODEL)
    print("=" * 45)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
