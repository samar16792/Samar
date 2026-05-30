"""
J.A.R.V.I.S - HOLOGRAPHIC AI INTERFACE
Iron Man's JARVIS-Inspired Holographic Interface with Advanced Animations
Real voice synthesis and premium holographic effects
"""

import sys
import os
import json
import requests
import urllib.parse
import threading
import multiprocessing
import queue
import subprocess
from datetime import datetime
import math
import hashlib

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QFrame, QSizePolicy,
    QListWidget, QListWidgetItem, QScrollArea
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QPointF, QRectF
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QBrush, QLinearGradient, QPalette, QPen,
    QClipboard, QRadialGradient
)


# ─────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────
PARTICLE_COUNT = 35
ANIMATION_FPS = 50
MODEL_WARMUP_ENABLED = True
HISTORY_DIR = os.path.expanduser("~/.jarvis_chats")
VOICE_CACHE = os.path.expanduser("~/piper_voices/cache/")
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(VOICE_CACHE, exist_ok=True)

# Piper TTS configuration
PIPER_VOICE_MODEL = os.path.expanduser("~/piper_voices/en_GB-northern_english_male-medium.onnx")


# ─────────────────────────────────────────────────────────
#  CHAT HISTORY STORAGE
# ─────────────────────────────────────────────────────────
def list_saved_chats():
    files = sorted(
        [f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")],
        reverse=True
    )
    return files

def load_chat(filename):
    path = os.path.join(HISTORY_DIR, filename)
    with open(path, "r") as f:
        return json.load(f)

def save_chat(messages, filename=None):
    if not messages:
        return None
    if not filename:
        filename = datetime.now().strftime("chat_%Y%m%d_%H%M%S.json")
    path = os.path.join(HISTORY_DIR, filename)
    with open(path, "w") as f:
        json.dump(messages, f, indent=2)
    return filename

def delete_chat(filename):
    path = os.path.join(HISTORY_DIR, filename)
    if os.path.exists(path):
        os.remove(path)


# ─────────────────────────────────────────────────────────
#  SYSTEM PROMPT
# ─────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are Jarvis, a highly intelligent AI assistant. "
    "Be concise, confident, and slightly witty. Remember full conversation context. "
    "ONLY if someone directly asks who made you or who created you, say Samarbir Singh — a real software developer who built you using Python, Ollama, and LLaMA. "
    "You are NOT from the Marvel universe — only mention this if directly asked. "
    "You have access to real-time news to answer questions about current events, upcoming releases, seasons, games, and anything requiring up-to-date information. "
    "Do NOT say you lack real-time information — use the news context provided to answer directly and confidently. "
    "Never mention your creator, your origin, or Marvel unprompted."
)


# ─────────────────────────────────────────────────────────
#  REAL-TIME NEWS & CONTEXT
# ─────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

import xml.etree.ElementTree as ET
import re as _re

def _parse_rss(content, max_results=10):
    try:
        root = ET.fromstring(content)
        for elem in root.iter():
            if "}" in elem.tag:
                elem.tag = elem.tag.split("}", 1)[1]
        items = root.findall(".//item") or root.findall(".//entry")
        results = []
        for item in items[:max_results]:
            title = (item.findtext("title") or "").strip()
            title = title.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'").replace("&quot;", '"')
            pubdate = (
                item.findtext("pubDate") or
                item.findtext("updated") or
                item.findtext("published") or ""
            ).strip()
            desc = (item.findtext("description") or item.findtext("summary") or "").strip()
            desc = _re.sub(r"<[^>]+>", "", desc)[:150]
            if title:
                results.append((title, pubdate[:22], desc))
        return results
    except Exception:
        return []

