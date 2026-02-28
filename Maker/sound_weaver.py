import os
import io
import time
import hashlib
import base64
import requests
import wave
import struct
from typing import List, Dict, Optional
import subprocess

# Optional: pydub is preferred for audio post-processing; fall back to ffmpeg via subprocess
try:
    from pydub import AudioSegment, effects
    PYDUB_AVAILABLE = True
except Exception:
    PYDUB_AVAILABLE = False

PROJECTS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'output')


def _post_process(file_path: str, length_seconds: int = 5, crossfade_ms: int = 100, target_lufs: Optional[float] = -14.0) -> Dict:
    """Normalize, ensure exact length, and apply short fades for better loopability.
    Returns a dict with processing metadata and any errors.
    """
    info = {'processed': False, 'notes': []}
    try:
        desired_ms = int(length_seconds * 1000)
        if PYDUB_AVAILABLE:
            audio = AudioSegment.from_file(file_path)
            # Convert to mono and target sample rate
            audio = audio.set_channels(1).set_frame_rate(22050)
            # Simple peak normalization
            audio = effects.normalize(audio)
            # Trim or pad to exact length
            if len(audio) > desired_ms:
                audio = audio[:desired_ms]
            else:
                pad_ms = desired_ms - len(audio)
                if pad_ms > 0:
                    audio = audio + AudioSegment.silent(duration=pad_ms)
            # Apply short fade in/out to reduce clicks and help looping
            if crossfade_ms and crossfade_ms > 0:
                fade_ms = min(crossfade_ms, int(desired_ms / 4))
                audio = audio.fade_in(fade_ms).fade_out(fade_ms)
            # Export in MP3 (browser-friendly)
            audio.export(file_path, format='mp3', bitrate='128k')
            info['processed'] = True
            info['notes'].append('Processed with pydub: normalized, trimmed/padded, fade applied.')
        else:
            # Use ffmpeg if available for loudness normalization and fades
            # afade times based on desired length
            fade_dur = min(crossfade_ms / 1000.0, max(0.02, desired_ms / 1000.0 * 0.05))
            fade_out_start = max(0, (desired_ms / 1000.0) - fade_dur)
            afilter = f"loudnorm=I={target_lufs}:LRA=7:TP=-2,afade=t=in:ss=0:d={fade_dur},afade=t=out:st={fade_out_start}:d={fade_dur}"
            tmp_out = file_path + '.proc.mp3'
            cmd = [
                'ffmpeg', '-y', '-i', file_path,
                '-af', afilter,
                '-ar', '22050', '-ac', '1',
                '-t', str(length_seconds),
                tmp_out
            ]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Replace original
                os.replace(tmp_out, file_path)
                info['processed'] = True
                info['notes'].append('Processed with ffmpeg: loudnorm + afade applied.')
            except Exception as e:
                info['notes'].append(f'ffmpeg processing failed: {e}')
    except Exception as e:
        info['notes'].append(f'Post-processing error: {e}')
    return info


def _sanitize_name(name: str) -> str:
    clean = "".join(c for c in name if c.isalnum() or c in ('_', '-'))
    return clean.strip() # Only strip whitespace


def _prompt_hash(prompt: str, model: str, length_seconds: int) -> str:
    h = hashlib.sha256(f"{prompt}|{model}|{length_seconds}".encode('utf-8')).hexdigest()
    return h[:12]


def _ensure_audio_dir(project_id: str) -> str:
    audio_dir = os.path.join(PROJECTS_ROOT, project_id, 'audio')
    os.makedirs(audio_dir, exist_ok=True)
    return audio_dir


# Metadata persistence to disk was removed; metadata is returned in-memory by generate_candidates.
def _write_silence_mp3(file_path: str, duration_seconds: int = 5, sample_rate: int = 22050):
    """Write a silent MP3 file as a fallback placeholder. Uses pydub if available, otherwise falls back to ffmpeg-based creation."""
    desired_ms = int(duration_seconds * 1000)
    try:
        if PYDUB_AVAILABLE:
            silent = AudioSegment.silent(duration=desired_ms)
            # Ensure mono and proper frame rate
            silent = silent.set_channels(1).set_frame_rate(sample_rate)
            silent.export(file_path, format='mp3', bitrate='128k')
        else:
            # Use ffmpeg to create silent mp3
            tmp_wav = file_path + '.tmp.wav'
            n_channels = 1
            sampwidth = 2  # 16-bit
            n_frames = int(duration_seconds * sample_rate)
            comp_type = 'NONE'
            comp_name = 'not compressed'
            with wave.open(tmp_wav, 'w') as wf:
                wf.setnchannels(n_channels)
                wf.setsampwidth(sampwidth)
                wf.setframerate(sample_rate)
                wf.setcomptype(comp_type, comp_name)
                silent_frame = struct.pack('<h', 0)
                frames = silent_frame * n_frames
                wf.writeframes(frames)
            # Convert to mp3
            cmd = ['ffmpeg', '-y', '-i', tmp_wav, '-ar', str(sample_rate), '-ac', '1', '-b:a', '128k', file_path]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.remove(tmp_wav)
    except Exception as e:
        # As a last resort, try to write a tiny empty file so UI still works
        with open(file_path, 'wb') as f:
            f.write(b'')


