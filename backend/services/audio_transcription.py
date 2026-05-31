"""
Whisper audio transcription service
Supports OpenAI (whisper-1) and Groq (whisper-large-v3-turbo)
"""
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional
from openai import OpenAI
from groq import Groq


class AudioTranscriptionService:
    """Service for transcribing audio using Whisper API"""

    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.audio_dir = Path("../storage/audio")
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.subtitle_dir = Path("../storage/subtitles")
        self.subtitle_dir.mkdir(parents=True, exist_ok=True)

    def extract_audio_from_video(self, video_path: str, video_id: str) -> str:
        """
        Extract audio from video file using ffmpeg

        Args:
            video_path: Path to video file
            video_id: Video ID for naming

        Returns:
            Path to extracted audio file
        """
        audio_path = self.audio_dir / f"{video_id}.mp3"

        # -ar 16000: 16kHz sample rate (optimal for Whisper)
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',
            '-acodec', 'libmp3lame',
            '-ar', '16000',
            '-ac', '1',
            '-b:a', '64k',
            '-y',
            str(audio_path)
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return str(audio_path)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to extract audio: {e.stderr.decode()}")
        except FileNotFoundError:
            raise Exception("ffmpeg not found. Please install ffmpeg to use audio transcription.")

    def transcribe_audio(
        self,
        audio_path: str,
        api_key: Optional[str] = None,
        language: Optional[str] = None,
        provider: str = "openai"
    ) -> Dict:
        """
        Transcribe audio using Whisper API

        Args:
            audio_path: Path to audio file
            api_key: API key (falls back to OPENAI_API_KEY / GROQ_API_KEY env var)
            language: Language code (e.g., 'en', 'zh', 'ja'). Auto-detect if None.
            provider: "openai" or "groq"

        Returns:
            Dict with transcription text and segments
        """
        try:
            if provider == "groq":
                return self._transcribe_with_groq(audio_path, api_key, language)
            else:
                return self._transcribe_with_openai(audio_path, api_key, language)
        except Exception as e:
            raise Exception(f"Whisper transcription failed: {str(e)}")

    def _transcribe_with_openai(
        self,
        audio_path: str,
        api_key: Optional[str],
        language: Optional[str]
    ) -> Dict:
        used_api_key = api_key or self.openai_api_key
        if not used_api_key:
            raise Exception("OpenAI API key is required. Provide it in the UI or set OPENAI_API_KEY in backend/.env")

        client = OpenAI(api_key=used_api_key)
        with open(audio_path, 'rb') as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                language=language
            )

        return {
            'text': transcription.text,
            'language': transcription.language,
            'duration': transcription.duration,
            'segments': transcription.segments
        }

    def _transcribe_with_groq(
        self,
        audio_path: str,
        api_key: Optional[str],
        language: Optional[str]
    ) -> Dict:
        used_api_key = api_key or self.groq_api_key
        if not used_api_key:
            raise Exception("Groq API key is required. Provide it in the UI or set GROQ_API_KEY in backend/.env")

        client = Groq(api_key=used_api_key)
        with open(audio_path, 'rb') as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio_file,
                response_format="verbose_json",
                language=language
            )

        return {
            'text': transcription.text,
            'language': transcription.language,
            'duration': transcription.duration,
            'segments': transcription.segments
        }

    def save_transcription_as_srt(
        self,
        transcription: Dict,
        video_id: str,
        language: str = 'ai'
    ) -> str:
        """
        Convert Whisper transcription to SRT subtitle format

        Args:
            transcription: Whisper transcription result
            video_id: Video ID
            language: Language code for filename

        Returns:
            Path to SRT file
        """
        srt_path = self.subtitle_dir / f"{video_id}.{language}.srt"

        segments = transcription['segments']

        with open(srt_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, 1):
                # Groq returns dicts; OpenAI returns objects with attributes
                if isinstance(segment, dict):
                    start_time = self._format_timestamp_srt(segment['start'])
                    end_time = self._format_timestamp_srt(segment['end'])
                    text = segment['text'].strip()
                else:
                    start_time = self._format_timestamp_srt(segment.start)
                    end_time = self._format_timestamp_srt(segment.end)
                    text = segment.text.strip()

                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")

        return str(srt_path)

    def _format_timestamp_srt(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def transcribe_video(
        self,
        video_path: str,
        video_id: str,
        api_key: Optional[str] = None,
        language: Optional[str] = None,
        provider: str = "openai"
    ) -> Dict:
        """
        Complete workflow: Extract audio, transcribe, and save as SRT

        Args:
            video_path: Path to video file
            video_id: Video ID
            api_key: API key (falls back to env var)
            language: Target language (None for auto-detect)
            provider: "openai" or "groq"

        Returns:
            Dict with subtitle path and transcription info
        """
        audio_path = self.extract_audio_from_video(video_path, video_id)

        transcription = self.transcribe_audio(audio_path, api_key, language, provider)

        detected_lang = transcription['language']
        srt_path = self.save_transcription_as_srt(transcription, video_id, detected_lang)

        try:
            os.remove(audio_path)
        except:
            pass

        return {
            'subtitle_path': srt_path,
            'language': detected_lang,
            'duration': transcription['duration'],
            'segments_count': len(transcription['segments'])
        }

    def cleanup_audio(self, video_id: str):
        """Clean up audio files"""
        audio_file = self.audio_dir / f"{video_id}.mp3"
        if audio_file.exists():
            audio_file.unlink()