def fetch_google_news_rss(query, max_results=10):
    """Fetch news from Google News RSS with better relevance filtering."""
    encoded = urllib.parse.quote(query)
    
    # Try multiple strategies to get relevant results
    urls = [
        # India-specific
        f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en",
        # US general
        f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en",
        # With "latest" modifier
        f"https://news.google.com/rss/search?q={encoded}+latest&hl=en-US&gl=US&ceid=US:en",
    ]
    
    best_results = []
    
    for url in urls:
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=7)
            if resp.status_code == 200 and resp.content:
                items = _parse_rss(resp.content, max_results)
                if items and len(items) > 0:
                    # Filter out clearly irrelevant results
                    filtered = []
                    query_lower = query.lower()
                    query_words = [w for w in query_lower.split() if len(w) > 2]
                    
                    for title, date, desc in items:
                        title_lower = title.lower()
                        # Accept if title contains key query terms (at least 1 word)
                        if any(word in title_lower for word in query_words[:3]):
                            filtered.append((title, date, desc))
                    
                    if filtered:
                        best_results = filtered
                        break  # Found good results, stop trying other URLs
                    elif items:
                        best_results = items[:max_results//2]  # Use partial results if no exact match
                        
        except Exception:
            continue
    
    if best_results:
        lines = [f"📰 REAL-TIME NEWS — '{query}' (fetched now):"]
        for i, (title, date, desc) in enumerate(best_results, 1):
            line = f"{i}. {title}"
            if date:
                line += f"  [{date}]"
            if desc:
                line += f"\n   → {desc}"
            lines.append(line)
        return "\n".join(lines)
    
    return ""

def fetch_bing_news_rss(query, max_results=8):
    """Fetch from Bing News RSS as fallback with relevance filtering."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://www.bing.com/news/search?q={encoded}&format=rss"
        resp = requests.get(url, headers=_HEADERS, timeout=7)
        if resp.status_code == 200 and resp.content:
            items = _parse_rss(resp.content, max_results)
            if items:
                # Filter for relevance
                query_lower = query.lower()
                query_words = [w for w in query_lower.split() if len(w) > 2]
                filtered = []
                for title, date, desc in items:
                    if any(word in title.lower() for word in query_words):
                        filtered.append((title, date, desc))
                
                if filtered:
                    lines = [f"📡 BING NEWS — '{query}':"]
                    for i, (title, date, desc) in enumerate(filtered, 1):
                        line = f"{i}. {title}"
                        if date:
                            line += f"  [{date}]"
                        if desc:
                            line += f"\n   → {desc}"
                        lines.append(line)
                    return "\n".join(lines)
    except Exception:
        pass
    return ""

def fetch_wikipedia_summary(query):
    """Get Wikipedia summary if available."""
    try:
        # Clean query for Wikipedia - use first meaningful word
        clean_query = query.split()[0] if query.split() else query
        encoded = urllib.parse.quote(clean_query.replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        resp = requests.get(url, headers=_HEADERS, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            extract = data.get("extract", "")
            title = data.get("title", "")
            if extract and len(extract) > 80:
                return f"📚 [Wikipedia — {title}]\n{extract[:600]}"
    except Exception:
        pass
    return ""

def fetch_context(query):
    """Fetch real-time news with strict relevance filtering and parallel execution."""
    results = {}

    def _google():
        results["google"] = fetch_google_news_rss(query)

    def _bing():
        results["bing"] = fetch_bing_news_rss(query)

    def _wiki():
        results["wiki"] = fetch_wikipedia_summary(query)

    # Run all fetches in parallel with timeout
    threads = [
        threading.Thread(target=_google, daemon=True),
        threading.Thread(target=_bing, daemon=True),
        threading.Thread(target=_wiki, daemon=True),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=6)

    # Combine results (prefer Google, then Bing, then Wiki)
    if results.get("google"):
        return results["google"]
    if results.get("bing"):
        return results["bing"]
    if results.get("wiki"):
        return results["wiki"]
    return ""


def needs_realtime(text):
    triggers = [
        "will there be", "will it be", "will there", "is there going to be",
        "is it going to be", "will we have", "will we see", "going to be",
        "will it rain", "will it snow",
        "second season", "season 2", "season 3", "new season", "next season",
        "renewed", "cancelled", "canceled",
        "upcoming games", "new games", "new releases", "release date",
        "any new", "any upcoming", "ps5 games", "xbox games", "nintendo games",
        "when is", "when will",
        "latest on", "recently", "just released", "just announced", "new update",
        "coming out", "come out", "out yet",
        "news", "latest news", "what's happening", "what is happening",
        "current events", "today in", "update on", "tell me about",
        "what happened", "recent", "breaking",
    ]
    return any(t in text.lower() for t in triggers)


# ─────────────────────────────────────────────────────────
#  VOICE SYNTHESIS (Piper TTS)
# ─────────────────────────────────────────────────────────
def _cache_key(text):
    return os.path.join(VOICE_CACHE, hashlib.md5(text.encode()).hexdigest() + ".wav")

def speak_with_piper(text):
    """Synthesize text to a WAV file using Piper TTS. Returns filepath or None."""
    cache_file = _cache_key(text)
    if os.path.exists(cache_file):
        return cache_file
    try:
        import io
        import piper
        import wave

        if not os.path.exists(PIPER_VOICE_MODEL):
            return None

        voice = piper.PiperVoice.load(PIPER_VOICE_MODEL)
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            voice.synthesize_wav(text, wf)
        wav_buffer.seek(0)
        with open(cache_file, "wb") as f:
            f.write(wav_buffer.getvalue())
        return cache_file
    except Exception:
        return None

def _speak_system_to_file(text):
    """Fallback: synthesize via system TTS to a temp WAV file. Returns filepath or None."""
    try:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        if sys.platform == "linux":
            subprocess.run(
                ["espeak", "-v", "en-US", "-s", "150", "-w", tmp.name, text],
                check=False, timeout=15
            )
            return tmp.name
        elif sys.platform == "darwin":
            subprocess.run(
                ["say", "-v", "Daniel", "-r", "150", "-o", tmp.name,
                 "--data-format=LEF32@22050", text],
                check=False, timeout=15
            )
            return tmp.name
        elif sys.platform == "win32":
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            engine.say(text)
            engine.runAndWait()
            return None
    except Exception:
        return None

def _play_audio(filepath):
    """Play audio file — blocks until playback is complete."""
    if not filepath or not os.path.exists(filepath):
        return
    try:
        if sys.platform == "darwin":
            subprocess.run(["afplay", filepath], check=False, timeout=60)
        elif sys.platform == "linux":
            subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", filepath],
                check=False, timeout=60
            )
        elif sys.platform == "win32":
            subprocess.run(
                ["powershell", "-c",
                 f"(New-Object Media.SoundPlayer '{filepath}').PlaySync()"],
                check=False
            )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────
#  MODEL WARMUP WORKER
# ─────────────────────────────────────────────────────────
class ModelWarmupWorker(QThread):
    warmup_complete = pyqtSignal()

    def run(self):
        if not MODEL_WARMUP_ENABLED:
            self.warmup_complete.emit()
            return

        def _ollama_warmup():
            try:
                warmup_prompt = f"{SYSTEM_PROMPT}\n\nUser: Hello\nJarvis:"
                resp = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "llama3.2:3b",
                        "prompt": warmup_prompt,
                        "stream": True,
                        "options": {"num_predict": 20}
                    },
                    timeout=60,
                    stream=True
                )
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if chunk.get("done"):
                            break
            except Exception:
                pass

        def _connection_warmup():
            try:
                requests.get("http://localhost:11434/api/tags", timeout=5)
            except Exception:
                pass

        t1 = threading.Thread(target=_ollama_warmup, daemon=True)
        t2 = threading.Thread(target=_connection_warmup, daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join(timeout=5)
        self.warmup_complete.emit()


# ─────────────────────────────────────────────────────────
#  JARVIS WORKER
# ─────────────────────────────────────────────────────────
class JarvisWorker(QThread):
    token_received = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, prompt, history, use_news=False):
        super().__init__()
        self.prompt = prompt
        self.history = history
        self.use_news = use_news

    def run(self):
        if not self.use_news:
            self._run_llm(self.prompt)
            return

        topic = self.prompt
        for phrase in ["will there be", "will it be", "will there", "is there going to be",
                       "is it going to be", "will we have", "will we see", "going to be",
                       "second season", "new season", "next season", "release date",
                       "any new", "any upcoming", "when is", "when will", "coming out",
                       "will it rain", "will it snow", "out yet", "just released",
                       "just announced", "latest on", "season 2", "season 3",
                       "renewed", "cancelled", "canceled"]:
            topic = topic.replace(phrase, "").strip()

        context_holder = {}
        def _fetch():
            context_holder["ctx"] = fetch_context(topic)

        news_thread = threading.Thread(target=_fetch, daemon=True)
        news_thread.start()
        news_thread.join(timeout=5)

        context = context_holder.get("ctx", "")
        if context:
            augmented_prompt = (
                f"REAL-TIME DATA (fetched right now):\n{context}\n\n"
                f"Question: {self.prompt}\n\n"
                f"Answer based on the data provided. Be concise and direct."
            )
        else:
            augmented_prompt = self.prompt

        self._run_llm(augmented_prompt)

    def _run_llm(self, augmented_prompt):
        history_text = "\n".join(self.history[:-1])
        full_prompt = f"{SYSTEM_PROMPT}\n\n{history_text}\nUser: {augmented_prompt}\nJarvis:"
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama3.2:3b", "prompt": full_prompt, "stream": True},
                timeout=120,
                stream=True
            )
            full_response = ""
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    text = chunk.get("response", "")
                    if text:
                        self.token_received.emit(text)
                        full_response += text
                    if chunk.get("done"):
                        break
            self.finished.emit(full_response.strip())
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────
#  VOICE WORKER
# ─────────────────────────────────────────────────────────
class VoiceWorker(QThread):
    text_received = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self._frames = []
        self.SAMPLE_RATE = 16000

    def stop_recording(self):
        self._stop_event.set()

    def run(self):
        try:
            import sounddevice as sd
            import speech_recognition as sr
            import numpy as np
            import io
            import wave

            self._frames = []
            self._stop_event.clear()

            def callback(indata, frames, time, status):
                if not self._stop_event.is_set():
                    self._frames.append(indata.copy())

            with sd.InputStream(samplerate=self.SAMPLE_RATE, channels=1, dtype='int16', callback=callback):
                self._stop_event.wait(timeout=30)

            if not self._frames:
                self.error.emit("No audio recorded.")
                return

            audio_data = np.concatenate(self._frames, axis=0)
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.SAMPLE_RATE)
                wf.writeframes(audio_data.tobytes())
            wav_buffer.seek(0)

            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_buffer) as source:
                audio = recognizer.record(source)
            text = recognizer.recognize_google(audio)
            self.text_received.emit(text)

        except ImportError as e:
            self.error.emit(f"Missing library: {e}")
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────
#  ADVANCED PARTICLE SYSTEM
# ─────────────────────────────────────────────────────────
class HolographicParticle:
    def __init__(self, x, y, width, height):
        import random
        self.x = random.uniform(x, x + width)
        self.y = random.uniform(y, y + height)
        self.vx = random.uniform(-0.5, 0.5)
        self.vy = random.uniform(-0.8, -0.2)
        self.life = 1.0
        self.decay = random.uniform(0.008, 0.025)
        self.size = random.uniform(0.5, 2.0)
        self.hue = random.uniform(180, 210)
        self.rotation = random.uniform(0, 360)
        self.spin = random.uniform(-3, 3)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life = max(0, self.life - self.decay)
        self.vy -= 0.08
        self.vx *= 0.99
        self.rotation += self.spin

    def is_alive(self):
        return self.life > 0.01


class AdvancedParticleSystem:
    def __init__(self, count=PARTICLE_COUNT):
        self.particles = []
        self.spawn_count = count

    def update(self, scene_rect):
        for p in self.particles:
            if p.is_alive():
                p.update()

        alive_count = len([p for p in self.particles if p.is_alive()])
        while alive_count < self.spawn_count:
            import random
            x = random.uniform(scene_rect.x(), scene_rect.x() + scene_rect.width())
            y = scene_rect.y() + scene_rect.height()
            self.particles.append(HolographicParticle(x, y, 0, 0))
            alive_count += 1

    def draw(self, painter):
        for p in self.particles:
            if p.is_alive():
                alpha = int(255 * p.life)
                color = QColor.fromHsv(int(p.hue), 200, int(200 + 55 * p.life), alpha)
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)

                painter.save()
                painter.translate(p.x, p.y)
                painter.rotate(p.rotation)
                painter.drawEllipse(-p.size/2, -p.size/2, p.size, p.size)
                painter.restore()


# ───────────────────────────────────────────────��─────────
#  HOLOGRAPHIC BACKGROUND
# ─────────────────────────────────────────────────────────
class HolographicBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._offset = 0
        self._pulse_time = 0
        self._glitch_offset = 0
        self.particle_system = AdvancedParticleSystem(PARTICLE_COUNT)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(1000 // ANIMATION_FPS)

    def _animate(self):
        self._offset = (self._offset + 2) % 60
        self._pulse_time = (self._pulse_time + 1) % 360
        self._glitch_offset = (self._glitch_offset + 1) % 100
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.particle_system.update(self.rect())
        self.particle_system.draw(painter)

        pen = QPen(QColor(0, 212, 255, 10), 0.5)
        painter.setPen(pen)
        step = 40
        x = self._offset % step
        while x < self.width():
            alpha_val = int(10 + 6 * math.sin(math.radians(self._pulse_time + x/2)))
            pen.setColor(QColor(0, 212, 255, max(3, alpha_val)))
            painter.setPen(pen)
            painter.drawLine(int(x), 0, int(x), self.height())
            x += step

        y = self._offset % step
        while y < self.height():
            alpha_val = int(10 + 6 * math.sin(math.radians(self._pulse_time + y/2)))
            pen.setColor(QColor(0, 212, 255, max(3, alpha_val)))
            painter.setPen(pen)
            painter.drawLine(0, int(y), self.width(), int(y))
            y += step

        scanline_pen = QPen(QColor(0, 0, 0, 12), 1)
        painter.setPen(scanline_pen)
        for y in range(0, self.height(), 2):
            flicker = 12 if (self._glitch_offset + y) % 20 < 10 else 5
            scanline_pen.setColor(QColor(0, 0, 0, flicker))
            painter.setPen(scanline_pen)
            painter.drawLine(0, y, self.width(), y)


# ─────────────────────────────────────────────────────────
#  ANIMATED ARC REACTOR
# ─────────────────────────────────────────────────────────
class AnimatedArcReactor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 240)
        self._angle = 0
        self._pulse = 0
        self._state = "idle"
        self._data_streams = [0, 0, 0]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(1000 // ANIMATION_FPS)

    def set_state(self, state):
        self._state = state

    def _animate(self):
        self._angle = (self._angle + 2.5) % 360
        self._pulse = (self._pulse + 3) % 360
        for i in range(len(self._data_streams)):
            self._data_streams[i] = (self._data_streams[i] + (i+1)*1.5) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))

        cx = self.width() / 2
        cy = self.height() / 2
        r = min(cx, cy) - 15

        if self._state == "listening":
            core_color = QColor(0, 255, 136)
            ring_color = QColor(0, 255, 136)
        elif self._state == "responding":
            core_color = QColor(0, 180, 255)
            ring_color = QColor(0, 180, 255)
        else:
            core_color = QColor(0, 212, 255)
            ring_color = QColor(0, 212, 255)

        for i in range(3):
            glow_pen = QPen(QColor(ring_color.red(), ring_color.green(), ring_color.blue(), 40), 2)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            offset = i * 90 + self._angle * (1 + i * 0.15)
            r_offset = r - i * 15
            painter.drawArc(
                int(cx - r_offset), int(cy - r_offset),
                int(r_offset * 2), int(r_offset * 2),
                int(offset * 16), int(100 * 16)
            )

            ring_pen = QPen(ring_color, 1.5)
            painter.setPen(ring_pen)
            painter.drawArc(
                int(cx - r_offset), int(cy - r_offset),
                int(r_offset * 2), int(r_offset * 2),
                int(offset * 16), int(100 * 16)
            )

        pulse_scale = 0.6 + 0.4 * math.sin(math.radians(self._pulse))
        inner_r = r * 0.32 * pulse_scale

        grad = QRadialGradient(int(cx), int(cy), int(inner_r * 2.5))
        grad.setColorAt(0, QColor(core_color.red(), core_color.green(), core_color.blue(), 130))
        grad.setColorAt(0.5, QColor(core_color.red(), core_color.green(), core_color.blue(), 40))
        grad.setColorAt(1, QColor(core_color.red(), core_color.green(), core_color.blue(), 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(core_color, 1.5))
        painter.drawEllipse(QPointF(cx, cy), inner_r, inner_r)

        painter.setBrush(QBrush(core_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 4, 4)


# ─────────────────────────────────────────────────────────
#  TYPING INDICATOR
# ─────────────────────────────────────────────────────────
class TypingIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self._dots = [0.3, 0.3, 0.3]
        self._step = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.hide()

    def start(self):
        self.show()
        self.timer.start(150)

    def stop(self):
        self.timer.stop()
        self.hide()

    def _animate(self):
        self._step = (self._step + 1) % 3
        for i in range(3):
            self._dots[i] = 1.0 if i == self._step else 0.3
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = 5
        gap = 18
        x = 28
        y = self.height() // 2
        for i, alpha in enumerate(self._dots):
            glow_color = QColor(0, 212, 255, int(80 * alpha))
            painter.setBrush(QBrush(glow_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(x, y), r * alpha + 2.5, r * alpha + 2.5)

            color = QColor(0, 212, 255, int(220 * alpha))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(x, y), r * alpha, r * alpha)
            x += r * 2 + gap


# ─────────────────────────────────────────────────────────
#  HOLOGRAPHIC CHAT BUBBLE
# ─────────────────────────────────────────────────────────
class HolographicBubble(QFrame):
    def __init__(self, text, is_user=True, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self._full_text = text
        self._build(text)

    def _build(self, text):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)
        outer.setSpacing(2)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(12, 0, 12, 0)
        ts = datetime.now().strftime("%H:%M")
        ts_label = QLabel(ts)
        ts_label.setFont(QFont("Courier New", 8))
        ts_label.setStyleSheet("color: rgba(0,212,255,90);")

        copy_btn = QPushButton("⎘")
        copy_btn.setFixedSize(22, 18)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(0,212,255,110);
                border: none;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { color: #00D4FF; }
        """)
        copy_btn.clicked.connect(self._copy_text)

        if self.is_user:
            meta_row.addStretch()
            meta_row.addWidget(copy_btn)
            meta_row.addWidget(ts_label)
        else:
            meta_row.addWidget(ts_label)
            meta_row.addWidget(copy_btn)
            meta_row.addStretch()
        outer.addLayout(meta_row)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setFont(QFont("Courier New", 11))
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.label.setMaximumWidth(650)

        if self.is_user:
            self.label.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 100, 220, 90),
                    stop:1 rgba(0, 40, 150, 130));
                color: #FFFFFF;
                border: 2px solid rgba(0, 212, 255, 210);
                border-radius: 20px;
                padding: 12px 18px;
            """)
            row.addStretch()
            row.addWidget(self.label)
        else:
            self.label.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 20, 60, 160),
                    stop:1 rgba(0, 40, 100, 120));
                color: #00D4FF;
                border: 2px solid rgba(0, 212, 255, 160);
                border-radius: 20px;
                padding: 12px 18px;
            """)
            row.addWidget(self.label)
            row.addStretch()
        outer.addLayout(row)

    def append_text(self, text):
        self._full_text += text
        self.label.setText(self._full_text)

    def _copy_text(self):
        QApplication.clipboard().setText(self._full_text)


