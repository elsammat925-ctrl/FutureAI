from flask import Flask, request, jsonify, render_template_string
import os
import json
import requests
import time

from core.settings import MODEL

app = Flask(__name__)

# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = "gemini-3.5-flash-lite"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.environ.get(
    "SUPABASE_PUBLISHABLE_KEY", ""
).strip()

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

_GEMINI_CLIENT = None


# --------------------------------------------------
# SUPABASE AUTHENTICATION
# --------------------------------------------------

def get_authenticated_user():
    """Verify the signed-in user's access token with Supabase."""

    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
        return None, (
            "Authentication is not configured on the server.",
            503
        )

    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return None, ("Please sign in to continue.", 401)

    token = auth_header.split(" ", 1)[1].strip()

    if not token:
        return None, ("Please sign in to continue.", 401)

    try:
        response = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {token}"
            },
            timeout=10
        )
    except requests.RequestException:
        app.logger.exception("Could not verify Supabase session")
        return None, (
            "Could not verify your session. Please try again.",
            503
        )

    if response.status_code != 200:
        return None, (
            "Your session has expired. Please sign in again.",
            401
        )

    try:
        user = response.json()
    except ValueError:
        return None, (
            "Could not verify your session. Please sign in again.",
            401
        )

    if not isinstance(user, dict) or not user.get("id"):
        return None, ("Could not verify your session.", 401)

    return user, None


# --------------------------------------------------
# GEMINI AI
# --------------------------------------------------

def ask_gemini(message):
    global _GEMINI_CLIENT

    if not GEMINI_API_KEY:
        raise RuntimeError("Gemini API key is not configured.")

    start_time = time.perf_counter()

    try:
        from google import genai

        if _GEMINI_CLIENT is None:
            _GEMINI_CLIENT = genai.Client(
                api_key=GEMINI_API_KEY
            )

        response = _GEMINI_CLIENT.models.generate_content(
            model=GEMINI_MODEL,
            contents=SYSTEM_PROMPT + "\n\nUser: " + message
        )

        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")

        return response.text.strip()

    finally:
        print(
            f"Gemini request time: "
            f"{time.perf_counter() - start_time:.2f} seconds",
            flush=True
        )


# --------------------------------------------------
# OLLAMA BACKUP
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

        reply = response.json().get(
            "message", {}
        ).get("content", "")

        if not reply:
            raise RuntimeError("Ollama returned an empty response.")

        return reply.strip()

    finally:
        print(
            f"Ollama request time: "
            f"{time.perf_counter() - start_time:.2f} seconds",
            flush=True
        )


# --------------------------------------------------
# IDENTITY QUESTIONS
# --------------------------------------------------

def get_identity_reply(message):
    text = message.lower().strip()
    text = (
        text.replace("’", "'")
        .replace("a. m.", "a.m.")
        .replace("a m", "a.m.")
    )

    name_questions = {
        "what is your name", "what's your name",
        "what is ur name", "whats your name",
        "tell me your name", "your name", "who are you",
        "what should i call you", "are you a.m.",
        "are you am", "are you zapp"
    }

    creator_questions = {
        "who created you", "who made you",
        "who is your creator", "who developed you",
        "who built you", "who is your developer",
        "who is your creator?", "who is your owner",
        "who owns you", "who is behind future ai"
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
        "your name is a.m.", "your name is a.m",
        "your name is am", "you are a.m.",
        "you are a.m", "you are am",
        "you are am.", "your name is a.m.!"
    }

    if text in name_questions:
        return (
            "My name is A.M. I am the AI assistant inside "
            "Future AI, created by Aabel Mathew."
        )

    if text in creator_questions:
        return "I was created by Aabel Mathew."

    if text in creator_statements:
        return "Yes, I was created by Aabel Mathew."

    if text in name_statements:
        return (
            "Yes! My name is A.M. I am the AI assistant inside "
            "Future AI, created by Aabel Mathew."
        )

    return None


# --------------------------------------------------
# AI RESPONSE
# --------------------------------------------------

def get_ai_reply(message):
    identity_reply = get_identity_reply(message)

    if identity_reply is not None:
        return identity_reply

    errors = []

    if GEMINI_API_KEY:
        try:
            return ask_gemini(message)
        except Exception as error:
            errors.append(f"Gemini error: {error}")
            app.logger.warning(
                "Gemini failed; trying Ollama: %s", error
            )

    try:
        return ask_ollama(message)
    except Exception as error:
        errors.append(f"Ollama error: {error}")
        app.logger.exception("Ollama also failed")

    return (
        "Sorry, I could not connect to an AI service. "
        "Please check your Gemini API key or make sure "
        "Ollama is running on your computer. "
        + " ".join(errors)
    )


# --------------------------------------------------
# COMPLETE MOBILE INTERFACE
# --------------------------------------------------

PAGE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#ffffff">
<title>A.M. — Future AI</title>

<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>

<style>
* { box-sizing: border-box; }

:root {
    --blue: #4169ed;
    --text: #171717;
    --muted: #777;
    --border: #e8e8ed;
    --panel: #f7f7f9;
}

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: white;
    color: var(--text);
}

button, input, select { font: inherit; }
button { cursor: pointer; -webkit-tap-highlight-color: transparent; }
button:disabled { opacity: .5; cursor: wait; }

.screen { display: none; min-height: 100dvh; }
.screen.active { display: flex; }

