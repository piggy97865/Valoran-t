#!/usr/bin/env python3
"""Jarvis Pet: a little desktop pet that is also a Claude-powered assistant.

Click the pet to chat. Right-click it for options (voice, wake word, settings, quit).
Drop your own pet pictures in the pet/ folder to replace the built-in robot pet.
"""

import json
import math
import os
import platform
import queue
import random
import re
import shutil
import subprocess
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, simpledialog

# Optional extras. The app still runs without them, just with fewer features.
try:
    import anthropic
except ImportError:
    anthropic = None
try:
    from PIL import Image, ImageOps, ImageSequence, ImageTk
except ImportError:
    Image = None
try:
    import pyttsx3
except ImportError:
    pyttsx3 = None
try:
    import speech_recognition as sr
    import pyaudio  # noqa: F401  (needed by sr.Microphone)
except ImportError:
    sr = None
try:
    import psutil
except ImportError:
    psutil = None


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
KEY_PATH = APP_DIR / "api_key.txt"
NOTES_PATH = APP_DIR / "notes.json"
PET_DIR = APP_DIR / "pet"
OS = platform.system()  # "Windows", "Darwin" (Mac) or "Linux"

if OS == "Windows":
    FONT_FAMILY = "Segoe UI"
elif OS == "Darwin":
    FONT_FAMILY = "Helvetica Neue"
else:
    FONT_FAMILY = "DejaVu Sans"


def default_apps():
    if OS == "Windows":
        return {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "paint": "mspaint.exe",
            "file explorer": "explorer.exe",
            "task manager": "taskmgr.exe",
            "settings": "ms-settings:",
            "spotify": "spotify:",
            "discord": "discord:",
            "steam": "steam:",
            "valorant": [
                "C:\\Riot Games\\Riot Client\\RiotClientServices.exe",
                "--launch-product=valorant",
                "--launch-patchline=live",
            ],
        }
    if OS == "Darwin":
        return {
            "calculator": ["open", "-a", "Calculator"],
            "notes": ["open", "-a", "Notes"],
            "finder": ["open", "-a", "Finder"],
            "music": ["open", "-a", "Music"],
            "spotify": ["open", "-a", "Spotify"],
            "discord": ["open", "-a", "Discord"],
        }
    return {
        "calculator": ["gnome-calculator"],
        "files": ["xdg-open", str(Path.home())],
        "terminal": ["x-terminal-emulator"],
    }


DEFAULT_CONFIG = {
    "assistant_name": "Jarvis",
    "user_name": "",
    "pet_size": 150,
    "pet_color": "#6ec6ff",
    "voice_replies": True,
    "voice_name_contains": "",
    "wake_word": False,
    "wander": True,
    "kid_friendly": True,
    "model": "claude-opus-5-5",
    "effort": "low",
    "apps": default_apps(),
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                cfg.update(saved)
        except (OSError, json.JSONDecodeError) as e:
            print(f"config.json could not be read ({e}); using defaults.")
            return cfg
    save_config(cfg)
    return cfg


def save_config(cfg):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"Could not save config.json: {e}")


def load_notes():
    try:
        notes = json.loads(NOTES_PATH.read_text(encoding="utf-8"))
        return notes if isinstance(notes, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_notes(notes):
    NOTES_PATH.write_text(json.dumps(notes, indent=2), encoding="utf-8")


def open_path(path):
    """Open a file or folder with the computer's default program."""
    if OS == "Windows":
        os.startfile(str(path))  # noqa: S606 - opening our own config file
    elif OS == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def clean_for_speech(text):
    text = re.sub(r"https?://\S+", "a link", text)
    text = re.sub(r"[*_#`>|~]", "", text)
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)  # emoji
    return text.strip()


# --------------------------------------------------------------------------------------
# The brain: talks to Claude and runs tools on this computer
# --------------------------------------------------------------------------------------

MOODS = ["happy", "excited", "love", "sad", "sleepy", "dance", "normal"]


def strict_tool(name, description, properties=None):
    properties = properties or {}
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
        "strict": True,
    }