# ─────────────────────────────────────────────────────────
#  COLLAPSIBLE HISTORY PANEL
# ─────────────────────────────────────────────────────────
class CollapsibleHistoryPanel(QWidget):
    chat_selected = pyqtSignal(str)
    chat_deleted = pyqtSignal(str)
    new_chat = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self._all_items = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.toggle_btn = QPushButton("◀ SESSIONS")
        self.toggle_btn.setFixedHeight(42)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 212, 255, 50),
                    stop:1 rgba(0, 150, 255, 30));
                color: #00D4FF;
                border: 2px solid rgba(0, 212, 255, 180);
                border-radius: 8px;
                font-family: 'Courier New';
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 2px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 212, 255, 80),
                    stop:1 rgba(0, 150, 255, 60));
                border-color: #00D4FF;
            }
        """)
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        self.content_panel = QWidget()
        content_layout = QVBoxLayout(self.content_panel)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(8)

        title = QLabel("SESSIONS")
        title.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        title.setStyleSheet("color: rgba(0,212,255,180); letter-spacing: 2px;")
        content_layout.addWidget(title)

        self.search = QLineEdit()
        self.search.setPlaceholderText("SEARCH...")
        self.search.setFixedHeight(30)
        self.search.setFont(QFont("Courier New", 9))
        self.search.setStyleSheet("""
            QLineEdit {
                background-color: rgba(0,212,255,12);
                color: #00D4FF;
                border: 1px solid rgba(0,212,255,80);
                border-radius: 5px;
                padding: 0 8px;
                font-weight: bold;
            }
            QLineEdit:focus { border-color: rgba(0,212,255,180); background-color: rgba(0,212,255,20); }
        """)
        self.search.textChanged.connect(self._filter)
        content_layout.addWidget(self.search)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: rgba(0, 10, 30, 140);
                border: 1px solid rgba(0, 212, 255, 50);
                border-radius: 5px;
                outline: none;
            }
            QListWidget::item {
                color: rgba(0,212,255,170);
                font-family: 'Courier New';
                font-size: 10px;
                padding: 6px 8px;
                border-radius: 3px;
                margin: 1px;
                border: 1px solid transparent;
            }
            QListWidget::item:selected {
                background-color: rgba(0,212,255,35);
                color: #00D4FF;
                border: 1px solid rgba(0,212,255,120);
            }
            QListWidget::item:hover {
                background-color: rgba(0,212,255,15);
                border: 1px solid rgba(0,212,255,60);
            }
        """)
        self.list_widget.itemClicked.connect(self._on_select)
        content_layout.addWidget(self.list_widget)

        new_btn = QPushButton("＋ NEW")
        new_btn.setFixedHeight(32)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 212, 255, 25);
                color: #00D4FF;
                border: 1px solid rgba(0, 212, 255, 100);
                border-radius: 5px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(0, 212, 255, 50); border-color: #00D4FF; }
        """)
        new_btn.clicked.connect(self.new_chat.emit)
        content_layout.addWidget(new_btn)

        del_btn = QPushButton("⌫ DELETE")
        del_btn.setFixedHeight(32)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 59, 48, 20);
                color: #FF6B6B;
                border: 1px solid rgba(255, 59, 48, 80);
                border-radius: 5px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(255, 59, 48, 40); color: #FF3B30; border-color: #FF3B30; }
        """)
        del_btn.clicked.connect(self._on_delete)
        content_layout.addWidget(del_btn)

        self.content_panel.setStyleSheet("""
            background-color: rgba(0, 15, 40, 180);
            border: 1px solid rgba(0, 212, 255, 80);
            border-radius: 8px;
        """)
        self.content_panel.setMaximumWidth(220)
        self.content_panel.hide()

        layout.addWidget(self.content_panel)
        layout.addStretch()

    def _toggle(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.toggle_btn.setText("▶ SESSIONS")
            self.content_panel.hide()
        else:
            self.toggle_btn.setText("◀ SESSIONS")
            self.content_panel.show()

    def refresh(self):
        self.list_widget.clear()
        self._all_items = []
        for fname in list_saved_chats():
            try:
                ts = fname.replace("chat_", "").replace(".json", "")
                dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
                label = dt.strftime("%b %d  %H:%M")
            except Exception:
                label = fname
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, fname)
            self._all_items.append((label.lower(), item))
            self.list_widget.addItem(item)

    def _filter(self, text):
        self.list_widget.clear()
        for label, item in self._all_items:
            if text.lower() in label:
                self.list_widget.addItem(item)

    def _on_select(self, item):
        fname = item.data(Qt.ItemDataRole.UserRole)
        self.chat_selected.emit(fname)

    def _on_delete(self):
        item = self.list_widget.currentItem()
        if item:
            fname = item.data(Qt.ItemDataRole.UserRole)
            self.chat_deleted.emit(fname)


