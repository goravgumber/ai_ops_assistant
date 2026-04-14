"""Voice input/output handler with wake-word listening and text fallback support."""

from __future__ import annotations

import os
import queue
import re
import threading
import time
from typing import Any, Callable

from dotenv import load_dotenv

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover - environment-dependent
    sr = None

try:
    import pyttsx3
except ImportError:  # pragma: no cover - environment-dependent
    pyttsx3 = None

try:
    import pyaudio  # type: ignore  # pragma: no cover - optional runtime dependency
except ImportError:  # pragma: no cover - environment-dependent
    pyaudio = None

load_dotenv()


class SpeechHandler:
    """Manage speech recognition, text-to-speech, and voice-command workflows.

    The handler is designed to fail safely: if microphone or TTS dependencies are
    unavailable, input gracefully falls back to regular text input.
    """

    def __init__(self) -> None:
        """Initialize recognizer, TTS engine, queue state, and wake-word settings."""
        self.recognizer: Any = None
        self.engine: Any = None
        self.is_listening = False
        self.wake_word = "assistant"
        self.command_queue: queue.Queue[str] = queue.Queue()
        self.available = False

        try:
            if sr is None:
                raise ImportError("speech_recognition is not installed")
            if pyttsx3 is None:
                raise ImportError("pyttsx3 is not installed (voice features disabled in this environment)")
            if pyaudio is None:
                raise ImportError("pyaudio is not installed (voice features disabled in this environment)")

            self.recognizer = sr.Recognizer()
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", 150)
            self.engine.setProperty("volume", 0.9)

            self._set_english_voice()
            try:
                mic_names = sr.Microphone.list_microphone_names()
                if not mic_names:
                    print("Warning: No microphone detected. Falling back to text input.")
                    self.available = False
                    return
            except Exception:
                print("Warning: Microphone unavailable. Falling back to text input.")
                self.available = False
                return
            self.available = True
            print("🎤 Voice assistant initialized")
        except ImportError as exc:
            print(f"ℹ️  Voice features disabled: {exc}")
            self.available = False
        except Exception as exc:
            print(f"Warning: Voice assistant initialization failed: {exc}")
            self.available = False

    def _set_english_voice(self) -> None:
        """Select the first available English voice for text-to-speech output."""
        if not self.engine:
            return

        try:
            voices = self.engine.getProperty("voices") or []
            for voice in voices:
                sample = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".lower()
                if "en" in sample or "english" in sample:
                    self.engine.setProperty("voice", voice.id)
                    return
        except Exception as exc:
            print(f"Warning: Could not select English voice: {exc}")

    def listen_once(self, timeout: int = 10, phrase_limit: int = 15) -> str | None:
        """Capture a single microphone utterance and transcribe it to lowercase text.

        Args:
            timeout: Maximum seconds to wait for speech start.
            phrase_limit: Maximum seconds for captured speech phrase.

        Returns:
            Normalized transcribed text, or `None` when speech recognition fails.
        """
        if not self.available or sr is None or self.recognizer is None:
            return None

        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_limit,
                )

            text = self.recognizer.recognize_google(audio)
            return text.strip().lower()
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            print("🎤 Could not understand audio, please try again")
            return None
        except sr.RequestError:
            print("🎤 Speech service unavailable, switching to text input")
            return None
        except Exception as exc:
            print(f"Warning: Voice listening error: {exc}")
            return None

    def listen_for_wake_word(self) -> bool:
        """Listen for the configured wake word for up to 30 seconds.

        Returns:
            `True` if the wake word is detected, else `False` on timeout/unavailable.
        """
        if not self.available:
            return False

        print(f"👂 Listening for wake word '{self.wake_word}'...")
        start = time.time()
        while (time.time() - start) < 30:
            if self.is_listening is False and threading.current_thread().daemon:
                return False
            heard = self.listen_once(timeout=3, phrase_limit=3)
            if heard and self.wake_word in heard:
                return True
        return False

    def listen_for_command(self) -> str | None:
        """Prompt the user for a voice command and return transcribed text."""
        if not self.available:
            return None

        self.speak("I'm listening, what would you like to know?")
        return self.listen_once(timeout=15, phrase_limit=30)

    def speak(self, text: str) -> None:
        """Speak text using TTS, with cleanup, truncation, and print fallback.

        Args:
            text: Text to synthesize.
        """
        cleaned = self._clean_speech_text(text)
        if len(cleaned) > 500:
            cleaned = cleaned[:500].rstrip() + "...and more"

        try:
            if not self.available or not self.engine:
                print(cleaned)
                return
            self.engine.say(cleaned)
            self.engine.runAndWait()
        except Exception:
            print(cleaned)

    def _clean_speech_text(self, text: str) -> str:
        """Normalize text for speech by removing noisy JSON punctuation patterns."""
        cleaned = re.sub(r"[\{\}\[\]\"]", " ", text or "")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or "Task completed successfully"

    def speak_result_summary(self, result: dict[str, Any]) -> None:
        """Speak a short summary and number of data sources from a result payload.

        Args:
            result: Final response dictionary from the verifier.
        """
        summary = result.get("summary") if isinstance(result, dict) else None
        if not isinstance(summary, str) or not summary.strip():
            summary = "Task completed successfully"

        self.speak(summary)

        sources = result.get("data_sources", []) if isinstance(result, dict) else []
        source_count = len(sources) if isinstance(sources, list) else 0
        self.speak(f"Data sources used: {source_count}")

    def narrate_pipeline_start(self, task: str) -> None:
        """Speak a natural introduction when the pipeline begins."""
        if not self.available:
            return
        short_task = (task or "").strip()
        if len(short_task) > 60:
            short_task = short_task[:60].rstrip() + "..."
        self.speak(
            f"Starting task: {short_task}. "
            "I will plan, execute, and verify your request."
        )

    def narrate_planning_start(self) -> None:
        """Narrate when planner agent starts."""
        if not self.available:
            return
        self.speak(
            "Planning agent is analyzing your request "
            "and creating an execution strategy."
        )

    def narrate_plan_ready(self, step_count: int) -> None:
        """Narrate when plan is ready."""
        if not self.available:
            return
        self.speak(
            f"Plan ready with {step_count} steps. "
            "Starting execution now."
        )

    def narrate_step_start(self, step_num: int, total: int, tool: str, action: str) -> None:
        """Narrate each executor step at start."""
        if not self.available:
            return
        tool_speech = {
            "GitHubTool": "GitHub",
            "WeatherTool": "weather service",
            "NewsTool": "news service",
        }
        action_speech = {
            "search_repos": "searching repositories",
            "get_trending": "fetching trending repositories",
            "get_repo_info": "getting repository details",
            "get_current_weather": "fetching current weather",
            "get_forecast": "getting weather forecast",
            "get_top_headlines": "fetching top headlines",
            "search_news": "searching news articles",
        }
        self.speak(
            f"Step {step_num} of {total}. "
            f"Calling {tool_speech.get(tool, tool)} — {action_speech.get(action, action)}."
        )

    def narrate_step_complete(self, step_num: int, success: bool, from_cache: bool) -> None:
        """Narrate step completion outcome."""
        if not self.available:
            return
        if success and from_cache:
            self.speak(f"Step {step_num} complete from cache.")
        elif success:
            self.speak(f"Step {step_num} complete.")
        else:
            self.speak(
                f"Step {step_num} encountered an issue. "
                "Attempting recovery."
            )

    def narrate_self_healing(self, step_num: int) -> None:
        """Narrate self-healing attempt for a failed step."""
        if not self.available:
            return
        self.speak(
            f"Step {step_num} failed. "
            "Self-healing agent is finding an alternative approach."
        )

    def narrate_verification_start(self) -> None:
        """Narrate verifier start."""
        if not self.available:
            return
        self.speak(
            "All steps complete. "
            "Verification agent is now validating and formatting results."
        )

    def narrate_confidence(self, score: int, grade: str) -> None:
        """Narrate the verification confidence score."""
        if not self.available:
            return
        if score >= 80:
            self.speak(
                f"Results verified with {score} percent confidence. "
                f"Grade {grade}. Excellent quality data."
            )
        elif score >= 60:
            self.speak(
                f"Results verified with {score} percent confidence. "
                f"Grade {grade}."
            )
        else:
            self.speak(
                f"Results verified with {score} percent confidence. "
                "Some data may be incomplete."
            )

    def narrate_final_result(self, result: dict[str, Any]) -> None:
        """Speak a natural, human-like summary of the final result payload."""
        if not self.available:
            return

        speech_parts: list[str] = []
        if isinstance(result, dict) and result.get("summary"):
            speech_parts.append(str(result["summary"]))
        else:
            if isinstance(result, dict):
                for key, value in result.items():
                    lowered = key.lower()
                    if ("repo" in lowered or "github" in lowered) and isinstance(value, list) and value:
                        first_repo = value[0] if isinstance(value[0], dict) else {}
                        speech_parts.append(
                            f"The top repository is {first_repo.get('name', 'unknown')} "
                            f"with {int(first_repo.get('stars', 0) or 0):,} stars."
                        )
                        break

                for key, value in result.items():
                    if "weather" in key.lower() and isinstance(value, dict):
                        speech_parts.append(
                            f"The weather shows {value.get('temperature_c', '?')} degrees Celsius, "
                            f"{value.get('condition', 'conditions unknown')}."
                        )
                        break

                for key, value in result.items():
                    if ("news" in key.lower() or "headlines" in key.lower()) and isinstance(value, list) and value:
                        first_item = value[0] if isinstance(value[0], dict) else {}
                        speech_parts.append(
                            f"Top news: {first_item.get('title', 'No title available')}."
                        )
                        break

        if isinstance(result, dict) and "confidence_score" in result:
            speech_parts.append(f"Confidence score: {result['confidence_score']} percent.")

        final_text = " ".join(part.strip() for part in speech_parts if part.strip())
        if not final_text:
            final_text = "Task completed successfully."
        self.speak(final_text)

    def narrate_chain_step(self, step_num: int, total: int, task: str) -> None:
        """Narrate task chain progression."""
        if not self.available:
            return
        self.speak(
            f"Chain step {step_num} of {total}. "
            f"Now working on: {(task or '')[:50]}."
        )

    def narrate_chain_complete(self, completed: int, total: int) -> None:
        """Narrate task chain completion."""
        if not self.available:
            return
        self.speak(
            f"Task chain complete. "
            f"{completed} of {total} tasks executed successfully."
        )

    def start_continuous_listening(self, callback: Callable[[str], None]) -> None:
        """Start a daemon thread that loops wake-word detection and command capture.

        Args:
            callback: Function called each time a voice command is captured.
        """
        if not self.available:
            print("Warning: Voice mode unavailable; falling back to text input only.")
            return

        if self.is_listening:
            print("Warning: Continuous listening is already running.")
            return

        self.is_listening = True

        def _worker() -> None:
            while self.is_listening:
                detected = self.listen_for_wake_word()
                if not self.is_listening:
                    break

                if detected:
                    if os.name == "nt":
                        print("\a", end="")
                    else:
                        print("\a", end="", flush=True)
                    print("🔔 Wake word detected!")
                    command = self.listen_for_command()
                    if command:
                        self.command_queue.put(command)
                        try:
                            callback(command)
                        except Exception as exc:
                            print(f"Warning: Voice callback failed: {exc}")
                        self.speak("Processing your request")
                else:
                    time.sleep(0.2)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def stop_listening(self) -> None:
        """Stop continuous listening mode and speak a short farewell."""
        self.is_listening = False
        self.speak("Goodbye")
        print("🎤 Voice assistant stopped")

    def get_input(self, prompt_text: str, use_voice: bool = False, voice_prompt_text: str = "") -> str:
        """Get non-empty user input via voice when possible, otherwise text.

        Args:
            prompt_text: Prompt shown to the user for text fallback.
            use_voice: Whether to attempt voice input first.
            voice_prompt_text: Optional spoken prompt prior to voice capture.

        Returns:
            A non-empty command string.
        """
        while True:
            if use_voice and self.available:
                print(prompt_text)
                if voice_prompt_text:
                    self.speak(voice_prompt_text)
                spoken = self.listen_for_command()
                if spoken:
                    return spoken
                print("Voice failed, please type your command:")
                typed = input("> ").strip()
                if typed:
                    return typed
                continue

            typed = input(prompt_text).strip()
            if typed:
                return typed


speech_handler = SpeechHandler()


if __name__ == "__main__":
    """Run a basic visual self-test for voice input/output behavior."""

    def _callback(cmd: str) -> None:
        print(f"[callback] Received command: {cmd}")

    print("Voice self-test started")
    print(f"Voice available: {speech_handler.available}")

    speech_handler.speak("Voice system self-test. If you can hear this, text to speech is working.")

    one_shot = speech_handler.get_input("Type a command (or enable voice): ", use_voice=False)
    print(f"Captured input: {one_shot}")

    if speech_handler.available:
        print("Starting continuous listening demo for 5 seconds...")
        speech_handler.start_continuous_listening(_callback)
        time.sleep(5)
        speech_handler.stop_listening()
    else:
        print("Voice mode unavailable in this environment. Text fallback is active.")
