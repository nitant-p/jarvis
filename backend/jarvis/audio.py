import json
import subprocess
from pathlib import Path


class Transcriber:
    def __init__(self, settings):
        self.settings = settings

    def transcribe(self, source: Path):
        wav = source.with_suffix(".wav")
        output = source.with_suffix(".transcript")
        try:
            subprocess.run(
                [
                    self.settings.ffmpeg_bin,
                    "-nostdin",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(source),
                    "-t",
                    str(self.settings.max_recording_seconds + 1),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(wav),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
            import wave

            with wave.open(str(wav)) as audio:
                if audio.getnframes() / audio.getframerate() > self.settings.max_recording_seconds:
                    raise ValueError("Recording exceeds the two-minute limit")
                import array

                samples = array.array("h", audio.readframes(audio.getnframes()))
                if not samples or max(abs(x) for x in samples) < 100:
                    raise ValueError("No speech detected; please record again")
            subprocess.run(
                [
                    self.settings.whisper_bin,
                    "-m",
                    str(self.settings.whisper_model),
                    "-f",
                    str(wav),
                    "-l",
                    "en",
                    "-oj",
                    "-of",
                    str(output),
                    "-nt",
                ],
                check=True,
                capture_output=True,
                timeout=180,
            )
            result = json.loads(Path(str(output) + ".json").read_text())
            text = " ".join(x["text"].strip() for x in result.get("transcription", []))
            if not text.strip():
                raise ValueError("No speech detected; please record again")
            return text
        except FileNotFoundError as e:
            raise ValueError(
                "Install FFmpeg/whisper.cpp and configure the speech model; see setup guide"
            ) from e
        except subprocess.CalledProcessError as e:
            raise ValueError(
                "Audio decoding or transcription failed; check local model setup"
            ) from e
        finally:
            wav.unlink(missing_ok=True)
            Path(str(output) + ".json").unlink(missing_ok=True)
