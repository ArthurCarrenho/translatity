import time
import logging
from pathlib import Path
import google.generativeai as genai
from google.api_core import exceptions
import random
import re
from PyQt6.QtCore import QObject, pyqtSignal

class APIKeyRotator(QObject):
    # APIKeyRotator implementation remains the same
    key_changed = pyqtSignal(int)

    def __init__(self, api_keys):
        super().__init__()
        if not api_keys:
            raise ValueError("At least one API key must be provided")
        self.api_keys = api_keys
        self.current_key_index = 0
        self.exhausted_keys = set()

    def get_current_key(self):
        return self.api_keys[self.current_key_index]

    def rotate_key(self):
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.key_changed.emit(self.current_key_index)
        logging.info("Rotated to next API key")

    def mark_key_exhausted(self, key):
        self.exhausted_keys.add(key)

    def has_available_keys(self):
        return len(self.exhausted_keys) < len(self.api_keys)

class SRTTranslator:
    def __init__(self, api_keys):
        self.key_rotator = APIKeyRotator(api_keys)
        self.model = self._initialize_model()
        self.last_request_time = 0
        self.base_delay = 30
        self.max_retries = 5
        self.max_backoff = 300
        self.chat = None
        # Add counters for 99% completion check
        self.near_completion_count = 0
        self.last_block_count = 0

    def _initialize_model(self):
        genai.configure(api_key=self.key_rotator.get_current_key())
        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
        }
        
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]
        
        return genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            generation_config=generation_config,
            safety_settings=safety_settings
        )

    def _check_near_completion(self, current_blocks, total_blocks):
        """Check if translation is near completion (≥99%) for consecutive tries."""
        completion_percentage = (current_blocks / total_blocks) * 100
        
        if completion_percentage >= 99:
            if current_blocks == self.last_block_count:
                self.near_completion_count += 1
            else:
                self.near_completion_count = 1
        else:
            self.near_completion_count = 0
            
        self.last_block_count = current_blocks
        return self.near_completion_count >= 2

    def _make_api_request(self, chat_session, message, is_continuation=False, retry_count=0):
        try:
            self._wait_with_backoff(retry_count)
            
            if is_continuation:
                response = chat_session.send_message("continue")
            else:
                if isinstance(message, list):
                    message = "\n---\n".join(message)
                response = chat_session.send_message(message)
            
            return response
            
        except exceptions.ResourceExhausted as e:
            if retry_count >= self.max_retries - 1:
                self._handle_quota_exhaustion()
                return self._make_api_request(chat_session, message, is_continuation, 0)
            logging.warning(f"Resource exhausted, retrying... ({retry_count + 1}/{self.max_retries})")
            return self._make_api_request(chat_session, message, is_continuation, retry_count + 1)
            
        except Exception as e:
            logging.error(f"Unexpected error during API request: {e}")
            raise

    def _calculate_backoff(self, retry_count):
        delay = min(self.max_backoff, self.base_delay * (2 ** retry_count))
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter

    def _wait_with_backoff(self, retry_count):
        if retry_count > 0:
            delay = self._calculate_backoff(retry_count - 1)
            logging.info(f"Backing off for {delay:.2f} seconds (attempt {retry_count}/{self.max_retries})")
            time.sleep(delay)

    def _handle_quota_exhaustion(self):
        current_key = self.key_rotator.get_current_key()
        self.key_rotator.mark_key_exhausted(current_key)
        
        if not self.key_rotator.has_available_keys():
            raise Exception("All API keys have been exhausted")
            
        self.key_rotator.rotate_key()
        self.model = self._initialize_model()

    def _create_chat(self):
        self.chat = self.model.start_chat()
        return self.chat

    def translate_file(self, input_path, output_path, save_progress=True, progress_callback=None, 
                      status_callback=None, input_lang="English", output_lang="Portuguese", 
                      context="", cancel_check=None):
        input_path = Path(input_path)
        output_path = Path(output_path)
        progress_path = output_path.with_suffix('.progress')
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        with open(input_path, 'r', encoding='utf-8') as f:
            input_content = f.read()
            total_blocks = count_srt_blocks(input_content)
            logging.info(f"Total SRT blocks in input file: {total_blocks}")
            if status_callback:
                status_callback(f"Total SRT blocks: {total_blocks}")

        translated_content = []
        if save_progress and progress_path.exists():
            with open(progress_path, 'r', encoding='utf-8') as f:
                progress_content = f.read()
                translated_blocks = extract_srt_blocks(progress_content)
                if translated_blocks:
                    translated_content = translated_blocks
                    current_blocks = len(translated_blocks)
                    logging.info(f"Loaded {current_blocks}/{total_blocks} blocks from progress file")
                    if status_callback:
                        status_callback(f"Loaded {current_blocks}/{total_blocks} blocks from progress")
                    if progress_callback:
                        progress_callback(current_blocks, total_blocks)

        chat = self._create_chat()
        
        try:
            if not translated_content:
                if status_callback:
                    status_callback("Starting translation...")
                
                system_message = f"""You are a professional subtitle translator. Your task is to translate subtitles from {input_lang} to {output_lang}.
                Maintain the SRT format and timing. Fix capitalization where needed. Preserve any special formatting or tags.
                Context for this translation: {context}
                Translate the content naturally, considering the context and maintaining the original tone and style."""
                
                response = self._make_api_request(chat, [
                    system_message,
                    input_content,
                    "Translate the provided subtitle file. Maintain SRT format and timing."
                ])
                
                current_blocks = len(extract_srt_blocks(response.text))
                translated_content.extend(extract_srt_blocks(response.text))
                logging.info(f"Translated {current_blocks}/{total_blocks} blocks")
                if status_callback:
                    status_callback(f"Translated {current_blocks}/{total_blocks} blocks")
                if progress_callback:
                    progress_callback(current_blocks, total_blocks)
                
                if save_progress:
                    with open(progress_path, 'w', encoding='utf-8') as f:
                        f.write('\n\n'.join(translated_content))
            
            while len(translated_content) < total_blocks:
                if cancel_check and cancel_check():
                    logging.info("Translation cancelled")
                    if status_callback:
                        status_callback("Translation cancellation requested")
                    return

                # Check if we're at 99% completion for 2 consecutive tries
                if self._check_near_completion(len(translated_content), total_blocks):
                    logging.info("Translation reached 99% completion for 2 consecutive tries. Marking as complete.")
                    if status_callback:
                        status_callback("Translation completed (99% threshold reached)")
                    break

                if status_callback:
                    status_callback("Continuing translation...")
                response = self._make_api_request(chat, "continue", is_continuation=True)
                new_blocks = extract_srt_blocks(response.text)
                
                for block in new_blocks:
                    if block not in translated_content:
                        translated_content.append(block)
                
                current_blocks = len(translated_content)
                logging.info(f"Translated {current_blocks}/{total_blocks} blocks")
                if status_callback:
                    status_callback(f"Translated {current_blocks}/{total_blocks} blocks")
                if progress_callback:
                    progress_callback(current_blocks, total_blocks)
                
                if save_progress:
                    with open(progress_path, 'w', encoding='utf-8') as f:
                        f.write('\n\n'.join(translated_content))
                
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(translated_content))
            
            if save_progress and progress_path.exists():
                progress_path.unlink()
                
            logging.info(f"Translation completed and saved to {output_path}")
            if status_callback:
                status_callback(f"Translation completed and saved to {output_path}")
            
        except Exception as e:
            logging.error(f"Error during translation: {e}")
            raise
        finally:
            if self.chat:
                self.chat = None

def count_srt_blocks(content):
    """Count the number of SRT blocks in the content."""
    blocks = re.findall(r'^\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->', content, re.MULTILINE)
    return len(blocks)

def extract_srt_blocks(content):
    """Extract individual SRT blocks from content."""
    blocks = [block.strip() for block in re.split(r'\n\s*\n', content) if block.strip()]
    return [block for block in blocks if re.match(r'^\d+\s*\n', block)]