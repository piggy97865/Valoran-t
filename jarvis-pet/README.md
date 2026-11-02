# Jarvis Pet

A little pet that lives on your desktop and works as your assistant, like Jarvis, powered by Claude.

It walks around the bottom of your screen, blinks, follows your mouse with its eyes, naps when you ignore it, and shows hearts when you pet it (wiggle the mouse over it).

## What it can do

Click the pet to chat, or talk to it out loud. It can:

- Answer questions and look things up on the web (news, weather, game updates)
- Open websites and apps ("open Spotify", "launch Valorant", "find a pizza recipe on YouTube")
- Set timers ("remind me in 20 minutes to take a break")
- Remember things about you between sessions ("remember my favorite agent is Jett")
- Check the time, battery, CPU and disk space
- Read what you copied, or copy text for you
- Show moods: happy, excited, love, sad, sleepy, dance

## Setup (Windows)

1. Install Python from https://www.python.org/downloads/ and tick **Add python.exe to PATH** in the installer.
2. Double-click `setup.bat`.
3. Get a Claude API key from https://console.anthropic.com (a grown-up may need to set this up, since using the API costs a little money).
4. Double-click `start.bat`. The first time you chat, the pet asks for your API key and saves it in `api_key.txt`.

On a Mac: install Python from python.org, open Terminal, `cd` into this folder, then run `sh setup.sh` and `sh start.sh`. For the microphone, install Homebrew (https://brew.sh) and run `brew install portaudio` before setup. Mac will ask to let Terminal use the microphone; say OK.

## Using it

- **Left-click** the pet: open or close the chat window.
- **Drag** the pet: move it anywhere.
- **Right-click** the pet: menu with Talk (microphone), voice on/off, wake word, walk around, forget the conversation, set the API key, settings and Quit.
- **Wake word**: turn it on in the right-click menu, then say "Jarvis, what's the weather?". This listens all the time and sends what it hears to Google's free speech service to turn it into text, so leave it off if you don't want that.

## Use your own pet

Put pictures of your pet in the `pet/` folder (one PNG or GIF is enough) and restart. See `pet/README.txt` for naming pictures by mood (`idle.png`, `talk.gif`, `sleep.png`, and more).

## Settings

Right-click, then **Open settings file**, to edit `config.json`:

| Setting | What it does |
|---|---|
| `assistant_name` | The pet's name. It's also the wake word. |
| `user_name` | Your name, so the pet can greet you. |
| `pet_size` | Size in pixels (default 150). |
| `pet_color` | Color of the built-in robot pet. |
| `voice_replies` | Speak replies out loud. |
| `voice_name_contains` | Pick a voice, e.g. `"Zira"` or `"David"` on Windows. |
| `wander` | Walk around the screen. |
| `kid_friendly` | Keep replies age-appropriate. |
| `model` / `effort` | Which Claude model to use and how hard it thinks (`low` is fastest). |
| `apps` | Names the pet can open, with the program or link to run. Fix the Valorant path here if Riot is installed somewhere else. |

Restart the pet after editing.