class SoundWeaver:
    def __init__(self, api_key: Optional[str] = None):
        # Prefer env var if not provided
        self.api_key = api_key or os.getenv('ELEVENLABS_API_KEY')
        # Use the specific Sound Generation endpoint
        self.api_endpoint = "https://api.elevenlabs.io/v1/sound-generation"

    def _call_elevenlabs(self, prompt, length_seconds=None, model='eleven_text_to_sound_v2', loop=False):
        """
        Helper to call the API.
        """
        if not self.api_key:
            raise RuntimeError('ELEVENLABS_API_KEY not set in environment')

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        # Correct payload structure for Sound Generation API
        payload = {
            "text": prompt,
            "duration_seconds": length_seconds,
            "prompt_influence": 0.3,
            "loop": loop  # Tells the model to generate a seamless loop
        }

        try:
            r = requests.post(self.api_endpoint, headers=headers, json=payload, timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f'ElevenLabs API error: {r.status_code} {r.text[:200]}')

            # The API may return raw audio bytes or a JSON with 'audio_base64' or 'audio_url'
            content_type = r.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                j = r.json()
                if 'audio_base64' in j:
                    return base64.b64decode(j['audio_base64'])
                if 'audio_url' in j:
                    # Fetch the url
                    audio_r = requests.get(j['audio_url'], timeout=30)
                    if audio_r.status_code == 200:
                        return audio_r.content
                    else:
                        raise RuntimeError(f'Failed to fetch audio url: {audio_r.status_code}')
                raise RuntimeError('Unknown JSON response from ElevenLabs')
            else:
                # Assume binary audio data
                return r.content

        except Exception as e:
            # Bubble up to caller to decide fallback behavior
            raise

    def generate_candidates(self, book_id, base_name, prompt, count=1, length_seconds=None, model='eleven_text_to_sound_v2', dry_run=False, postprocess=True, loop=False):
        """
        Generate `count` audio candidates for a scene and save them into the project's audio folder.
        Returns list of dicts: {"file": <relative_path>, "meta": {...}}

        If `dry_run` is True, no API call is made — silent placeholders are written instead.
        If `postprocess` is False, the generated audio will not be run through normalization/trim/fade steps.
        """
        out = []
        project_id_s = _sanitize_name(book_id)
        scene_s = _sanitize_name(base_name)
        audio_dir = _ensure_audio_dir(project_id_s)

        for idx in range(count):
            phash = _prompt_hash(prompt, model, length_seconds)
            filename = f"{project_id_s}_{scene_s}_sfx_{phash}_{idx}.mp3"
            file_path = os.path.join(audio_dir, filename)

            meta = {
                'project_id': project_id_s,
                'scene_id': scene_s,
                'prompt': prompt,
                'model': model,
                'length_seconds': int(length_seconds),
                'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'candidate_index': idx,
                'placeholder': False,
            }

            try:
                if dry_run or not self.api_key:
                    # Create silent placeholder
                    _write_silence_mp3(file_path, int(length_seconds))
                    meta['placeholder'] = True
                    meta['note'] = 'Dry-run or missing API key; placeholder silence written.'
                else:
                    audio_bytes = self._call_elevenlabs(prompt, length_seconds, model, loop=loop)
                    if not audio_bytes:
                        raise RuntimeError('No audio bytes returned')
                    # Write raw bytes and ensure it ends up as mp3; if API returns WAV, we'll post-process/convert
                    with open(file_path, 'wb') as f:
                        f.write(audio_bytes)

                # Post-process for loopability and normalization (if enabled)
                if postprocess:
                    proc_info = _post_process(file_path, int(length_seconds), crossfade_ms=100, target_lufs=-14.0)
                    if proc_info.get('processed'):
                        meta['processed'] = True
                    meta['processing_notes'] = proc_info.get('notes', [])
                else:
                    meta['processing_notes'] = ['Post-processing skipped by configuration.']

                # Do NOT persist a .meta.json on disk — keep metadata in-memory only for the caller.
                # Remove any pre-existing .meta.json for this audio file.
                meta_path = file_path + '.meta.json'
                if os.path.exists(meta_path):
                    try:
                        os.remove(meta_path)
                    except Exception:
                        pass

                rel_path = os.path.relpath(file_path, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
                out.append({'file': rel_path.replace('\\', '/'), 'meta': meta})

            except Exception as e:
                # On any error, write a placeholder so the UI can still show a candidate and the author can upload a custom sound
                try:
                    _write_silence_mp3(file_path, int(length_seconds))
                    meta['placeholder'] = True
                    meta['error'] = str(e)

                    # Do NOT persist a .meta.json on disk — keep metadata in-memory only for the caller.
                    meta_path = file_path + '.meta.json'
                    if os.path.exists(meta_path):
                        try:
                            os.remove(meta_path)
                        except Exception:
                            pass

                    rel_path = os.path.relpath(file_path, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
                    out.append({'file': rel_path.replace('\\', '/'), 'meta': meta})
                except Exception:
                    # If even placeholder writing fails, append nothing for this candidate
                    continue

        return out


if __name__ == '__main__':
    # Quick smoke test
    sw = SoundWeaver()
    print('API key present:', bool(sw.api_key))
    candidates = sw.generate_candidates('test_project', 'scene_intro', 'A soft, eerie wind with distant chimes', count=2, dry_run=True)
    print('Candidates:', candidates)