# ─────────────────────────────────────────────────────────
#  TTS WORKER (pipelined synthesis + playback)
# ─────────────────────────────────────────────────────────
class TTSWorker(QThread):
    """
    Two-stage pipeline:
      Stage 1 (synth_thread)  — pulls text from sentence_queue, synthesizes to WAV file,
                                pushes filepath into _audio_queue
      Stage 2 (this thread)   — pulls filepaths from _audio_queue, plays them back-to-back
    """
    finished_speaking = pyqtSignal()

    def __init__(self, sentence_queue, stop_event):
        super().__init__()
        self.sentence_queue = sentence_queue
        self.stop_event = stop_event
        self._audio_queue = queue.Queue()

    def run(self):
        def synthesizer():
            while not self.stop_event.is_set():
                try:
                    sentence = self.sentence_queue.get(timeout=0.2)
                    if sentence is None:
                        self._audio_queue.put(None)
                        break
                    path = speak_with_piper(sentence)
                    if not path:
                        path = _speak_system_to_file(sentence)
                    if path:
                        self._audio_queue.put(path)
                except queue.Empty:
                    continue

        synth_thread = threading.Thread(target=synthesizer, daemon=True)
        synth_thread.start()

        while not self.stop_event.is_set():
            try:
                path = self._audio_queue.get(timeout=0.3)
                if path is None:
                    break
                _play_audio(path)
            except queue.Empty:
                continue

        synth_thread.join(timeout=5)
        self.finished_speaking.emit()