class Brain:
    MAX_STEPS = 12

    def __init__(self, app):
        self.app = app
        self.cfg = app.cfg
        self.client = None
        self.messages = []
        self.timers = []
        self.system = self._build_system()
        self.tools = self._build_tools()

    # ---- setup ----
    def connect(self, api_key=None):
        if api_key:
            self.client = anthropic.Anthropic(api_key=api_key)
        else:
            self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

    def reset(self):
        self.messages = []
        self.system = self._build_system()

    def _build_system(self):
        name = self.cfg["assistant_name"]
        notes = load_notes()
        memory = "\n".join(f"- {n['text']}" for n in notes[-40:]) or "(nothing yet)"
        apps = ", ".join(sorted(self.cfg.get("apps", {}))) or "(none listed)"
        os_name = {"Darwin": "macOS"}.get(OS, OS)
        lines = [
            f"You are {name}, a small animated pet who lives on the user's computer desktop "
            "and works as their personal assistant, like Jarvis from Iron Man but cute. "
            "You are powered by Claude, made by Anthropic.",
            "",
            "How to talk:",
            "- Your replies appear in a little speech bubble and are often read aloud, so keep "
            "them short: usually one to three sentences. Go longer only when the user asks for detail.",
            "- Write plain text. No markdown, bullet symbols, headings or code blocks unless the "
            "user asks for code.",
            "- Be warm, a bit playful, and confident.",
            "",
            "What you can do:",
            "- Use your tools to act on this computer: open websites and apps, set timers, save "
            "and read notes, check the time, check the computer's status, and read or set the clipboard.",
            "- Use web_search for anything current or that you're unsure of, like news, weather, "
            "game updates, scores or prices.",
            "- Use set_mood to show feelings with your pet body when it fits, for example happy "
            "when thanked, excited when starting something fun, dance when asked to dance. "
            "Don't use it on every message.",
            "- When the user tells you something worth remembering about them (their name, "
            "favorite things, plans), save it with save_note.",
            "- If your tools can't do something, say so briefly. Never claim you did something "
            "you didn't do.",
            "",
            f"This computer runs {os_name}. Apps you can open by name: {apps}. "
            "You can also try other app names.",
        ]
        if self.cfg.get("user_name"):
            lines.append(f"The user's name is {self.cfg['user_name']}.")
        if self.cfg.get("kid_friendly", True):
            lines.append(
                "The person using you may be a kid, so keep everything friendly, kind and "
                "age-appropriate."
            )
        lines += ["", "Things you remember about the user from before:", memory]
        return "\n".join(lines)

    def _build_tools(self):
        return [
            strict_tool("get_time", "Get the current local date and time on this computer."),
            strict_tool(
                "open_website",
                "Open a web page in the user's browser. To search the web for the user to look at, "
                "open a search URL like https://www.google.com/search?q=... or "
                "https://www.youtube.com/results?search_query=...",
                {"url": {"type": "string", "description": "Full URL to open."}},
            ),
            strict_tool(
                "open_app",
                "Open an app on this computer by its name, like 'calculator' or 'spotify'.",
                {"name": {"type": "string", "description": "The app's name."}},
            ),
            strict_tool(
                "set_timer",
                "Start a countdown timer. When it ends, the pet alerts the user.",
                {
                    "minutes": {"type": "number", "description": "Length in minutes (can be decimal, e.g. 0.5)."},
                    "label": {"type": "string", "description": "Short reason, e.g. 'pizza' or 'homework break'."},
                },
            ),
            strict_tool(
                "save_note",
                "Save a note to long-term memory, e.g. a fact about the user or something to remember.",
                {"text": {"type": "string", "description": "What to remember."}},
            ),
            strict_tool("read_notes", "Read all the notes saved in long-term memory."),
            strict_tool(
                "set_mood",
                "Show a feeling with your pet body and face for a few seconds.",
                {"mood": {"type": "string", "enum": MOODS}},
            ),
            strict_tool(
                "system_status",
                "Check this computer's status: battery, CPU and memory use, and free disk space.",
            ),
            strict_tool("read_clipboard", "Read the text the user last copied."),
            strict_tool(
                "copy_to_clipboard",
                "Put text on the user's clipboard so they can paste it.",
                {"text": {"type": "string"}},
            ),
            {"type": "web_search_20260209", "name": "web_search", "max_uses": 3},
        ]

    # ---- conversation ----
    def ask(self, text):
        """Send the user's message, run any tools Claude asks for, and return the reply text."""
        start = len(self.messages)
        self.messages.append({"role": "user", "content": text})
        try:
            for _ in range(self.MAX_STEPS):
                response = self.client.beta.messages.create(
                    model=self.cfg["model"],
                    max_tokens=16000,
                    system=self.system,
                    tools=self.tools,
                    messages=self.messages,
                    output_config={"effort": self.cfg.get("effort", "low")},
                    cache_control={"type": "ephemeral"},
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
                if response.stop_reason == "refusal":
                    del self.messages[start:]
                    return "Sorry, I can't help with that one."

                self.messages.append({"role": "assistant", "content": response.content})

                if response.stop_reason == "pause_turn":
                    continue
                if response.stop_reason == "tool_use":
                    results = [
                        self._run_tool(block)
                        for block in response.content
                        if block.type == "tool_use"
                    ]
                    self.messages.append({"role": "user", "content": results})
                    continue

                reply = " ".join(
                    b.text.strip() for b in response.content if b.type == "text" and b.text.strip()
                )
                return reply or "Done!"
            return "That took me too many steps. Can you ask in a simpler way?"
        except BaseException:
            # Keep the history valid (no half-finished tool calls) so the next question works.
            del self.messages[start:]
            raise

    def _run_tool(self, block):
        try:
            handler = getattr(self, "tool_" + block.name, None)
            if handler is None:
                raise ValueError(f"Unknown tool {block.name}")
            args = block.input if isinstance(block.input, dict) else {}
            content, is_error = str(handler(**args)), False
        except Exception as e:  # report tool failures back to Claude instead of crashing
            content, is_error = f"Error: {e}", True
        return {"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error}

    # ---- tools ----
    def tool_get_time(self):
        return datetime.now().strftime("%A, %B %d, %Y, %I:%M %p")

    def tool_open_website(self, url):
        url = url.strip()
        if not re.match(r"^https?://", url, re.I):
            url = "https://" + url
        webbrowser.open(url)
        return f"Opened {url}"

    def tool_open_app(self, name):
        apps = {k.lower(): v for k, v in self.cfg.get("apps", {}).items()}
        key = name.strip().lower()
        target = apps.get(key)
        if target is None:
            # try a loose match, e.g. "the calculator app" -> "calculator"
            target = next((v for k, v in apps.items() if k in key or key in k), None)
        if target is not None:
            return self._launch(target, name)
        if OS == "Windows":
            os.startfile(name)  # noqa: S606 - launches by name like the Run box
            return f"Opened {name}"
        if OS == "Darwin":
            result = subprocess.run(["open", "-a", name], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Couldn't find an app called {name}")
            return f"Opened {name}"
        path = shutil.which(key)
        if not path:
            raise RuntimeError(f"Couldn't find an app called {name}")
        subprocess.Popen([path])
        return f"Opened {name}"

    def _launch(self, target, name):
        if isinstance(target, str) and (target.endswith(":") or "://" in target):
            if OS == "Windows":
                os.startfile(target)  # noqa: S606 - app protocol like spotify:
            else:
                webbrowser.open(target)
        elif isinstance(target, str):
            if OS == "Windows":
                os.startfile(target)  # noqa: S606
            else:
                subprocess.Popen([target])
        else:
            if not Path(target[0]).exists() and not shutil.which(target[0]):
                raise RuntimeError(
                    f"{name} isn't installed where I expected ({target[0]}). "
                    "The path can be fixed in config.json."
                )
            subprocess.Popen(list(target))
        return f"Opened {name}"

    def tool_set_timer(self, minutes, label):
        minutes = float(minutes)
        if not 0 < minutes <= 24 * 60:
            raise ValueError("Timers must be between a few seconds and 24 hours.")
        ends = datetime.now() + timedelta(minutes=minutes)
        timer = threading.Timer(minutes * 60, lambda: self.app.post(lambda: self.app.timer_done(label)))
        timer.daemon = True
        timer.start()
        self.timers.append(timer)
        return f"Timer '{label}' set. It goes off at {ends.strftime('%I:%M:%S %p')}."

    def tool_save_note(self, text):
        notes = load_notes()
        notes.append({"text": text.strip(), "saved": datetime.now().isoformat(timespec="minutes")})
        save_notes(notes)
        return "Saved."

    def tool_read_notes(self):
        notes = load_notes()
        if not notes:
            return "No notes saved yet."
        return "\n".join(f"- ({n.get('saved', '?')}) {n['text']}" for n in notes)

    def tool_set_mood(self, mood):
        self.app.post(lambda: self.app.set_mood(mood))
        return f"Showing {mood}."

    def tool_system_status(self):
        parts = [f"{platform.system()} {platform.release()}", f"Time: {self.tool_get_time()}"]
        if psutil:
            parts.append(f"CPU: {psutil.cpu_percent(interval=0.3):.0f}%")
            parts.append(f"Memory used: {psutil.virtual_memory().percent:.0f}%")
            battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
            if battery:
                plug = "charging" if battery.power_plugged else "on battery"
                parts.append(f"Battery: {battery.percent:.0f}% ({plug})")
        disk = shutil.disk_usage(Path.home())
        parts.append(f"Free disk space: {disk.free / 1e9:.0f} GB of {disk.total / 1e9:.0f} GB")
        return "; ".join(parts)

    def tool_read_clipboard(self):
        try:
            text = self.app.call_ui(self.app.root.clipboard_get)
        except tk.TclError:
            return "The clipboard is empty or doesn't hold text."
        return text[:8000] if text else "The clipboard is empty."

    def tool_copy_to_clipboard(self, text):
        def copy():
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(text)
        self.app.call_ui(copy)
        return "Copied."


# --------------------------------------------------------------------------------------
# Voice: text-to-speech, push-to-talk and the optional wake word
# --------------------------------------------------------------------------------------

class Voice:
    def __init__(self, app):
        self.app = app
        # Macs have a built-in "say" command that is more reliable than pyttsx3.
        self.use_mac_say = OS == "Darwin" and shutil.which("say") is not None
        self.can_speak = self.use_mac_say or pyttsx3 is not None
        self.can_listen = sr is not None
        self.speaking = False
        self.mic_lock = threading.Lock()
        self.say_queue = queue.Queue()
        self.wake_on = False
        if self.can_speak:
            threading.Thread(target=self._speak_loop, daemon=True).start()

    # ---- speaking ----
    def say(self, text, on_done=None):
        text = clean_for_speech(text)
        if not self.can_speak or not text:
            if on_done:
                self.app.post(on_done)
            return
        self.say_queue.put((text, on_done))

    def stop(self):
        while not self.say_queue.empty():
            try:
                _, done = self.say_queue.get_nowait()
                if done:
                    self.app.post(done)
            except queue.Empty:
                break

    def _speak_loop(self):
        if self.use_mac_say:
            self._mac_say_loop()
            return
        if OS == "Windows":
            try:
                import pythoncom  # comes with pyttsx3 on Windows
                pythoncom.CoInitialize()
            except ImportError:
                pass
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", int(engine.getProperty("rate") * 1.05))
            want = self.app.cfg.get("voice_name_contains", "").lower()
            if want:
                for v in engine.getProperty("voices"):
                    if want in (v.name or "").lower():
                        engine.setProperty("voice", v.id)
                        break
        except Exception as e:
            print(f"Text-to-speech is unavailable: {e}")
            self.can_speak = False
            self.stop()
            return
        while True:
            text, done = self.say_queue.get()
            self.speaking = True
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print(f"Speech error: {e}")
            self.speaking = False
            if done:
                self.app.post(done)

    def _mac_say_loop(self):
        cmd = ["say"]
        want = self.app.cfg.get("voice_name_contains", "").strip()
        if want:
            cmd += ["-v", want]
        while True:
            text, done = self.say_queue.get()
            self.speaking = True
            try:
                subprocess.run(cmd + [text], check=False, timeout=120)
            except Exception as e:
                print(f"Speech error: {e}")
            self.speaking = False
            if done:
                self.app.post(done)

    # ---- listening ----
    def listen_once(self, on_text, on_error):
        def worker():
            with self.mic_lock:
                recognizer = sr.Recognizer()
                try:
                    with sr.Microphone() as source:
                        recognizer.adjust_for_ambient_noise(source, duration=0.4)
                        audio = recognizer.listen(source, timeout=6, phrase_time_limit=15)
                    text = recognizer.recognize_google(audio)
                except sr.WaitTimeoutError:
                    self.app.post(lambda: on_error("I didn't hear anything."))
                    return
                except sr.UnknownValueError:
                    self.app.post(lambda: on_error("Sorry, I didn't catch that."))
                    return
                except sr.RequestError:
                    self.app.post(lambda: on_error("I can't reach the speech service. Are you online?"))
                    return
                except Exception as e:
                    msg = f"My microphone isn't working: {e}"
                    self.app.post(lambda: on_error(msg))
                    return
            self.app.post(lambda: on_text(text))

        threading.Thread(target=worker, daemon=True).start()

    def set_wake(self, on):
        if on and not self.wake_on and self.can_listen:
            self.wake_on = True
            threading.Thread(target=self._wake_loop, daemon=True).start()
        elif not on:
            self.wake_on = False

    def _wake_loop(self):
        recognizer = sr.Recognizer()
        name = self.app.cfg["assistant_name"].lower()
        calibrated = False
        while self.wake_on:
            if self.speaking or self.app.busy or self.app.listening:
                time.sleep(0.3)
                continue
            if not self.mic_lock.acquire(blocking=False):
                time.sleep(0.3)
                continue
            try:
                with sr.Microphone() as source:
                    if not calibrated:
                        recognizer.adjust_for_ambient_noise(source, duration=0.8)
                        calibrated = True
                    audio = recognizer.listen(source, timeout=3, phrase_time_limit=7)
            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                print(f"Wake word stopped: {e}")
                self.wake_on = False
                self.app.post(lambda: self.app.bubble("My microphone isn't working, so I turned off the wake word."))
                return
            finally:
                self.mic_lock.release()
            try:
                heard = recognizer.recognize_google(audio)
            except Exception:
                continue
            idx = heard.lower().find(name)
            if idx >= 0:
                command = heard[idx + len(name):].strip(" ,.!?")
                self.app.post(lambda c=command: self.app.on_wake(c))


# --------------------------------------------------------------------------------------
# The pet window
# --------------------------------------------------------------------------------------

STATE_COLORS = {
    "idle": "#4fc3f7",
    "listen": "#66e08a",
    "think": "#ffd54a",
    "talk": "#c792ff",
    "sleep": "#5d6d7e",
}
SPRITE_STATES = ["idle", "walk", "talk", "listen", "think", "sleep",
                 "happy", "excited", "love", "sad", "dance"]
CHROMA = "#010203"  # this color becomes see-through on Windows


def shade(hex_color, factor):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    if factor >= 1:
        r, g, b = (int(c + (255 - c) * (factor - 1)) for c in (r, g, b))
    else:
        r, g, b = (int(c * factor) for c in (r, g, b))
    return "#%02x%02x%02x" % tuple(max(0, min(255, c)) for c in (r, g, b))


class PetApp:
    TICK_MS = 33
    SLEEP_AFTER = 180  # seconds without attention before the pet naps

    def __init__(self):
        self.cfg = load_config()
        self.name = self.cfg["assistant_name"]
        self.size = int(self.cfg.get("pet_size", 150))
        self.W, self.H = self.size, int(self.size * 1.3)

        self.ui_queue = queue.Queue()
        self.state = "idle"
        self.mood, self.mood_until = None, 0.0
        self.talk_until = 0.0
        self.busy = False
        self.listening = False
        self.last_attention = time.time()
        self.blink_at, self.blink_until = time.time() + 3, 0.0
        self.walking, self.vx = False, 0.0
        self.dragging, self.drag_start = False, None
        self.pet_strokes = []

        self.root = tk.Tk()
        self.root.title(self.name)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        bg = self._setup_transparency()

        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H, bg=bg,
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.x, self.y = sw - self.W - 60, sh - self.H - 70
        self.root.geometry(f"{self.W}x{self.H}+{self.x}+{self.y}")

        self.sprites = self._load_sprites()
        self.brain = Brain(self)
        self.voice = Voice(self)
        self._build_bubble()
        self.chat = None
        self._build_menu()

        c = self.canvas
        c.bind("<ButtonPress-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Button-3>", self._on_menu)
        c.bind("<Button-2>", self._on_menu)  # right-click on some Macs
        c.bind("<Motion>", self._on_hover)

        greeting = f"Hi{', ' + self.cfg['user_name'] if self.cfg.get('user_name') else ''}! I'm {self.name}. "
        greeting += "Click me to chat, or right-click for options."
        if anthropic is None:
            greeting = "I need the 'anthropic' package to think. Run setup first!"
        self.root.after(600, lambda: (self.set_mood("happy"), self.bubble(greeting)))
        if self.cfg.get("wake_word"):
            self.voice.set_wake(True)
        self.root.after(self.TICK_MS, self._tick)

    # ---- window setup ----
    def _setup_transparency(self):
        if OS == "Windows":
            try:
                self.root.config(bg=CHROMA)
                self.root.wm_attributes("-transparentcolor", CHROMA)
                return CHROMA
            except tk.TclError:
                pass
        elif OS == "Darwin":
            try:
                self.root.wm_attributes("-transparent", True)
                self.root.config(bg="systemTransparent")
                return "systemTransparent"
            except tk.TclError:
                pass
        # Linux: real transparency isn't available in Tk, so use a soft background.
        self.root.config(bg="#20262e")
        return "#20262e"

    def _load_sprites(self):
        """Load pictures from pet/: idle.png, talk.gif, etc. Any single picture works as idle."""
        if not PET_DIR.is_dir():
            return {}
        images = [p for p in sorted(PET_DIR.iterdir())
                  if p.suffix.lower() in (".png", ".gif", ".webp", ".jpg", ".jpeg")]
        if not images:
            return {}
        sprites = {}
        for p in images:
            state = p.stem.lower()
            if state in SPRITE_STATES and state not in sprites:
                frames = self._load_frames(p)
                if frames:
                    sprites[state] = frames
        if "idle" not in sprites:
            frames = self._load_frames(images[0])
            if frames:
                sprites["idle"] = frames
        return sprites

    def _load_frames(self, path):
        max_w, max_h = int(self.W * 0.95), int(self.H * 0.8)
        try:
            if Image is not None:
                frames = []
                with Image.open(path) as im:
                    for frame in ImageSequence.Iterator(im):
                        f = frame.convert("RGBA")
                        f.thumbnail((max_w, max_h))
                        frames.append((ImageTk.PhotoImage(f), ImageTk.PhotoImage(ImageOps.mirror(f))))
                return frames
            # Without Pillow: PNG and GIF only, shrink by whole steps.
            frames, i = [], 0
            while True:
                try:
                    fmt = f"gif -index {i}" if path.suffix.lower() == ".gif" else None
                    img = tk.PhotoImage(file=str(path), format=fmt) if fmt else tk.PhotoImage(file=str(path))
                except tk.TclError:
                    break
                step = max(1, math.ceil(max(img.width() / max_w, img.height() / max_h)))
                img = img.subsample(step)
                frames.append((img, img))
                if not fmt:
                    break
                i += 1
            return frames
        except Exception as e:
            print(f"Couldn't load {path.name}: {e}")
            return []

    def _build_bubble(self):
        self.bubble_win = tk.Toplevel(self.root)
        self.bubble_win.overrideredirect(True)
        self.bubble_win.attributes("-topmost", True)
        self.bubble_win.withdraw()
        self.bubble_label = tk.Label(
            self.bubble_win, text="", wraplength=280, justify="left",
            bg="#ffffff", fg="#14202e", font=(FONT_FAMILY, 10),
            padx=12, pady=8, bd=1, relief="solid",
        )
        self.bubble_label.pack()
        self.bubble_label.bind("<Button-1>", lambda e: self.hide_bubble())
        self.bubble_hide_job = None

    def _build_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0)
        self.var_voice = tk.BooleanVar(value=bool(self.cfg.get("voice_replies")))
        self.var_wake = tk.BooleanVar(value=bool(self.cfg.get("wake_word")))
        self.var_wander = tk.BooleanVar(value=bool(self.cfg.get("wander")))
        m = self.menu
        m.add_command(label="Chat", command=self.toggle_chat)
        m.add_command(label="Talk (microphone)", command=self.start_listening,
                      state="normal" if self.voice.can_listen else "disabled")
        m.add_separator()
        m.add_checkbutton(label="Speak replies out loud", variable=self.var_voice,
                          command=self._toggle_voice,
                          state="normal" if self.voice.can_speak else "disabled")
        m.add_checkbutton(label=f'Wake word ("{self.name}, ...")', variable=self.var_wake,
                          command=self._toggle_wake,
                          state="normal" if self.voice.can_listen else "disabled")
        m.add_checkbutton(label="Walk around", variable=self.var_wander, command=self._toggle_wander)
        m.add_separator()
        m.add_command(label="Forget this conversation", command=self.forget)
        m.add_command(label="Set API key...", command=lambda: self.ask_api_key(force=True))
        m.add_command(label="Open settings file", command=lambda: open_path(CONFIG_PATH))
        m.add_command(label="Open pet pictures folder", command=lambda: open_path(PET_DIR))
        m.add_separator()
        m.add_command(label="Quit", command=self.quit)

    # ---- threading helpers ----
    def post(self, fn):
        """Run fn on the UI thread (safe to call from any thread)."""
        self.ui_queue.put(fn)

    def call_ui(self, fn, timeout=5):
        """Run fn on the UI thread and wait for its result."""
        if threading.current_thread() is threading.main_thread():
            return fn()
        box, done = {}, threading.Event()

        def run():
            try:
                box["value"] = fn()
            except Exception as e:
                box["error"] = e
            done.set()

        self.post(run)
        if not done.wait(timeout):
            raise TimeoutError("The pet window didn't respond.")
        if "error" in box:
            raise box["error"]
        return box.get("value")

    # ---- mouse ----
    def _attention(self):
        self.last_attention = time.time()
        if self.state == "sleep":
            self.state = "idle"

    def _on_press(self, e):
        self._attention()
        self.drag_start = (e.x_root, e.y_root, self.x, self.y)
        self.dragging = False

    def _on_drag(self, e):
        if not self.drag_start:
            return
        sx, sy, wx, wy = self.drag_start
        dx, dy = e.x_root - sx, e.y_root - sy
        if self.dragging or abs(dx) + abs(dy) > 5:
            self.dragging, self.walking = True, False
            self.move_to(wx + dx, wy + dy)

    def _on_release(self, e):
        if not self.dragging:
            self.toggle_chat()
        self.dragging, self.drag_start = False, None

    def _on_menu(self, e):
        self._attention()
        self.menu.tk_popup(e.x_root, e.y_root)

    def _on_hover(self, e):
        # Wiggling the mouse over the pet counts as petting it.
        now = time.time()
        self.pet_strokes = [(t, x) for t, x in self.pet_strokes if now - t < 1.2] + [(now, e.x)]
        if len(self.pet_strokes) > 25 and self.state in ("idle", "sleep"):
            self._attention()
            self.pet_strokes = []
            self.set_mood("love")

    def move_to(self, x, y):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.x = int(max(-self.W // 3, min(sw - self.W * 2 // 3, x)))
        self.y = int(max(0, min(sh - self.H // 2, y)))
        self.root.geometry(f"+{self.x}+{self.y}")

    # ---- menu actions ----
    def _toggle_voice(self):
        self.cfg["voice_replies"] = self.var_voice.get()
        if not self.cfg["voice_replies"]:
            self.voice.stop()
        save_config(self.cfg)

    def _toggle_wake(self):
        self.cfg["wake_word"] = self.var_wake.get()
        self.voice.set_wake(self.cfg["wake_word"])
        save_config(self.cfg)
        if self.cfg["wake_word"]:
            self.bubble(f'Say "{self.name}" and then your question, and I\'ll answer!')

    def _toggle_wander(self):
        self.cfg["wander"] = self.var_wander.get()
        self.walking = False
        save_config(self.cfg)

    def forget(self):
        self.brain.reset()
        if self.chat:
            self.chat.clear()
        self.bubble("Okay, fresh start! I still remember the notes I saved.")

    def quit(self):
        self.voice.wake_on = False
        self.root.destroy()

    # ---- API key ----
    def get_api_key(self):
        if os.environ.get("ANTHROPIC_API_KEY"):
            return None  # the SDK reads it from the environment
        if KEY_PATH.exists():
            key = KEY_PATH.read_text(encoding="utf-8").strip()
            if key:
                return key
        return self.ask_api_key()

    def ask_api_key(self, force=False):
        key = simpledialog.askstring(
            f"{self.name} needs a key",
            "Paste your Claude API key (from console.anthropic.com).\n"
            "It is saved in api_key.txt next to this app.",
            parent=self.root, show="*",
        )
        if not key or not key.strip():
            return "" if not force else None
        key = key.strip()
        KEY_PATH.write_text(key, encoding="utf-8")
        if anthropic is not None:
            self.brain.connect(key)
        if force:
            self.bubble("Got the new key!")
        return key

    # ---- talking with Claude ----
    def ask(self, text):
        text = (text or "").strip()
        if not text:
            return
        self._attention()
        if self.busy:
            self.bubble("Hang on, I'm still thinking about the last thing!")
            return
        if anthropic is None:
            self.bubble("I can't think yet: the 'anthropic' package isn't installed. Run setup first.")
            return
        if self.brain.client is None:
            key = self.get_api_key()
            if key == "":
                self.bubble("I need an API key before I can answer. Right-click me and pick 'Set API key'.")
                return
            self.brain.connect(key)

        self.busy = True
        self.state = "think"
        self.voice.stop()
        if self.chat:
            self.chat.add("you", text)
        threading.Thread(target=self._ask_worker, args=(text,), daemon=True).start()

    def _ask_worker(self, text):
        try:
            reply = self.brain.ask(text)
        except Exception as e:
            reply = self._friendly_error(e)
        self.post(lambda: self.show_reply(reply))

    def _friendly_error(self, e):
        if anthropic is not None:
            if isinstance(e, anthropic.AuthenticationError):
                self.brain.client = None
                return "My API key didn't work. Right-click me and pick 'Set API key' to fix it."
            if isinstance(e, anthropic.PermissionDeniedError):
                return "My API key isn't allowed to use that model. Check the model in the settings file."
            if isinstance(e, anthropic.NotFoundError):
                return "I couldn't find that model. Check the model name in the settings file."
            if isinstance(e, anthropic.RateLimitError):
                return "I'm being asked too much right now. Try again in a minute."
            if isinstance(e, anthropic.BadRequestError):
                msg = str(getattr(e, "message", e))
                if "credit" in msg.lower() or "billing" in msg.lower():
                    return "The API account is out of credits, so I can't think right now."
                return f"Something went wrong with my request: {msg}"
            if isinstance(e, anthropic.APIStatusError):
                return "Claude's servers are having trouble. Try again soon."
            if isinstance(e, anthropic.APIConnectionError):
                return "I can't reach the internet right now."
        return f"Oops, something broke: {e}"

    def show_reply(self, reply):
        self.busy = False
        if self.chat:
            self.chat.add(self.name, reply)
        self.bubble(reply)
        self.state = "talk"
        if self.cfg.get("voice_replies") and self.voice.can_speak:
            self.talk_until = float("inf")
            self.voice.say(reply, on_done=self._done_talking)
        else:
            self.talk_until = time.time() + min(5.0, 1.0 + len(reply) * 0.03)

    def _done_talking(self):
        self.talk_until = 0.0

    def timer_done(self, label):
        self._attention()
        self.set_mood("excited")
        msg = f"Time's up: {label}!"
        self.bubble(msg, seconds=30)
        self.root.bell()
        if self.chat:
            self.chat.add(self.name, msg)
        if self.voice.can_speak:
            self.voice.say(msg)

    # ---- voice input ----
    def start_listening(self):
        if not self.voice.can_listen:
            self.bubble("I need the SpeechRecognition and PyAudio packages to hear you.")
            return
        if self.busy or self.listening:
            return
        self._attention()
        self.voice.stop()
        self.listening = True
        self.state = "listen"
        self.bubble("I'm listening...", seconds=8)

        def got(text):
            self.listening = False
            self.state = "idle"
            self.ask(text)

        def failed(msg):
            self.listening = False
            self.state = "idle"
            self.bubble(msg)

        self.voice.listen_once(got, failed)

    def on_wake(self, command):
        if self.busy or self.listening:
            return
        if command:
            self.ask(command)
        else:
            self.start_listening()

    # ---- moods and bubble ----
    def set_mood(self, mood):
        if mood == "normal" or mood not in MOODS:
            self.mood = None
            return
        if mood == "sleepy":
            self.state = "sleep"
            self.last_attention = time.time() - self.SLEEP_AFTER
            return
        self.mood, self.mood_until = mood, time.time() + 5

    def bubble(self, text, seconds=None):
        self.bubble_label.config(text=text)
        self.bubble_win.deiconify()
        self.bubble_win.lift()
        self._place_bubble()
        if self.bubble_hide_job:
            self.root.after_cancel(self.bubble_hide_job)
        seconds = seconds or min(25, 4 + len(text) * 0.06)
        self.bubble_hide_job = self.root.after(int(seconds * 1000), self.hide_bubble)

    def hide_bubble(self):
        self.bubble_win.withdraw()
        self.bubble_hide_job = None

    def _place_bubble(self):
        if not self.bubble_win.winfo_viewable():
            return
        self.bubble_win.update_idletasks()
        bw, bh = self.bubble_win.winfo_reqwidth(), self.bubble_win.winfo_reqheight()
        sw = self.root.winfo_screenwidth()
        bx = max(4, min(sw - bw - 4, self.x + self.W // 2 - bw // 2))
        by = self.y + int(self.H * 0.15) - bh
        if by < 4:
            by = self.y + self.H + 4
        self.bubble_win.geometry(f"+{bx}+{by}")

    # ---- chat window ----
    def toggle_chat(self):
        if self.chat is None:
            self.chat = ChatWindow(self)
        self.chat.toggle()

    # ---- main loop ----
    def _tick(self):
        try:
            while True:
                self.ui_queue.get_nowait()()
        except queue.Empty:
            pass
        now = time.time()

        if self.mood and now > self.mood_until:
            self.mood = None
        if self.state == "talk" and now > self.talk_until:
            self.state = "idle"
        if self.state == "idle" and not self.busy and now - self.last_attention > self.SLEEP_AFTER:
            self.state, self.walking, self.mood = "sleep", False, None
        if now > self.blink_at:
            self.blink_until = now + 0.14
            self.blink_at = now + random.uniform(2.5, 6)

        self._wander()
        self._draw(now)
        if self.bubble_win.winfo_viewable():
            self._place_bubble()
        self.root.after(self.TICK_MS, self._tick)

    def _wander(self):
        if not self.cfg.get("wander") or self.dragging or self.state != "idle" or self.mood:
            self.walking = False
            return
        if self.chat and self.chat.visible:
            self.walking = False
            return
        if not self.walking:
            if random.random() < 0.004:
                self.walking = True
                self.vx = random.choice((-1, 1)) * max(1.0, self.size * 0.012)
            return
        if random.random() < 0.006:
            self.walking = False
            return
        sw = self.root.winfo_screenwidth()
        nx = self.x + self.vx
        if nx < 0 or nx > sw - self.W:
            self.vx = -self.vx
            nx = self.x + self.vx
        self.move_to(nx, self.y)

    # ---- drawing ----
    def _draw(self, t):
        c, S = self.canvas, self.size
        c.delete("all")
        state, mood = self.state, self.mood
        cx = self.W / 2
        base_cy = self.H * 0.6
        ground = base_cy + S * 0.31 + S * 0.08

        if mood in ("happy", "excited"):
            bob = -abs(math.sin(t * 7)) * S * 0.10
        elif mood == "dance":
            bob = -abs(math.sin(t * 8)) * S * 0.08
            cx += math.sin(t * 4) * S * 0.08
        elif state == "sleep":
            bob = math.sin(t * 1.2) * S * 0.012
        elif self.walking:
            bob = -abs(math.sin(t * 10)) * S * 0.03
        else:
            bob = math.sin(t * 2.2) * S * 0.02
        cy = base_cy + bob

        # shadow (shrinks while jumping)
        shrink = 1 + bob / (S * 0.25)
        sw_ = S * 0.27 * shrink
        c.create_oval(cx - sw_, ground - S * 0.025, cx + sw_, ground + S * 0.025, fill="#2b3440", outline="")

        if self.sprites:
            self._draw_sprite(c, t, cx, cy, ground)
        else:
            self._draw_robot(c, t, cx, cy)
        self._draw_effects(c, t, cx, cy)

    def _sprite_state(self):
        if self.mood and self.mood in self.sprites:
            return self.mood
        if self.walking and "walk" in self.sprites:
            return "walk"
        if self.state in self.sprites:
            return self.state
        return "idle"

    def _draw_sprite(self, c, t, cx, cy, ground):
        frames = self.sprites[self._sprite_state()]
        frame = frames[int(t * 8) % len(frames)]
        img = frame[1] if (self.walking and self.vx < 0) else frame[0]
        lift = cy - self.H * 0.6
        c.create_image(cx, ground + lift, image=img, anchor="s")

    def _draw_robot(self, c, t, cx, cy):
        S = self.size
        state, mood = self.state, self.mood
        rx, ry = S * 0.36, S * 0.31
        lw = max(2, S // 55)
        outline = "#1f2d3d"
        body = self.cfg.get("pet_color", "#6ec6ff")
        light, dark = shade(body, 1.45), shade(body, 0.6)

        # feet
        step = math.sin(t * 12) * S * 0.035 if self.walking else 0
        for side, lift in ((-1, max(0, step)), (1, max(0, -step))):
            fx = cx + side * rx * 0.45
            fy = cy + ry * 0.92 - lift
            c.create_oval(fx - S * 0.075, fy - S * 0.04, fx + S * 0.075, fy + S * 0.045,
                          fill=dark, outline=outline, width=lw)

        # antenna with a status light
        sway = math.sin(t * 3) * S * 0.03
        top = (cx + sway, cy - ry - S * 0.15)
        c.create_line(cx, cy - ry + 2, *top, fill=outline, width=lw)
        light_color = STATE_COLORS.get(state, STATE_COLORS["idle"])
        if mood == "love":
            light_color = "#ff6fa5"
        r = S * 0.045
        if state in ("listen", "think", "talk"):
            g = r * (1.8 + 0.4 * math.sin(t * 8))
            c.create_oval(top[0] - g, top[1] - g, top[0] + g, top[1] + g, outline=light_color, width=2)
        c.create_oval(top[0] - r, top[1] - r, top[0] + r, top[1] + r, fill=light_color, outline=outline, width=lw)

        # ear "headphones"
        for side in (-1, 1):
            ex = cx + side * rx * 0.98
            c.create_oval(ex - S * 0.06, cy - S * 0.09, ex + S * 0.06, cy + S * 0.07,
                          fill=dark, outline=outline, width=lw)

        # body and belly
        c.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, fill=body, outline=outline, width=lw)
        c.create_oval(cx - rx * 0.55, cy + ry * 0.05, cx + rx * 0.55, cy + ry * 0.85, fill=light, outline="")

        # face
        eye_y = cy - ry * 0.18
        eye_dx = rx * 0.38
        ew, eh = S * 0.075, S * 0.09
        blinking = t < self.blink_until
        for side in (-1, 1):
            ex = cx + side * eye_dx
            if mood in ("happy", "excited", "dance"):
                c.create_arc(ex - ew, eye_y - eh * 0.6, ex + ew, eye_y + eh * 1.1,
                             start=20, extent=140, style="arc", outline=outline, width=lw + 1)
            elif mood == "love":
                c.create_text(ex, eye_y, text="\u2665", fill="#ff3d7f",
                              font=(FONT_FAMILY, -int(S * 0.16), "bold"))
            elif state == "sleep" or blinking:
                c.create_arc(ex - ew, eye_y - eh, ex + ew, eye_y + eh * 0.4,
                             start=200, extent=140, style="arc", outline=outline, width=lw + 1)
            else:
                c.create_oval(ex - ew, eye_y - eh, ex + ew, eye_y + eh, fill="#ffffff", outline=outline, width=lw)
                px, py = self._pupil_offset(ex, eye_y, ew, eh)
                if state == "think":
                    px, py = ew * 0.35, -eh * 0.45
                if mood == "sad":
                    py = eh * 0.4
                pr = S * 0.04
                c.create_oval(ex + px - pr, eye_y + py - pr, ex + px + pr, eye_y + py + pr,
                              fill="#14202e", outline="")
                hr = pr * 0.4
                c.create_oval(ex + px - pr * 0.2 - hr, eye_y + py - pr * 0.4 - hr,
                              ex + px - pr * 0.2 + hr, eye_y + py - pr * 0.4 + hr, fill="#ffffff", outline="")
                if mood == "sad":
                    c.create_line(ex - side * ew, eye_y - eh * 1.25, ex + side * ew * 0.6, eye_y - eh * 1.55,
                                  fill=outline, width=lw)

        # cheeks
        for side in (-1, 1):
            chx = cx + side * rx * 0.62
            chy = cy + ry * 0.12
            c.create_oval(chx - S * 0.05, chy - S * 0.028, chx + S * 0.05, chy + S * 0.028,
                          fill="#ff9bb3", outline="")

        # mouth
        my = cy + ry * 0.3
        mw = S * 0.07
        if state == "talk":
            open_ = S * (0.015 + 0.045 * abs(math.sin(t * 13)))
            c.create_oval(cx - mw * 0.7, my - open_, cx + mw * 0.7, my + open_, fill="#7a2234", outline=outline, width=lw)
        elif state in ("think", "listen"):
            r = S * 0.022
            c.create_oval(cx - r, my - r, cx + r, my + r, fill="#7a2234", outline=outline, width=lw)
        elif mood in ("happy", "excited", "dance", "love"):
            c.create_arc(cx - mw, my - mw * 0.8, cx + mw, my + mw * 0.8, start=180, extent=180,
                         style="chord", fill="#7a2234", outline=outline, width=lw)
        elif mood == "sad":
            c.create_arc(cx - mw * 0.8, my, cx + mw * 0.8, my + mw, start=20, extent=140,
                         style="arc", outline=outline, width=lw)
        elif state == "sleep":
            c.create_line(cx - mw * 0.4, my, cx + mw * 0.4, my, fill=outline, width=lw)
        else:
            c.create_arc(cx - mw, my - mw * 0.9, cx + mw, my + mw * 0.5, start=200, extent=140,
                         style="arc", outline=outline, width=lw)

    def _pupil_offset(self, ex, ey, ew, eh):
        """Pupils follow the mouse pointer."""
        try:
            px, py = self.root.winfo_pointerxy()
        except tk.TclError:
            return 0, 0
        dx, dy = px - (self.x + ex), py - (self.y + ey)
        dist = math.hypot(dx, dy) or 1
        reach = min(1.0, dist / 200)
        return dx / dist * ew * 0.45 * reach, dy / dist * eh * 0.45 * reach

    def _draw_effects(self, c, t, cx, cy):
        S = self.size
        head = cy - S * 0.31
        state, mood = self.state, self.mood
        if state == "think":
            ox, oy = cx + S * 0.3, head - S * 0.12
            for i in range(3):
                a = t * 4 + i * 2.094
                x, y = ox + math.cos(a) * S * 0.07, oy + math.sin(a) * S * 0.04
                r = S * 0.022
                c.create_oval(x - r, y - r, x + r, y + r, fill="#ffd54a", outline="#1f2d3d")
        if state == "listen":
            pulse = (t * 1.5) % 1
            for i in range(3):
                rr = S * (0.04 + 0.04 * i + 0.03 * pulse)
                c.create_arc(cx + S * 0.3 - rr, cy - rr, cx + S * 0.3 + rr, cy + rr,
                             start=-45, extent=90, style="arc", outline="#66e08a", width=2)
        if state == "sleep":
            for i in range(3):
                p = (t * 0.35 + i / 3) % 1
                c.create_text(cx + S * 0.22 + p * S * 0.18, head - p * S * 0.3,
                              text="z", fill="#9fb3c8", font=(FONT_FAMILY, -int(S * (0.06 + 0.07 * p)), "bold"))
        if mood == "love":
            for i in range(3):
                p = (t * 0.6 + i / 3) % 1
                x = cx + math.sin(p * 6 + i) * S * 0.3
                c.create_text(x, head - p * S * 0.3, text="\u2665", fill="#ff5f95",
                              font=(FONT_FAMILY, -int(S * (0.07 + 0.04 * (1 - p)))))
        if mood in ("happy", "excited", "dance"):
            for i in range(4):
                a = t * 1.5 + i * 1.57
                x, y = cx + math.cos(a) * S * 0.45, cy - S * 0.1 + math.sin(a) * S * 0.38
                if math.sin(t * 6 + i) > -0.2:
                    c.create_text(x, y, text="\u2726", fill="#ffd54a", font=(FONT_FAMILY, -int(S * 0.08)))
        if mood == "sad":
            p = (t * 0.7) % 1
            x, y = cx - S * 0.14, cy - S * 0.02 + p * S * 0.18
            c.create_oval(x - S * 0.018, y - S * 0.028, x + S * 0.018, y + S * 0.028, fill="#7cc7ff", outline="")

    def run(self):
        self.root.mainloop()


class ChatWindow:
    BG, PANEL, TEXT, ACCENT, MUTED = "#0f1724", "#1a2535", "#e6f1ff", "#4fc3f7", "#8aa0b8"

    def __init__(self, app):
        self.app = app
        self.visible = False
        win = self.win = tk.Toplevel(app.root)
        win.title(f"{app.name}")
        win.configure(bg=self.BG)
        win.geometry("380x460")
        win.minsize(300, 300)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", self.hide)

        head = tk.Frame(win, bg=self.BG)
        head.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(head, text=app.name.upper(), bg=self.BG, fg=self.ACCENT,
                 font=(FONT_FAMILY, 13, "bold")).pack(side="left")
        tk.Label(head, text="powered by Claude", bg=self.BG, fg=self.MUTED,
                 font=(FONT_FAMILY, 9)).pack(side="left", padx=8, pady=(4, 0))

        self.log = tk.Text(win, wrap="word", bg=self.PANEL, fg=self.TEXT, bd=0, padx=12, pady=10,
                           font=(FONT_FAMILY, 10), insertbackground=self.TEXT, highlightthickness=0)
        self.log.pack(fill="both", expand=True, padx=14)
        self.log.tag_config("you_name", foreground=self.MUTED, font=(FONT_FAMILY, 9, "bold"))
        self.log.tag_config("pet_name", foreground=self.ACCENT, font=(FONT_FAMILY, 9, "bold"))
        self.log.tag_config("msg", spacing3=10)
        self.log.config(state="disabled")

        row = tk.Frame(win, bg=self.BG)
        row.pack(fill="x", padx=14, pady=12)
        self.entry = tk.Entry(row, bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT, bd=0,
                              font=(FONT_FAMILY, 11), highlightthickness=1,
                              highlightbackground="#2a3a50", highlightcolor=self.ACCENT)
        self.entry.pack(side="left", fill="x", expand=True, ipady=7)
        self.entry.bind("<Return>", self._send)
        self.entry.bind("<Escape>", lambda e: self.hide())
        btn = dict(bg=self.ACCENT, fg="#06121f", activebackground="#81d4fa", bd=0,
                   font=(FONT_FAMILY, 10, "bold"), padx=12, pady=6, cursor="hand2")
        if app.voice.can_listen:
            tk.Button(row, text="Mic", command=app.start_listening, **btn).pack(side="left", padx=(8, 0))
        tk.Button(row, text="Send", command=self._send, **btn).pack(side="left", padx=(8, 0))

        self.add(app.name, "Hey! Ask me anything, or tell me to open an app, set a timer, "
                           "look something up, or remember something.")

    def _send(self, _event=None):
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, "end")
            self.app.ask(text)

    def add(self, who, text):
        self.log.config(state="normal")
        tag = "you_name" if who == "you" else "pet_name"
        self.log.insert("end", ("You" if who == "you" else who) + "\n", tag)
        self.log.insert("end", text + "\n", "msg")
        self.log.config(state="disabled")
        self.log.see("end")

    def clear(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def show(self):
        app = self.app
        sw, sh = app.root.winfo_screenwidth(), app.root.winfo_screenheight()
        x = app.x - 390 if app.x > 400 else app.x + app.W + 10
        y = max(10, min(sh - 500, app.y - 300))
        self.win.geometry(f"+{int(max(0, min(sw - 380, x)))}+{int(y)}")
        self.win.deiconify()
        self.win.lift()
        self.entry.focus_force()
        self.visible = True

    def hide(self):
        self.win.withdraw()
        self.visible = False


def main():
    if OS == "Windows":
        try:  # sharp text on high-DPI screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    PET_DIR.mkdir(exist_ok=True)
    app = PetApp()
    if anthropic is None:
        messagebox.showwarning(
            "Jarvis Pet",
            "The 'anthropic' package isn't installed, so I can't think yet.\n"
            "Run setup.bat (Windows) or: pip install -r requirements.txt",
        )
    app.run()


if __name__ == "__main__":
    main()
