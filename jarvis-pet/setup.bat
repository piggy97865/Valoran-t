@echo off
cd /d "%~dp0"
echo Installing Jarvis Pet...
py -m pip install --upgrade pip
py -m pip install "anthropic>=2.3.0"
if errorlevel 1 (
  echo.
  echo Could not install. Is Python installed? Get it from https://www.python.org/downloads/
  echo Tick "Add python.exe to PATH" during install.
  pause
  exit /b 1
)
for %%P in (pillow pyttsx3 SpeechRecognition pyaudio psutil) do py -m pip install %%P
echo.
echo Done! Double-click start.bat to wake up your pet.
pause
