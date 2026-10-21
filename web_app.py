
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
