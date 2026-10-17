import json
import urllib.request
from pathlib import Path

# A.M. Future AI - Piper Voice Downloader
BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
ROOT = Path(__file__).resolve().parent
VOICE_DIR = ROOT / "voices"
VOICE_DIR.mkdir(exist_ok=True)

# A selection of free English voice models.
# Each model requires both an ONNX file and its JSON config.
VOICES = [
    "en/en_US/amy/medium/en_US-amy-medium",
    "en/en_US/arctic/medium/en_US-arctic-medium",
    "en/en_US/lessac/medium/en_US-lessac-medium",
    "en/en_US/libritts/high/en_US-libritts-high",
    "en/en_US/ryan/medium/en_US-ryan-medium",
    "en/en_US/joe/medium/en_US-joe-medium",
    "en/en_US/kristin/medium/en_US-kristin-medium",
    "en/en_US/kathleen/low/en_US-kathleen-low",
    "en/en_GB/alba/medium/en_GB-alba-medium",
    "en/en_GB/aru/medium/en_GB-aru-medium",
    "en/en_GB/cori/medium/en_GB-cori-medium",
    "en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium",
    "en/en_GB/northern_english_male/medium/en_GB-northern_english_male-medium",
    "en/en_GB/semaine/medium/en_GB-semaine-medium",
]

def download(url, destination):
    if destination.exists() and destination.stat().st_size > 1000:
        print(f"Already downloaded: {destination.name}")
        return True

    print(f"\nDownloading: {destination.name}")
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "AM-FutureAI-Voice-Downloader"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            with open(destination, "wb") as file:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    file.write(chunk)

        if destination.stat().st_size < 1000:
            destination.unlink(missing_ok=True)
            print("Download was too small; skipping.")
            return False

        print(f"Finished: {destination.name}")
        return True

    except Exception as error:
        destination.unlink(missing_ok=True)
        print(f"Could not download {destination.name}: {error}")
        return False

def main():
    downloaded = 0
    for voice in VOICES:
        model_name = voice.split("/")[-1]
        for suffix in (".onnx", ".onnx.json"):
            filename = model_name + suffix
            url = f"{BASE_URL}/{voice}{suffix}?download=true"
            if download(url, VOICE_DIR / filename):
                downloaded += 1

    print("\nDownload process finished.")
    print(f"Files ready or already present: {downloaded}")
    print(f"Voice folder: {VOICE_DIR}")
    print("Restart web_app.py and refresh your phone page.")
    print("Note: the current web_app.py must discover models in the voices folder.")
    input("\nPress Enter to close...")

if __name__ == "__main__":
    main()