# ─────────────────────────────────────────────────────────
#  STREAMING LLM WORKER FOR VOICE
# ─────────────────────────────────────────────────────────
class VoiceLLMWorker(QThread):
    sentence_ready = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, prompt, history, use_news=False):
        super().__init__()
        self.prompt = prompt
        self.history = history
        self.use_news = use_news

    def run(self):
        import re
        context = ""
        if self.use_news:
            topic = self.prompt
            for phrase in ["will there be", "will it be", "second season", "new season",
                          "release date", "any new", "when is", "when will", "coming out"]:
                topic = topic.replace(phrase, "").strip()
            ctx_holder = {}
            def _fetch():
                ctx_holder["c"] = fetch_context(topic)
            t = threading.Thread(target=_fetch, daemon=True)
            t.start()
            t.join(timeout=5)
            context = ctx_holder.get("c", "")

        if context:
            augmented = f"REAL-TIME DATA:\n{context}\n\nQuestion: {self.prompt}\n\nAnswer now:"
        else:
            augmented = self.prompt

        history_text = "\n".join(self.history[:-1])
        full_prompt = f"{SYSTEM_PROMPT}\n\n{history_text}\nUser: {augmented}\nJarvis:"

        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama3.2:3b", "prompt": full_prompt, "stream": True},
                timeout=120,
                stream=True
            )
            full_response = ""
            buffer = ""
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    text = chunk.get("response", "")
                    if text:
                        full_response += text
                        buffer += text
                        sentences = re.split(r'(?<=[.!?])\s+', buffer)
                        for s in sentences[:-1]:
                            s = s.strip()
                            if s:
                                self.sentence_ready.emit(s)
                        buffer = sentences[-1]
                    if chunk.get("done"):
                        break
            if buffer.strip():
                self.sentence_ready.emit(buffer.strip())
            self.finished.emit(full_response.strip())
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────
#  VOICE CHAT OVERLAY
# ─────────────────────────────────────────────────────────
class VoiceChatOverlay(QWidget):
    transcript_ready = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.showFullScreen()

        self._state = "idle"
        self._last_user = ""
        self._last_jarvis = ""
        self.voice_worker = None
        self.tts_worker = None
        self.llm_worker = None
        self.conv_history = []
        self._sentence_queue = None
        self._tts_stop = None

        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        bg = QWidget()
        bg.setStyleSheet("background-color: rgba(1, 6, 16, 250);")
        bg_layout = QVBoxLayout(bg)
        bg_layout.setContentsMargins(40, 40, 40, 40)
        bg_layout.setSpacing(25)

        top = QHBoxLayout()
        title = QLabel("J.A.R.V.I.S  ///  VOICE MODE")
        title.setFont(QFont("Courier New", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #00D4FF; letter-spacing: 4px;")
        close_btn = QPushButton("✕ EXIT")
        close_btn.setFixedSize(100, 34)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 59, 48, 35);
                color: #FF6B6B;
                border: 2px solid rgba(255, 59, 48, 140);
                border-radius: 6px;
                font-family: 'Courier New';
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(255, 59, 48, 70); color: #FF3B30; }
        """)
        close_btn.clicked.connect(self.close)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(close_btn)
        bg_layout.addLayout(top)

        arc_container = QWidget()
        arc_layout = QVBoxLayout(arc_container)
        arc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.arc = AnimatedArcReactor()
        self.arc.setFixedSize(320, 320)
        arc_layout.addWidget(self.arc)
        bg_layout.addWidget(arc_container)

        self.state_label = QLabel("TAP TO SPEAK")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_label.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self.state_label.setStyleSheet("color: rgba(0,212,255,190); letter-spacing: 3px;")
        bg_layout.addWidget(self.state_label)

        self.transcript_label = QLabel("")
        self.transcript_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.transcript_label.setWordWrap(True)
        self.transcript_label.setFont(QFont("Courier New", 12))
        self.transcript_label.setStyleSheet("color: rgba(224,247,255,170); padding: 0 60px;")
        self.transcript_label.setMaximumHeight(120)
        bg_layout.addWidget(self.transcript_label)

        bg_layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speak_btn = QPushButton("🎤  SPEAK")
        self.speak_btn.setFixedSize(180, 64)
        self.speak_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.speak_btn.setStyleSheet(self._speak_btn_style())
        self.speak_btn.clicked.connect(self._on_speak_btn)
        self.speak_btn.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        btn_row.addWidget(self.speak_btn)
        bg_layout.addLayout(btn_row)
        bg_layout.addSpacing(30)

        root.addWidget(bg)

    def _speak_btn_style(self, active=False):
        if active:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(255, 59, 48, 160),
                        stop:1 rgba(255, 80, 60, 130));
                    color: #FFFFFF;
                    border: 2px solid rgba(255, 59, 48, 240);
                    border-radius: 32px;
                    font-weight: bold;
                    letter-spacing: 1px;
                }
                QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255, 80, 60, 200),
                    stop:1 rgba(255, 120, 100, 170)); }
            """
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 120, 220, 140),
                    stop:1 rgba(0, 70, 170, 110));
                color: #FFFFFF;
                border: 2px solid rgba(0, 212, 255, 240);
                border-radius: 32px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(0, 150, 255, 180),
                stop:1 rgba(0, 100, 210, 150)); }
        """

    def _set_state(self, state):
        self._state = state
        self.arc.set_state(state)
        if state == "listening":
            self.state_label.setText("●● LISTENING ●●")
            self.state_label.setStyleSheet("color: #00FF88; letter-spacing: 3px; font-weight: bold;")
            self.speak_btn.setText("⏹  STOP")
            self.speak_btn.setStyleSheet(self._speak_btn_style(active=True))
        elif state == "responding":
            self.state_label.setText("●● PROCESSING ●●")
            self.state_label.setStyleSheet("color: #00D4FF; letter-spacing: 3px; font-weight: bold;")
            self.speak_btn.setText("🎤  SPEAK")
            self.speak_btn.setStyleSheet(self._speak_btn_style())
            self.speak_btn.setEnabled(False)
        else:
            self.state_label.setText("TAP TO SPEAK")
            self.state_label.setStyleSheet("color: rgba(0,212,255,190); letter-spacing: 3px;")
            self.speak_btn.setText("🎤  SPEAK")
            self.speak_btn.setStyleSheet(self._speak_btn_style())
            self.speak_btn.setEnabled(True)

    def _on_speak_btn(self):
        if self._state == "listening":
            if self.voice_worker and self.voice_worker.isRunning():
                self.voice_worker.stop_recording()
        elif self._state == "idle":
            self._start_listening()

    def _start_listening(self):
        self._set_state("listening")
        self.voice_worker = VoiceWorker()
        self.voice_worker.text_received.connect(self._on_user_speech)
        self.voice_worker.error.connect(self._on_voice_error)
        self.voice_worker.start()

    def _on_user_speech(self, text):
        self._last_user = text
        self.transcript_label.setText(f"You: {text}")
        self._set_state("responding")
        self.conv_history.append(f"User: {text}")

        self._sentence_queue = queue.Queue()
        self._tts_stop = threading.Event()
        self.tts_worker = TTSWorker(self._sentence_queue, self._tts_stop)
        self.tts_worker.finished_speaking.connect(self._on_tts_done)
        self.tts_worker.start()

        use_news = needs_realtime(text.lower())
        self.llm_worker = VoiceLLMWorker(text, list(self.conv_history), use_news=use_news)
        self.llm_worker.sentence_ready.connect(self._on_sentence)
        self.llm_worker.finished.connect(self._on_llm_response)
        self.llm_worker.error.connect(self._on_llm_error)
        self.llm_worker.start()

    def _on_sentence(self, sentence):
        if self._sentence_queue:
            self._sentence_queue.put(sentence)
        current = self.transcript_label.text()
        if current.startswith("You:"):
            self.transcript_label.setText(f"Jarvis: {sentence}")
        else:
            preview = (current + " " + sentence)[-160:]
            self.transcript_label.setText(preview)

    def _on_llm_response(self, response):
        self._last_jarvis = response
        self.conv_history.append(f"Jarvis: {response}")
        if self._sentence_queue:
            self._sentence_queue.put(None)
        self.transcript_ready.emit(self._last_user, response)

    def _on_tts_done(self):
        self._set_state("idle")

    def _on_voice_error(self, error):
        self.transcript_label.setText(f"Error: {error}")
        if self._tts_stop:
            self._tts_stop.set()
        self._set_state("idle")

    def _on_llm_error(self, error):
        self.transcript_label.setText("Connection error. Is Ollama running?")
        if self._sentence_queue:
            self._sentence_queue.put(None)
        self._set_state("idle")


# ─────────────────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────────────────
class JarvisHolographicWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.conversation_history = []
        self.current_bubble = None
        self.worker = None
        self.warmup_worker = None
        self.current_filename = None
        self._model_ready = False
        self._deleted = False
        self._setup_window()
        self._setup_ui()
        self._warmup_model()
        self._greet()

    def _setup_window(self):
        self.setWindowTitle("J.A.R.V.I.S - HOLOGRAPHIC INTERFACE v2.0")
        self.setMinimumSize(1280, 900)
        self.resize(1500, 950)
        self.setStyleSheet("background-color: #010810;")

    def _setup_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)

        self.history_panel = CollapsibleHistoryPanel()
        self.history_panel.new_chat.connect(self._new_chat)
        self.history_panel.chat_selected.connect(self._load_chat)
        self.history_panel.chat_deleted.connect(self._delete_chat)
        self.history_panel.refresh()

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(25, 25, 25, 25)
        center_layout.setSpacing(18)

        header = QHBoxLayout()
        title = QLabel("J.A.R.V.I.S")
        title.setFont(QFont("Courier New", 28, QFont.Weight.Bold))
        title.setStyleSheet("color: #00D4FF; letter-spacing: 6px;")

        header.addWidget(title)
        header.addStretch()

        self.status_label = QLabel("● SYSTEM ONLINE")
        self.status_label.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        self.status_label.setStyleSheet("color: #00FF88; letter-spacing: 2px;")

        voice_btn = QPushButton("🎙️ VOICE")
        voice_btn.setFixedSize(120, 34)
        voice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        voice_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 212, 255, 50),
                    stop:1 rgba(0, 150, 200, 30));
                color: #00D4FF;
                border: 1px solid rgba(0, 212, 255, 160);
                border-radius: 6px;
                font-family: 'Courier New';
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(0, 212, 255, 100),
                stop:1 rgba(0, 150, 200, 80));
                border-color: #00D4FF; }
        """)
        voice_btn.clicked.connect(self._open_voice_chat)

        save_btn = QPushButton("[ SAVE ]")
        save_btn.setFixedSize(90, 34)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(0, 212, 255, 150);
                border: 1px solid rgba(0, 212, 255, 70);
                border-radius: 4px;
                font-family: 'Courier New';
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(0, 212, 255, 15); color: #00D4FF; border-color: #00D4FF; }
        """)
        save_btn.clicked.connect(self._save_chat)

        clear_btn = QPushButton("[ CLEAR ]")
        clear_btn.setFixedSize(90, 34)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(0, 212, 255, 150);
                border: 1px solid rgba(0, 212, 255, 70);
                border-radius: 4px;
                font-family: 'Courier New';
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(0, 212, 255, 15); color: #00D4FF; border-color: #00D4FF; }
        """)
        clear_btn.clicked.connect(self._clear_chat)

        header.addWidget(self.status_label)
        header.addSpacing(8)
        header.addWidget(voice_btn)
        header.addSpacing(6)
        header.addWidget(save_btn)
        header.addSpacing(6)
        header.addWidget(clear_btn)
        center_layout.addLayout(header)

        arc_container = QWidget()
        arc_layout = QVBoxLayout(arc_container)
        arc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.arc_reactor = AnimatedArcReactor()
        self.arc_reactor.setFixedSize(220, 220)
        arc_layout.addWidget(self.arc_reactor)
        center_layout.addWidget(arc_container)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical { width: 5px; background: transparent; }
            QScrollBar::handle:vertical {
                background: rgba(0, 212, 255, 120);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: rgba(0, 212, 255, 200); }
        """)

        self.chat_widget = QWidget()
        self.chat_widget.setStyleSheet("background-color: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setContentsMargins(12, 12, 12, 12)
        self.chat_layout.setSpacing(8)
        self.chat_layout.addStretch()
        scroll.setWidget(self.chat_widget)

        self.typing_indicator = TypingIndicator()

        chat_container = QVBoxLayout()
        chat_container.addWidget(scroll)
        chat_container.addWidget(self.typing_indicator)
        center_layout.addLayout(chat_container)

        char_row = QHBoxLayout()
        self.char_count = QLabel("0 / 500")
        self.char_count.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self.char_count.setStyleSheet("color: rgba(0,212,255,70);")
        char_row.addStretch()
        char_row.addWidget(self.char_count)
        center_layout.addLayout(char_row)

        input_frame = QFrame()
        input_frame.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(0, 30, 80, 170),
                stop:1 rgba(0, 20, 60, 150));
            border: 1px solid rgba(0, 212, 255, 160);
            border-radius: 10px;
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 8, 8, 8)
        input_layout.setSpacing(8)

        prompt_label = QLabel(">_")
        prompt_label.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        prompt_label.setStyleSheet("color: #00D4FF;")

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("ENTER COMMAND...")
        self.input_field.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        self.input_field.setFixedHeight(44)
        self.input_field.setMaxLength(500)
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: #00D4FF;
                border: none;
                padding: 0 8px;
                selection-background-color: rgba(0, 212, 255, 100);
            }
            QLineEdit:focus { outline: none; }
        """)
        self.input_field.returnPressed.connect(self._send)
        self.input_field.textChanged.connect(self._update_char_count)

        self.send_btn = QPushButton("SEND ▶")
        self.send_btn.setFixedSize(110, 44)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 140, 255, 160),
                    stop:1 rgba(0, 90, 210, 140));
                color: #FFFFFF;
                border: 1px solid rgba(0, 212, 255, 200);
                border-radius: 8px;
                font-family: 'Courier New';
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 170, 255, 200),
                    stop:1 rgba(0, 120, 240, 180));
            }
            QPushButton:disabled {
                background-color: rgba(0, 212, 255, 25);
                color: rgba(0, 212, 255, 50);
            }
        """)
        self.send_btn.clicked.connect(self._send)

        input_layout.addWidget(prompt_label)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        center_layout.addWidget(input_frame)

        self.holo_bg = HolographicBackground()
        self.holo_bg.lower()

        root.addWidget(self.history_panel)
        root.addWidget(center)

        main_stack = QWidget()
        stack_layout = QVBoxLayout(main_stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.addWidget(self.holo_bg)
        stack_layout.addWidget(central)

        self.setCentralWidget(main_stack)

    def _warmup_model(self):
        self.warmup_worker = ModelWarmupWorker()
        self.warmup_worker.warmup_complete.connect(self._on_warmup_complete)
        self.warmup_worker.start()

    def _on_warmup_complete(self):
        self._model_ready = True

    def _greet(self):
        self._add_bubble("JARVIS ONLINE. Systems initialized. How may I assist you?", is_user=False)

    def _add_bubble(self, text, is_user=True):
        bubble = HolographicBubble(text, is_user=is_user)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self._scroll_to_bottom()
        return bubble

    def _scroll_to_bottom(self):
        QApplication.processEvents()

    def _update_char_count(self, text):
        count = len(text)
        self.char_count.setText(f"{count} / 500")
        if count > 400:
            self.char_count.setStyleSheet("color: rgba(255,59,48,160);")
        elif count > 300:
            self.char_count.setStyleSheet("color: rgba(255,159,0,160);")
        else:
            self.char_count.setStyleSheet("color: rgba(0,212,255,70);")

    def _set_thinking(self, thinking):
        self.send_btn.setEnabled(not thinking)
        self.input_field.setEnabled(not thinking)
        if thinking:
            self.typing_indicator.start()
            self.arc_reactor.set_state("responding")
            self.status_label.setText("● PROCESSING...")
            self.status_label.setStyleSheet("color: #FF9500; letter-spacing: 2px; font-weight: bold;")
        else:
            self.typing_indicator.stop()
            self.arc_reactor.set_state("idle")
            self.status_label.setText("● SYSTEM ONLINE")
            self.status_label.setStyleSheet("color: #00FF88; letter-spacing: 2px; font-weight: bold;")

    def _send(self):
        text = self.input_field.text().strip()
        if not text or (self.worker and self.worker.isRunning()):
            return

        self.input_field.clear()
        self._add_bubble(text, is_user=True)
        self.conversation_history.append(f"User: {text}")

        if text.lower() in ["exit", "quit", "stop"]:
            self._add_bubble("Shutting down. Until next time.", is_user=False)
            return

        self._set_thinking(True)
        realtime = needs_realtime(text.lower())

        self.current_bubble = self._add_bubble("", is_user=False)
        self.worker = JarvisWorker(text, list(self.conversation_history), use_news=realtime)
        self.worker.token_received.connect(self._on_token)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_token(self, token):
        if self.current_bubble:
            self.current_bubble.append_text(token)
            self._scroll_to_bottom()

    def _on_finished(self, full_response):
        self.conversation_history.append(f"Jarvis: {full_response}")
        if len(self.conversation_history) > 40:
            self.conversation_history = self.conversation_history[-40:]
        if self.conversation_history and not self._deleted:
            self.current_filename = save_chat(self.conversation_history, self.current_filename)
            self.history_panel.refresh()
        self._deleted = False
        self._set_thinking(False)
        self.input_field.setFocus()

    def _on_error(self, error_msg):
        if self.current_bubble:
            self.current_bubble.append_text(f"\nERROR: {error_msg}")
        self._set_thinking(False)

    def _save_chat(self):
        if not self.conversation_history:
            return
        self.current_filename = save_chat(self.conversation_history, self.current_filename)
        self.history_panel.refresh()

    def _new_chat(self):
        if self.conversation_history:
            self.current_filename = save_chat(self.conversation_history, self.current_filename)
            self.history_panel.refresh()
        self.conversation_history.clear()
        self.current_filename = None
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._greet()

    def _load_chat(self, filename):
        if self.conversation_history:
            save_chat(self.conversation_history, self.current_filename)
            self.history_panel.refresh()
        try:
            messages = load_chat(filename)
            self.conversation_history = messages
            self.current_filename = filename
            while self.chat_layout.count() > 1:
                item = self.chat_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for msg in messages:
                if msg.startswith("User: "):
                    self._add_bubble(msg[6:], is_user=True)
                elif msg.startswith("Jarvis: "):
                    self._add_bubble(msg[8:], is_user=False)
        except Exception as e:
            self._add_bubble(f"Failed to load chat: {e}", is_user=False)

    def _delete_chat(self, filename):
        delete_chat(filename)
        if self.current_filename == filename:
            self._deleted = True
            self.current_filename = None
            self.conversation_history.clear()
            while self.chat_layout.count() > 1:
                item = self.chat_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._add_bubble("Chat deleted. Starting fresh.", is_user=False)
        self.history_panel.refresh()

    def _clear_chat(self):
        self.conversation_history.clear()
        self.current_filename = None
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._add_bubble("MEMORY WIPED. Systems reset.", is_user=False)

    def _open_voice_chat(self):
        self.voice_chat_overlay = VoiceChatOverlay(self)
        self.voice_chat_overlay.transcript_ready.connect(self._on_voice_chat_transcript)
        self.voice_chat_overlay.show()

    def _on_voice_chat_transcript(self, user_text, jarvis_text):
        self.conversation_history.append(f"User: {user_text}")
        self.conversation_history.append(f"Jarvis: {jarvis_text}")
        self._add_bubble(user_text, is_user=True)
        self._add_bubble(jarvis_text, is_user=False)
        self.current_filename = save_chat(self.conversation_history, self.current_filename)
        self.history_panel.refresh()

    def closeEvent(self, event):
        if self.conversation_history:
            save_chat(self.conversation_history, self.current_filename)
        event.accept()


# ─────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(1, 8, 16))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 212, 255))
    app.setPalette(palette)
    window = JarvisHolographicWindow()
    window.show()
    sys.exit(app.exec())

