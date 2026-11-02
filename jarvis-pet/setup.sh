#!/bin/sh
# Mac / Linux setup: run with  sh setup.sh
# On Mac, the microphone also needs PortAudio first: brew install portaudio
cd "$(dirname "$0")"
python3 -m pip install "anthropic>=2.3.0" || exit 1
for pkg in pillow pyttsx3 SpeechRecognition pyaudio psutil; do
  python3 -m pip install "$pkg" || echo "Skipped optional $pkg"
done
echo "Done! Run ./start.sh to wake up your pet."