.icon-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 54px;
    height: 54px;
    border: 0;
    border-radius: 50%;
    background: #fff;
    color: #111;
    box-shadow: 0 2px 12px #00000008;
    font-size: 27px;
}

.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 22px;
}

.brand { font-size: 20px; font-weight: 700; }
.subtle { color: var(--muted); font-size: 13px; }

#authScreen {
    align-items: center;
    justify-content: center;
    padding: 24px;
    background: #f7f8fc;
}

.auth-card {
    width: 100%;
    max-width: 420px;
    padding: 28px;
    border: 1px solid var(--border);
    border-radius: 22px;
    background: white;
    box-shadow: 0 10px 35px #0000000a;
}

.auth-card .brand { margin-bottom: 28px; }
.auth-card h1 { margin: 0 0 10px; font-size: 27px; }
.auth-card p { line-height: 1.5; color: #666; }

.auth-card label {
    display: block;
    margin: 18px 0 7px;
    font-size: 14px;
    font-weight: 600;
}

.auth-input {
    display: block;
    width: 100%;
    padding: 14px;
    border: 1px solid #dcdde5;
    border-radius: 12px;
    background: white;
    color: #171717;
    outline-color: var(--blue);
}

.auth-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }

.auth-button {
    flex: 1;
    min-width: 120px;
    padding: 13px 15px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: white;
    color: #171717;
}

