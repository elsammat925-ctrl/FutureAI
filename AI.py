
import requests
import pyttsx3
import sounddevice as sd
import numpy as np
import speech_recognition as sr
import webrtcvad

from core.settings import AI_NAME, MODEL
from core.memory import remember, recall, load_memory

URL = "http://localhost:11434/api/chat"

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30
SILENCE_DURATION = 1.0
MAX_RECORD_SECONDS = 15
START_TIMEOUT_SECONDS = 10

WAKE_PHRASE = "hey future"


# ---------------- SPEECH OUTPUT ----------------

def speak(text):
    """Speak using the Windows Zira voice when available."""
    engine = None

    try:
        engine = pyttsx3.init("sapi5")

        for voice in engine.getProperty("voices"):
            if "zira" in voice.name.lower():
                engine.setProperty("voice", voice.id)
                break

        engine.setProperty("rate", 175)
        engine.setProperty("volume", 1.0)

        engine.say(str(text))
        engine.runAndWait()

    except Exception as error:
        print("Speaking error:", error)

    finally:
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass


# ---------------- SPEECH INPUT ----------------

def listen():
    """Record speech until silence is detected."""

    recognizer = sr.Recognizer()
    vad = webrtcvad.Vad(2)

    frame_size = int(
        SAMPLE_RATE * FRAME_DURATION_MS / 1000
    )
    frame_bytes = frame_size * 2

    silence_frames_needed = int(
        SILENCE_DURATION * 1000 / FRAME_DURATION_MS
    )

    max_frames = int(
        MAX_RECORD_SECONDS * 1000 / FRAME_DURATION_MS
    )

    start_timeout_frames = int(
        START_TIMEOUT_SECONDS * 1000 / FRAME_DURATION_MS
    )

    frames = []
    speech_started = False
    silence_frames = 0

    try:
        print("\nListening... Speak when you're ready.")

        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=frame_size,
            channels=1,
            dtype="int16"
        ) as stream:

            for frame_number in range(max_frames):
                data, overflowed = stream.read(frame_size)
                frame = bytes(data)

                if len(frame) != frame_bytes:
                    continue

                is_speech = vad.is_speech(
                    frame, SAMPLE_RATE
                )

                if is_speech:
                    speech_started = True
                    silence_frames = 0
                    frames.append(frame)

                elif speech_started:
                    frames.append(frame)
                    silence_frames += 1

                    if silence_frames >= silence_frames_needed:
                        break

                elif frame_number >= start_timeout_frames:
                    print("No speech detected.")
                    return None

        if not speech_started or not frames:
            print("I couldn't hear you. Please try again.")
            return None

        audio_data = sr.AudioData(
            b"".join(frames),
            SAMPLE_RATE,
            2
        )

        print("Converting speech to text...")

        question = recognizer.recognize_google(
            audio_data,
            language="en-IN"
        )

        print("You said:", question)
        return question

    except sr.UnknownValueError:
        print("I couldn't understand you.")

    except sr.RequestError as error:
        print("Speech recognition service error:", error)
        print("Check your internet connection.")

    except Exception as error:
        print("Microphone or voice detection error:", error)

    return None


# ---------------- CONVERSATION MEMORY ----------------

messages = [
    {
        "role": "system",
        "content": (
            "You are Future AI. Answer questions clearly, "
            "helpfully, and simply. Use concise answers."
        )
    }
]


def show_memories():
    saved = load_memory()

    if saved:
        print(AI_NAME + ": Here is what I remember:")

        for key, value in saved.items():
            print(f"- {key}: {value}")

    else:
        print(AI_NAME + ": I don't have any saved memories.")


def handle_special_command(question):
    """
    Handle memory commands.
    Return True when a command has been handled.
    """

    lower_question = question.strip().lower()

    # Display memories
    if lower_question == "memories":
        show_memories()
        return True

    # Recall memory: recall: key
    if lower_question.startswith("recall:"):
        key = question[len("recall:"):].strip()

        if not key:
            answer = "Please specify a memory key."
            print(AI_NAME + ":", answer)
            speak(answer)
            return True

        value = recall(key)

        if value is not None:
            print(AI_NAME + ":", value)
            speak(str(value))
        else:
            answer = "I don't have that saved."
            print(AI_NAME + ":", answer)
            speak(answer)

        return True

    # Recall memory: recall key
    if lower_question.startswith("recall "):
        key = question.strip()[7:].strip()
        value = recall(key) if key else None

        if value is not None:
            print(AI_NAME + ":", value)
            speak(str(value))
        else:
            answer = "I don't have that saved."
            print(AI_NAME + ":", answer)
            speak(answer)

        return True

    # Save memory: remember: key = value
    if lower_question.startswith("remember:"):
        text = question[len("remember:"):].strip()

        if "=" in text:
            key, value = text.split("=", 1)

            if key.strip() and value.strip():
                remember(key.strip(), value.strip())

                answer = "I saved that in memory."
                print(AI_NAME + ":", answer)
                speak(answer)

            else:
                answer = "Please provide both a key and value."
                print(AI_NAME + ":", answer)
                speak(answer)

        else:
            answer = "Use remember: key = value"
            print(AI_NAME + ":", answer)
            speak(answer)

        return True

    # Remember favorite subject
    prefix = "my favorite subject is "

    if lower_question.startswith(prefix):
        value = question[len(prefix):].strip()

        if value:
            remember("favorite_subject", value)

            answer = (
                "I'll remember your favorite subject is "
                + value + "."
            )

            print(AI_NAME + ":", answer)
            speak(answer)

        return True

    return False