.auth-button.primary { background: #171717; color: white; }
.auth-message { min-height: 20px; overflow-wrap: anywhere; }
.auth-note { font-size: 12px; }

#chatScreen { flex-direction: column; }
.chat-layout { display: flex; flex: 1; min-height: 0; }

.sidebar {
    display: none;
    width: min(320px, 85vw);
    flex-shrink: 0;
    flex-direction: column;
    padding: 16px;
    background: #f7f7f9;
    border-right: 1px solid var(--border);
    overflow-y: auto;
}

.sidebar.open { display: flex; }

.new-chat {
    padding: 13px;
    border: 1px solid var(--border);
    border-radius: 15px;
    background: white;
    text-align: left;
}

.history-heading { margin: 24px 0 10px; font-size: 13px; color: var(--muted); }

.history-item {
    display: block;
    width: 100%;
    padding: 12px;
    margin: 3px 0;
    border: 0;
    border-radius: 10px;
    background: transparent;
    text-align: left;
    overflow-wrap: anywhere;
}

.history-item.selected, .history-item:hover { background: #e9eaf0; }

.chat-main {
    display: flex;
    flex: 1;
    min-width: 0;
    flex-direction: column;
    width: 100%;
}

.chat-messages {
    flex: 1;
    width: 100%;
    max-width: 820px;
    margin: 0 auto;
    padding: 18px 18px 24px;
    overflow-y: auto;
}

.message {
    width: fit-content;
    max-width: 90%;
    margin: 12px 0;
    padding: 12px 15px;
    border-radius: 18px;
    line-height: 1.55;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}

.message.user { margin-left: auto; background: #e9efff; }
.message.ai { margin-right: auto; background: #f5f5f7; }

.chat-welcome { margin: auto; padding: 25px; text-align: center; }
.chat-welcome h1 { font-size: clamp(25px, 5vw, 38px); font-weight: 500; }

.composer {
    display: flex;
    align-items: center;
    gap: 9px;
    width: 100%;
    max-width: 820px;
    margin: 0 auto;
    padding: 12px 16px max(18px, env(safe-area-inset-bottom));
    background: white;
}

.composer input {
    flex: 1;
    min-width: 0;
    padding: 15px;
    border: 1px solid var(--border);
    border-radius: 25px;
    outline: none;
    background: #f7f7f8;
}

.round-button {
    width: 48px;
    height: 48px;
    flex-shrink: 0;
    border: 0;
    border-radius: 50%;
    background: #f1f1f3;
    color: #171717;
    font-size: 21px;
}

.send-button { background: #171717; color: white; }

.main-actions {
    display: flex;
    justify-content: center;
    gap: 12px;
    flex-wrap: wrap;
    padding: 0 16px 16px;
}

.action-button {
    padding: 12px 18px;
    border: 1px solid var(--border);
    border-radius: 24px;
    background: white;
}

.action-button.primary { background: #171717; color: white; border-color: #171717; }

#voiceScreen {
    position: relative;
    flex-direction: column;
    height: 100dvh;
    min-height: 100dvh;
    overflow: hidden;
    background: radial-gradient(ellipse at 50% 55%, #fff 25%, #fbfbfd 72%, #f5f5f7 100%);
}

.voice-topbar {
    position: relative;
    z-index: 2;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: max(20px, env(safe-area-inset-top)) 26px 12px;
}

.voice-orb-area {
    display: flex;
    flex: 1;
    min-height: 0;
    align-items: center;
    justify-content: center;
    padding: 12px;
}

.voice-orb {
    position: relative;
    width: min(60vw, 420px);
    aspect-ratio: 1;
    max-height: 43dvh;
    border-radius: 50%;
    overflow: hidden;
    background:
        radial-gradient(ellipse at 50% 70%, #dce7ff 0%, transparent 50%),
        radial-gradient(ellipse at 25% 20%, #7ba2ff 0%, transparent 43%),
        radial-gradient(ellipse at 76% 28%, #3565e9 0%, transparent 48%),
        linear-gradient(150deg, #4778f1, #9bb7ff 70%, #d9e5ff);
    box-shadow: inset -10px -16px 35px #4568d033;
    transition: transform .3s ease;
}

.voice-orb::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: radial-gradient(ellipse at 48% 63%, #fff 0%, #ffffffdd 8%, #e6edffbb 25%, transparent 49%);
    filter: blur(8px);
    transform: translateY(7%);
}

.voice-orb::after {
    content: "";
    position: absolute;
    width: 70%;
    height: 34%;
    left: 12%;
    top: 13%;
    border-radius: 50%;
    background: #ffffff22;
    filter: blur(22px);
    transform: rotate(-28deg);
}

.voice-orb.listening { animation: breathe 2.5s ease-in-out infinite; }
.voice-orb.speaking { animation: speak-pulse 1s ease-in-out infinite; }

@keyframes breathe { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.035); } }
@keyframes speak-pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.065); } }

.voice-status {
    position: absolute;
    left: 15px;
    right: 15px;
    bottom: 115px;
    min-height: 24px;
    text-align: center;
    color: #777;
    font-size: 14px;
}

.voice-bottom {
    position: relative;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 12px 22px max(22px, env(safe-area-inset-bottom));
}

.voice-input {
    display: flex;
    flex: 1;
    align-items: center;
    gap: 12px;
    max-width: 440px;
    min-width: 0;
    padding: 7px 14px;
    border: 1px solid #eeeeef;
    border-radius: 32px;
    background: white;
}

.voice-input input { width: 100%; min-width: 0; padding: 10px 0; border: 0; outline: none; background: transparent; font-size: 16px; }
.voice-input button { flex-shrink: 0; border: 0; background: transparent; font-size: 25px; }

.mic-toggle, .exit-button {
    width: 60px;
    height: 60px;
    flex-shrink: 0;
    border: 0;
    border-radius: 50%;
    font-size: 24px;
}

.mic-toggle { background: #f0f0f2; color: #171717; }
.exit-button { background: #050505; color: white; font-size: 30px; }

.panel {
    position: fixed;
    z-index: 20;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(350px, 90vw);
    padding: 22px;
    overflow-y: auto;
    background: white;
    box-shadow: -8px 0 35px #00000018;
    transform: translateX(110%);
    transition: transform .2s ease;
}

.panel.open { transform: translateX(0); }
.panel h2 { margin-top: 12px; }
.panel button, .panel select { max-width: 100%; }
.panel select { width: 100%; margin: 10px 0 18px; padding: 12px; border: 1px solid var(--border); border-radius: 12px; background: white; }

.modal-backdrop {
    position: fixed;
    z-index: 40;
    inset: 0;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 22px;
    background: #00000066;
}

.modal-backdrop.open { display: flex; }
.modal { width: 100%; max-width: 390px; padding: 24px; border-radius: 22px; background: white; box-shadow: 0 12px 45px #00000022; }
.modal h2 { margin-top: 0; }
.modal p { color: #555; line-height: 1.5; }
.modal-actions { display: flex; flex-wrap: wrap; gap: 9px; margin-top: 22px; }
.modal-actions button { flex: 1; min-width: 115px; padding: 12px; border: 0; border-radius: 12px; }
.save-button { background: #171717; color: white; }
.cancel-button { background: #ededf0; color: #171717; }

@media (max-width: 500px) {
    .topbar { padding: 18px 22px; }
    .chat-messages { padding: 12px; }
    .voice-orb { width: min(60vw, 420px); max-height: 36dvh; }
    .voice-bottom { gap: 9px; padding-left: 14px; padding-right: 14px; }
    .mic-toggle, .exit-button { width: 56px; height: 56px; }
    .voice-status { bottom: 100px; }
    .auth-card { padding: 23px; }
}
</style>
</head>

<body>

<!-- SIGN IN / CREATE ACCOUNT -->

<section id="authScreen" class="screen active">
    <div class="auth-card">
        <div class="brand">A.M. — Future AI</div>
        <h1 id="authHeading">Sign in to A.M.</h1>
        <p id="authDescription">Sign in or create an account to continue.</p>

        <form id="authForm">
            <label for="authEmail">Email</label>
            <input class="auth-input" id="authEmail" type="email"
                   required autocomplete="email">

            <label for="authPassword">Password</label>
            <input class="auth-input" id="authPassword" type="password"
                   required minlength="6" autocomplete="current-password">

            <div class="auth-actions">
                <button id="loginButton" type="submit"
                        class="auth-button primary">Sign in</button>
                <button id="signupButton" type="button"
                        class="auth-button">Create account</button>
            </div>
        </form>

        <p id="authMessage" class="auth-message" role="status"></p>
        <p class="auth-note">If email confirmation is enabled, check your inbox after signing up.</p>
    </div>
</section>

<!-- NORMAL CHAT SCREEN -->

<section id="chatScreen" class="screen">
    <div class="topbar">
        <button class="icon-button" id="menuButton" aria-label="Open chat history">☰</button>
        <div class="brand">A.M.</div>
        <button class="icon-button" id="settingsButton" aria-label="Voice settings">☷</button>
    </div>

    <div class="chat-layout">
        <aside class="sidebar" id="sidebar">
            <button class="new-chat" id="newChatButton">＋ New chat</button>
            <div class="history-heading">CHAT HISTORY</div>
            <div id="historyList"></div>
        </aside>

        <main class="chat-main">
            <div class="chat-messages" id="chatMessages" aria-live="polite"></div>
            <div class="main-actions">
                <button class="action-button primary" id="startVoiceButton">🎙 Speak to A.M.</button>
                <button class="action-button" id="newChatShortcut">＋ New chat</button>
            </div>

            <form class="composer" id="chatForm">
                <input id="messageInput" placeholder="Message A.M...." autocomplete="off" required>
                <button class="round-button send-button" id="sendButton" type="submit" aria-label="Send message">↑</button>
            </form>
        </main>
    </div>
</section>

<!-- FULL-SCREEN VOICE CHAT -->

<section id="voiceScreen" class="screen">
    <div class="voice-topbar">
        <button class="icon-button" id="voiceMenuButton" aria-label="Chat history">☰</button>
        <button class="icon-button" id="voiceSettingsButton" aria-label="Voice settings">☷</button>
    </div>

    <div class="voice-orb-area">
        <div class="voice-orb" id="voiceOrb"></div>
    </div>

    <div class="voice-status" id="voiceStatus">Tap the microphone to start speaking</div>

    <div class="voice-bottom">
        <form class="voice-input" id="voiceTextForm">
            <button type="button" id="voicePlus" aria-label="Return to chat">＋</button>
            <input id="voiceTextInput" placeholder="Talk to A.M...." autocomplete="off">
        </form>
        <button class="mic-toggle" id="voiceMicButton" aria-label="Start or pause microphone">🎙</button>
        <button class="exit-button" id="exitVoiceButton" aria-label="End voice conversation">×</button>
    </div>
</section>

<!-- SETTINGS PANEL -->

<aside class="panel" id="settingsPanel">
    <button class="icon-button" id="closeSettingsButton" aria-label="Close settings">×</button>

    <h2>Voice settings</h2>
    <p class="subtle">Choose how A.M. sounds.</p>

    <label for="voiceSelect">Reply voice</label>
    <select id="voiceSelect">
        <option value="">Default browser voice</option>
    </select>

    <button class="action-button primary" id="previewVoiceButton">▶ Preview voice</button>

    <p class="subtle" style="margin-top:22px">Available voices depend on your browser and device.</p>

    <hr>
    <h2>Account</h2>
    <p class="subtle" id="signedInEmail"></p>
    <button class="action-button" id="logoutButton">Sign out</button>
</aside>

<!-- EXIT CONFIRMATION -->

<div class="modal-backdrop" id="saveModal">
    <div class="modal">
        <h2>Save voice conversation?</h2>
        <p>Would you like to add what you said and A.M.'s replies to your chat history so you can read and continue this conversation later?</p>
        <div class="modal-actions">
            <button class="save-button" id="saveVoiceButton">Yes, save</button>
            <button class="cancel-button" id="discardVoiceButton">No, don't save</button>
        </div>
    </div>
</div>

<script>
const SUPABASE_URL = __SUPABASE_URL_JSON__;
const SUPABASE_PUBLISHABLE_KEY = __SUPABASE_KEY_JSON__;

const supabaseClient = (
    SUPABASE_URL &&
    SUPABASE_PUBLISHABLE_KEY &&
    window.supabase
) ? window.supabase.createClient(
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY
) : null;

const $ = id => document.getElementById(id);

const authScreen = $("authScreen");
const authForm = $("authForm");
const authEmail = $("authEmail");
const authPassword = $("authPassword");
const authMessage = $("authMessage");
const authHeading = $("authHeading");
const authDescription = $("authDescription");
const loginButton = $("loginButton");
const signupButton = $("signupButton");
const signedInEmail = $("signedInEmail");

const chatScreen = $("chatScreen");
const voiceScreen = $("voiceScreen");
const chatMessages = $("chatMessages");
const chatForm = $("chatForm");
const messageInput = $("messageInput");
const sendButton = $("sendButton");
const historyList = $("historyList");
const sidebar = $("sidebar");
const voiceOrb = $("voiceOrb");
const voiceStatus = $("voiceStatus");
const voiceSelect = $("voiceSelect");
const settingsPanel = $("settingsPanel");
const saveModal = $("saveModal");

const STORAGE_KEY = "am_future_ai_conversations_v1";
const VOICE_KEY = "am_future_ai_selected_voice_v1";

let currentSession = null;
let conversations = loadConversations();
let activeConversationId = null;
let voiceDraft = [];
let voiceActive = false;
let microphonePaused = false;
let recognition = null;
let isSpeaking = false;
let requestInProgress = false;
let recognitionStarting = false;
let availableVoices = [];
let recognitionSupported = false;
let voiceExitPending = false;
let nextRecognitionTimer = null;


// --------------------------------------------------
// AUTHENTICATION INTERFACE
// --------------------------------------------------

function setAuthMessage(text) {
    authMessage.textContent = text || "";
}

function showAuthScreen(message = "") {
    currentSession = null;
    authScreen.classList.add("active");
    chatScreen.classList.remove("active");
    voiceScreen.classList.remove("active");
    setAuthMessage(message);
}

function showChatForSession(session) {
    if (!session) {
        showAuthScreen();
        return;
    }

    currentSession = session;
    authScreen.classList.remove("active");
    voiceScreen.classList.remove("active");
    chatScreen.classList.add("active");

    if (signedInEmail) {
        signedInEmail.textContent = session.user?.email || "";
    }

    renderChat();
    renderHistory();
}

function setAuthBusy(busy) {
    loginButton.disabled = busy;
    signupButton.disabled = busy;
}

authForm.addEventListener("submit", async event => {
    event.preventDefault();

    if (!supabaseClient) {
        setAuthMessage("Sign-in is not configured. Check the Supabase environment variables in Render.");
        return;
    }

    const email = authEmail.value.trim();
    const password = authPassword.value;

    if (!email || !password) {
        setAuthMessage("Enter your email and password.");
        return;
    }

    setAuthBusy(true);
    setAuthMessage("Signing in…");

    try {
        const { data, error } = await supabaseClient.auth.signInWithPassword({
            email,
            password
        });

        if (error) throw error;

        if (!data.session) {
            setAuthMessage("No active session was returned. Please try again.");
            return;
        }

        showChatForSession(data.session);
        setAuthMessage("");

    } catch (error) {
        setAuthMessage(error.message || "Sign-in failed.");
    } finally {
        setAuthBusy(false);
    }
});

signupButton.addEventListener("click", async () => {
    if (!supabaseClient) {
        setAuthMessage("Sign-up is not configured. Check the Supabase environment variables in Render.");
        return;
    }

    const email = authEmail.value.trim();
    const password = authPassword.value;

    if (!email || !password) {
        setAuthMessage("Enter an email address and a password.");
        return;
    }

    if (password.length < 6) {
        setAuthMessage("Your password must contain at least 6 characters.");
        return;
    }

    setAuthBusy(true);
    setAuthMessage("Creating your account…");

    try {
        const { data, error } = await supabaseClient.auth.signUp({
            email,
            password,
            options: {
                emailRedirectTo: window.location.origin + "/"
            }
        });

        if (error) throw error;

        if (data.session) {
            showChatForSession(data.session);
            setAuthMessage("");
        } else {
            setAuthMessage(
                "Account request completed. If this is a new account, check your email for a confirmation link. After confirming, return here and sign in. If the account already exists, try signing in."
            );
        }

    } catch (error) {
        setAuthMessage(error.message || "Could not create the account.");
    } finally {
        setAuthBusy(false);
    }
});


// --------------------------------------------------
// LOCAL CHAT HISTORY
// --------------------------------------------------

function makeId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 9);
}

function loadConversations() {
    try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        return Array.isArray(saved) ? saved : [];
    } catch (error) {
        return [];
    }
}

function persistConversations() {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
        return true;
    } catch (error) {
        alert("The browser could not save chat history. Check available device storage.");
        return false;
    }
}

function newConversation() {
    const conversation = {
        id: makeId(),
        title: "New chat",
        messages: [],
        updatedAt: Date.now()
    };

    conversations.unshift(conversation);
    activeConversationId = conversation.id;
    persistConversations();
    renderChat();
    renderHistory();
    sidebar.classList.remove("open");
    $("messageInput").focus();
}

function getActiveConversation() {
    return conversations.find(item => item.id === activeConversationId);
}

function ensureConversation() {
    let conversation = getActiveConversation();

    if (!conversation) {
        conversation = {
            id: makeId(),
            title: "New chat",
            messages: [],
            updatedAt: Date.now()
        };
        conversations.unshift(conversation);
        activeConversationId = conversation.id;
    }

    return conversation;
}

function addSavedMessage(role, text) {
    const conversation = ensureConversation();

    conversation.messages.push({
        role: role,
        text: text,
        time: Date.now()
    });

    if (conversation.title === "New chat" && role === "user") {
        conversation.title = text.slice(0, 42) + (text.length > 42 ? "…" : "");
    }

    conversation.updatedAt = Date.now();
    conversations.sort((a, b) => b.updatedAt - a.updatedAt);
    persistConversations();
    renderChat();
    renderHistory();
}

function openConversation(id) {
    const conversation = conversations.find(item => item.id === id);
    if (!conversation) return;

    activeConversationId = id;
    renderChat();
    renderHistory();
    sidebar.classList.remove("open");
    chatScreen.classList.add("active");
    voiceScreen.classList.remove("active");
}

function renderChat() {
    chatMessages.replaceChildren();
    const conversation = getActiveConversation();

    if (!conversation || conversation.messages.length === 0) {
        const welcome = document.createElement("div");
        welcome.className = "chat-welcome";

        const heading = document.createElement("h1");
        heading.textContent = "Hello! I'm A.M.";

        const paragraph = document.createElement("p");
        paragraph.textContent = "How can I help you today?";

        welcome.append(heading, paragraph);
        chatMessages.appendChild(welcome);
        return;
    }

    conversation.messages.forEach(message => {
        const bubble = document.createElement("div");
        bubble.className = "message " + (message.role === "user" ? "user" : "ai");
        bubble.textContent = message.text;
        chatMessages.appendChild(bubble);
    });

    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderHistory() {
    historyList.replaceChildren();

    if (conversations.length === 0) {
        const empty = document.createElement("p");
        empty.className = "subtle";
        empty.textContent = "Your saved chats will appear here.";
        historyList.appendChild(empty);
        return;
    }

    conversations.forEach(conversation => {
        const button = document.createElement("button");
        button.className = "history-item";

        if (conversation.id === activeConversationId) {
            button.classList.add("selected");
        }

        button.textContent = conversation.title || "New chat";
        button.addEventListener("click", () => openConversation(conversation.id));
        historyList.appendChild(button);
    });
}


// --------------------------------------------------
// AI CHAT REQUEST — SEND SUPABASE ACCESS TOKEN
// --------------------------------------------------

async function getReply(text) {
    if (!supabaseClient) {
        showAuthScreen("Sign-in is not configured. Check server settings.");
        throw new Error("Sign-in is not configured.");
    }

    const { data: sessionData, error: sessionError } =
        await supabaseClient.auth.getSession();

    const session = sessionData?.session;

    if (sessionError || !session?.access_token) {
        showAuthScreen("Please sign in to continue.");
        throw new Error("Please sign in to continue.");
    }

    const response = await fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
            message: text,
            language: "auto"
        })
    });

    let data = {};

    try {
        data = await response.json();
    } catch (error) {
        throw new Error("The server returned an invalid response.");
    }

    if (response.status === 401) {
        await supabaseClient.auth.signOut();
        showAuthScreen(data.reply || "Your session has expired. Please sign in again.");
        throw new Error(data.reply || "Please sign in again.");
    }

    if (!response.ok) {
        throw new Error(data.reply || "Request failed.");
    }

    return data.reply || "I could not generate a reply.";
}


// --------------------------------------------------
// NORMAL TEXT CHAT
// --------------------------------------------------

async function sendTextMessage(text) {
    text = text.trim();
    if (!text || requestInProgress) return;

    requestInProgress = true;
    sendButton.disabled = true;
    addSavedMessage("user", text);
    messageInput.value = "";

    const thinking = document.createElement("div");
    thinking.className = "message ai";
    thinking.textContent = "A.M. is thinking…";
    thinking.id = "thinkingMessage";
    chatMessages.appendChild(thinking);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const reply = await getReply(text);
        $("thinkingMessage")?.remove();
        addSavedMessage("ai", reply);
        speakReply(reply);
    } catch (error) {
        $("thinkingMessage")?.remove();
        addSavedMessage("ai", "Sorry, I could not get a reply. " + error.message);
    } finally {
        requestInProgress = false;
        sendButton.disabled = false;
    }
}

chatForm.addEventListener("submit", event => {
    event.preventDefault();
    sendTextMessage(messageInput.value);
});

$("newChatButton").addEventListener("click", newConversation);
$("newChatShortcut").addEventListener("click", newConversation);

$("menuButton").addEventListener("click", () => sidebar.classList.toggle("open"));

$("voiceMenuButton").addEventListener("click", () => {
    sidebar.classList.toggle("open");
    chatScreen.classList.add("active");
    voiceScreen.classList.remove("active");
});


// --------------------------------------------------
// BROWSER SPEECH VOICES
// --------------------------------------------------

function loadVoices() {
    if (!("speechSynthesis" in window)) {
        voiceSelect.innerHTML = '<option value="">Speech unavailable</option>';
        return;
    }

    availableVoices = speechSynthesis.getVoices();
    const savedValue = localStorage.getItem(VOICE_KEY) || "";
    voiceSelect.replaceChildren();

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "Default browser voice";
    voiceSelect.appendChild(defaultOption);

    availableVoices.forEach((voice, index) => {
        const option = document.createElement("option");
        option.value = String(index);
        option.textContent = voice.name + " (" + voice.lang + ")";
        voiceSelect.appendChild(option);
    });

    if (savedValue !== "" && Number(savedValue) < availableVoices.length) {
        voiceSelect.value = savedValue;
    }
}

if ("speechSynthesis" in window) {
    loadVoices();
    speechSynthesis.addEventListener("voiceschanged", loadVoices);
    setTimeout(loadVoices, 500);
    setTimeout(loadVoices, 1500);
}

voiceSelect.addEventListener("change", () => {
    localStorage.setItem(VOICE_KEY, voiceSelect.value);
});

function speakReply(text, forVoiceChat = false) {
    if (!("speechSynthesis" in window)) {
        if (forVoiceChat) {
            setVoiceStatus("Speech playback is not supported in this browser.");
        }
        return;
    }

    speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    const index = Number(voiceSelect.value);

    if (voiceSelect.value !== "" && availableVoices[index]) {
        utterance.voice = availableVoices[index];
        utterance.lang = utterance.voice.lang;
    } else {
        utterance.lang = "en-US";
    }

    utterance.rate = 1;
    utterance.pitch = 1;

    utterance.onstart = () => {
        isSpeaking = true;

        if (forVoiceChat) {
            voiceOrb.classList.remove("listening");
            voiceOrb.classList.add("speaking");
            setVoiceStatus("A.M. is speaking…");
        }
    };

    utterance.onend = () => {
        isSpeaking = false;
        voiceOrb.classList.remove("speaking");

        if (forVoiceChat && voiceActive) {
            if (!microphonePaused) {
                setVoiceStatus("Listening…");
                scheduleRecognition();
            } else {
                setVoiceStatus("Microphone paused");
            }
        }
    };

    utterance.onerror = () => {
        isSpeaking = false;
        voiceOrb.classList.remove("speaking");

        if (forVoiceChat && voiceActive && !microphonePaused) {
            scheduleRecognition();
        }
    };

    speechSynthesis.speak(utterance);
}

$("previewVoiceButton").addEventListener("click", () => {
    speakReply("Hello! I am A.M., your personal AI assistant. How can I help you today?");
});


// --------------------------------------------------
// SETTINGS PANEL
// --------------------------------------------------

function openSettings() {
    settingsPanel.classList.add("open");
}

function closeSettings() {
    settingsPanel.classList.remove("open");
}

$("settingsButton").addEventListener("click", openSettings);
$("voiceSettingsButton").addEventListener("click", openSettings);
$("closeSettingsButton").addEventListener("click", closeSettings);


// --------------------------------------------------
// VOICE CONVERSATION
// --------------------------------------------------

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
recognitionSupported = Boolean(SpeechRecognition);

function setVoiceStatus(text) {
    voiceStatus.textContent = text;
}

function startVoiceScreen() {
    voiceDraft = [];
    voiceActive = true;
    microphonePaused = false;
    voiceExitPending = false;

    chatScreen.classList.remove("active");
    voiceScreen.classList.add("active");
    closeSettings();
    sidebar.classList.remove("open");
    voiceOrb.classList.add("listening");

    if (!recognitionSupported) {
        setVoiceStatus("Voice recognition is unavailable. Try Chrome on HTTPS or use the text box below.");
        return;
    }

    setVoiceStatus("Starting microphone…");
    startRecognition();
}

$("startVoiceButton").addEventListener("click", startVoiceScreen);

function startRecognition() {
    if (
        !voiceActive || microphonePaused || requestInProgress ||
        isSpeaking || recognitionStarting || !recognitionSupported
    ) {
        return;
    }

    try {
        recognition = new SpeechRecognition();
        recognition.lang = "en-US";
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
            recognitionStarting = false;

            if (voiceActive && !microphonePaused) {
                voiceOrb.classList.add("listening");
                setVoiceStatus("Listening… Speak to A.M.");
            }
        };

        recognition.onresult = async event => {
            const transcript = event.results[0][0].transcript.trim();
            if (transcript) await sendVoiceMessage(transcript);
        };

        recognition.onerror = event => {
            recognitionStarting = false;
            if (!voiceActive) return;

            if (event.error === "not-allowed" || event.error === "service-not-allowed") {
                voiceActive = false;
                voiceOrb.classList.remove("listening");
                setVoiceStatus("Microphone permission denied. Allow microphone access in your browser settings, then try again.");
                return;
            }

            if (event.error === "no-speech") {
                setVoiceStatus("I didn't hear anything. Listening again…");
                return;
            }

            if (event.error === "audio-capture") {
                voiceActive = false;
                setVoiceStatus("No microphone was found. Check your device.");
                return;
            }

            setVoiceStatus("Microphone: " + event.error);
        };

        recognition.onend = () => {
            recognitionStarting = false;

            if (voiceActive && !microphonePaused && !isSpeaking && !requestInProgress) {
                scheduleRecognition();
            }
        };

        recognitionStarting = true;
        recognition.start();

    } catch (error) {
        recognitionStarting = false;

        if (voiceActive) {
            setVoiceStatus("Could not start microphone. Please try again.");
        }
    }
}

function scheduleRecognition() {
    clearTimeout(nextRecognitionTimer);

    nextRecognitionTimer = setTimeout(() => {
        if (voiceActive && !microphonePaused && !isSpeaking && !requestInProgress) {
            startRecognition();
        }
    }, 500);
}

async function sendVoiceMessage(text) {
    if (!voiceActive || requestInProgress) return;

    requestInProgress = true;
    voiceDraft.push({ role: "user", text: text, time: Date.now() });
    voiceOrb.classList.remove("listening");
    setVoiceStatus("A.M. is thinking…");

    try {
        const reply = await getReply(text);
        voiceDraft.push({ role: "ai", text: reply, time: Date.now() });
        setVoiceStatus("A.M. is preparing a reply…");
        requestInProgress = false;
        speakReply(reply, true);

    } catch (error) {
        voiceDraft.push({
            role: "ai",
            text: "Sorry, I could not get a reply. " + error.message,
            time: Date.now()
        });

        requestInProgress = false;
        speakReply("Sorry, I could not get a reply. Please try again.", true);
    }
}


// --------------------------------------------------
// MICROPHONE PAUSE / RESUME
// --------------------------------------------------

$("voiceMicButton").addEventListener("click", () => {
    if (!voiceActive) {
        startVoiceScreen();
        return;
    }

    microphonePaused = !microphonePaused;

    if (microphonePaused) {
        clearTimeout(nextRecognitionTimer);
        try { recognition?.stop(); } catch (error) {}

        voiceOrb.classList.remove("listening");
        $("voiceMicButton").textContent = "🔇";
        setVoiceStatus("Microphone paused");

    } else {
        $("voiceMicButton").textContent = "🎙";
        setVoiceStatus("Starting microphone…");
        startRecognition();
    }
});


// --------------------------------------------------
// OPTIONAL TYPING WHILE IN VOICE SCREEN
// --------------------------------------------------

$("voiceTextForm").addEventListener("submit", async event => {
    event.preventDefault();

    const input = $("voiceTextInput");
    const text = input.value.trim();

    if (!text || requestInProgress) return;

    input.value = "";

    if (!voiceActive) startVoiceScreen();
    await sendVoiceMessage(text);
});

$("voicePlus").addEventListener("click", exitVoice);


// --------------------------------------------------
// EXIT AND ASK WHETHER TO SAVE
// --------------------------------------------------

function stopVoiceCapture() {
    voiceActive = false;
    microphonePaused = true;
    clearTimeout(nextRecognitionTimer);

    if ("speechSynthesis" in window) speechSynthesis.cancel();

    try { recognition?.stop(); } catch (error) {}

    isSpeaking = false;
    requestInProgress = false;
    voiceOrb.classList.remove("listening", "speaking");
}

function exitVoice() {
    stopVoiceCapture();

    if (voiceDraft.length > 0) {
        voiceExitPending = true;
        saveModal.classList.add("open");
    } else {
        returnToChat();
    }
}

$("exitVoiceButton").addEventListener("click", exitVoice);

function returnToChat() {
    saveModal.classList.remove("open");
    voiceScreen.classList.remove("active");
    chatScreen.classList.add("active");
    voiceDraft = [];
    voiceExitPending = false;
    renderChat();
    renderHistory();
}

$("saveVoiceButton").addEventListener("click", () => {
    if (!voiceExitPending) return;

    const conversation = ensureConversation();

    voiceDraft.forEach(message => {
        conversation.messages.push({
            role: message.role === "user" ? "user" : "ai",
            text: message.text,
            time: message.time || Date.now()
        });
    });

    if (conversation.title === "New chat" && voiceDraft.length > 0) {
        const firstUserMessage = voiceDraft.find(message => message.role === "user");

        if (firstUserMessage) {
            conversation.title = firstUserMessage.text.slice(0, 42) +
                (firstUserMessage.text.length > 42 ? "…" : "");
        }
    }

    conversation.updatedAt = Date.now();
    persistConversations();
    voiceDraft = [];
    returnToChat();
});

$("discardVoiceButton").addEventListener("click", () => {
    voiceDraft = [];
    returnToChat();
});


// --------------------------------------------------
// SIGN OUT
// --------------------------------------------------

$("logoutButton").addEventListener("click", async () => {
    stopVoiceCapture();

    if (supabaseClient) {
        const { error } = await supabaseClient.auth.signOut();

        if (error) {
            showAuthScreen("Sign-out error: " + error.message);
            return;
        }
    }

    showAuthScreen("You have signed out.");
});


// --------------------------------------------------
// STARTUP AND RESTORE AUTH SESSION
// --------------------------------------------------

if (conversations.length > 0) {
    activeConversationId = conversations[0].id;
} else {
    activeConversationId = null;
}

renderChat();
renderHistory();
loadVoices();

if (!supabaseClient) {
    showAuthScreen("Sign-in is not configured. Check SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in Render.");
} else {
    supabaseClient.auth.onAuthStateChange((_event, session) => {
        if (session) {
            showChatForSession(session);
        } else {
            showAuthScreen();
        }
    });

    supabaseClient.auth.getSession()
        .then(({ data, error }) => {
            if (error) {
                showAuthScreen("Could not restore your session. Please sign in.");
            } else if (data.session) {
                showChatForSession(data.session);
            } else {
                showAuthScreen();
            }
        })
        .catch(() => {
            showAuthScreen("Could not check your session. Please sign in again.");
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
    page = PAGE.replace(
        "__SUPABASE_URL_JSON__", json.dumps(SUPABASE_URL)
    ).replace(
        "__SUPABASE_KEY_JSON__", json.dumps(SUPABASE_PUBLISHABLE_KEY)
    )

    return render_template_string(page)


# --------------------------------------------------
# CHAT API — LOGIN REQUIRED
# --------------------------------------------------

@app.route("/chat", methods=["POST"])
def chat():
    user, auth_error = get_authenticated_user()

    if auth_error:
        error_message, status_code = auth_error
        return jsonify({"reply": error_message}), status_code

    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    language = str(data.get("language", "auto")).strip().lower()

    if language not in ("auto", "en", "hi", "ml"):
        language = "auto"

    if not message:
        return jsonify({"reply": "Please type or say a message."}), 400

    start_time = time.perf_counter()

    try:
        language_names = {
            "en": "English",
            "hi": "Hindi",
            "ml": "Malayalam"
        }

        if language != "auto":
            language_instruction = (
                f"\n\nImportant: Reply in {language_names[language]}. "
                "Use natural, clear language and the appropriate script. "
                "Keep the meaning of the user's question unchanged."
            )
            prompt = message + language_instruction
        else:
            prompt = message + "\n\nReply in the same language the user used."

        reply = get_ai_reply(prompt)

        return jsonify({
            "reply": reply,
            "language": language
        })

    except Exception:
        app.logger.exception("Unexpected chat error")
        return jsonify({
            "reply": "Sorry, an unexpected error occurred."
        }), 500

    finally:
        elapsed = time.perf_counter() - start_time
        print(f"Total Future AI time: {elapsed:.2f} seconds", flush=True)


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
        "supabase_configured": bool(
            SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY
        ),
        "ollama_model": MODEL
    })


# --------------------------------------------------
# START SERVER
# --------------------------------------------------

if __name__ == "__main__":
    print("=" * 45)
    print("A.M. / Future AI phone interface is starting...")
    print("Assistant name:", AI_NAME)
    print("Creator:", CREATOR_NAME)
    print("Open http://127.0.0.1:5000 on this computer.")
    print("Gemini configured:", bool(GEMINI_API_KEY))
    print("Supabase configured:", bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY))
    print("Ollama model:", MODEL)
    print("=" * 45)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