# ---------------- ASK THE AI ----------------

def ask_ai(question):
    messages.append({
        "role": "user",
        "content": question
    })

    try:
        print(AI_NAME + " is thinking...")

        response = requests.post(
            URL,
            json={
                "model": MODEL,
                "messages": messages,
                "stream": False
            },
            timeout=300
        )

        response.raise_for_status()

        answer = response.json()["message"]["content"].strip()

        messages.append({
            "role": "assistant",
            "content": answer
        })

        print("\n" + AI_NAME + ":", answer, "\n")
        print("Speaking answer...")
        speak(answer)
        print("Finished speaking.")

    except requests.RequestException as error:
        messages.pop()

        print("ERROR: Could not contact Ollama.")
        print("Make sure Ollama is running.")
        print("Details:", error)

    except (ValueError, KeyError) as error:
        messages.pop()

        print("ERROR: Unexpected response from Ollama.")
        print("Details:", error)


# ---------------- CONTINUOUS VOICE CONVERSATION ----------------

def voice_conversation():
    print("\nContinuous voice conversation started.")
    print("Ask your question after listening begins.")
    print("Say 'exit' to end the conversation.")

    speak("Future AI is ready. What would you like to know?")

    while True:
        try:
            question = listen()

            if not question:
                continue

            command = question.strip().lower()

            if command in (
                "exit", "quit", "goodbye", "stop conversation"
            ):
                speak("Goodbye!")
                print("Voice conversation ended.")
                break

            if handle_special_command(question):
                continue

            ask_ai(question)

        except KeyboardInterrupt:
            print("\nVoice conversation ended.")
            break


# ---------------- HEY FUTURE WAKE WORD ----------------

def wake_word_conversation():
    print("\nHey Future mode activated.")
    print("Say 'Hey Future' to wake me up.")
    print("You can also say 'Hey Future' followed by a question.")
    print("Type Ctrl+C to leave wake-word mode.")

    speak(
        "Hey Future mode is ready. "
        "Say Hey Future when you need me."
    )

    while True:
        try:
            heard = listen()

            if not heard:
                continue

            normalized = heard.lower().strip()

            # Remove common punctuation for phrase detection.
            normalized = (
                normalized
                .replace(",", "")
                .replace(".", "")
                .replace("!", "")
                .replace("?", "")
            )

            if normalized in ("exit", "quit", "goodbye"):
                speak("Wake-word mode stopped. Goodbye!")
                print("Wake-word mode stopped.")
                break

            if normalized == WAKE_PHRASE:
                speak("Yes? I'm listening.")
                question = listen()

                if not question:
                    continue

            elif normalized.startswith(WAKE_PHRASE + " "):
                # Keep the part after "Hey Future".
                question = heard.strip()[len(WAKE_PHRASE):].strip()
                question = question.lstrip(" ,.!?")

                if not question:
                    speak("What would you like to know?")
                    question = listen()

                if not question:
                    continue

            else:
                print("Wake word not detected.")
                continue

            command = question.strip().lower()

            if command in ("exit", "quit", "goodbye"):
                speak("Goodbye!")
                print("Wake-word mode stopped.")
                break

            if handle_special_command(question):
                continue

            ask_ai(question)

        except KeyboardInterrupt:
            print("\nWake-word mode stopped.")
            break


# ---------------- START FUTURE AI ----------------

print("=" * 32)
print("       " + AI_NAME)
print("=" * 32)

print("Commands:")
print("talk - Start continuous voice conversation")
print("voice - Ask one spoken question")
print("wake - Activate Hey Future wake-word mode")
print("remember: key = value")
print("recall: key")
print("memories")
print("exit")
print()

while True:
    try:
        question = input("You: ").strip()

    except (EOFError, KeyboardInterrupt):
        print("\n" + AI_NAME + ": Goodbye!")
        speak("Goodbye!")
        break

    if not question:
        continue

    lower_question = question.lower()

    # Exit
    if lower_question in ("exit", "bye", "quit"):
        print(AI_NAME + ": Goodbye!")
        speak("Goodbye!")
        break

    # Continuous conversation
    if lower_question == "talk":
        voice_conversation()
        continue

    # Wake-word mode
    if lower_question == "wake":
        wake_word_conversation()
        continue

    # One spoken question
    if lower_question == "voice":
        question = listen()

        if not question:
            continue

        lower_question = question.strip().lower()

        if lower_question in ("exit", "bye", "quit"):
            speak("Goodbye!")
            break

    # Memory commands
    if handle_special_command(question):
        continue

    # Ask Ollama
    ask_ai(question)
