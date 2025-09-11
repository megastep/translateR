"""
AI Logger System

Logs all AI provider requests and responses in human-readable format.
Author: Emre Ertunç
"""

import os
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class AILogger:
    """Logs AI provider requests and responses."""
    
    def __init__(self, log_dir: str = "logs"):
        """
        Initialize AI logger.
        
        Args:
            log_dir: Directory to store log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True, mode=0o755)
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"ai_requests_{timestamp}.log"
        
        # Synchronization for concurrent writes
        self._lock = threading.Lock()

        # Write header
        self._write_header()
    
    def _write_header(self):
        """Write log file header."""
        header = f"""
===============================================================================
TranslateR AI Request Log
Started: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
===============================================================================

"""
        with self._lock:
            with open(self.log_file, "w", encoding="utf-8") as f:
                f.write(header)
    
    def log_request(self, provider: str, model: str, text: str,
                   target_language: str, max_length: Optional[int] = None,
                   is_keywords: bool = False, seed: Optional[int] = None):
        """
        Log AI translation request.
        
        Args:
            provider: AI provider name
            model: Model used
            text: Text being translated
            target_language: Target language
            max_length: Character limit
            is_keywords: Whether text is keywords
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_entry = f"""
[{timestamp}] REQUEST
Provider: {provider}
Model: {model}
Seed: {seed if seed is not None else 'n/a'}
Target Language: {target_language}
Max Length: {max_length if max_length else "No limit"}
Is Keywords: {is_keywords}
Original Text ({len(text)} chars):
{'-' * 50}
{text}
{'-' * 50}

"""
        
        with self._lock:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
    
    def log_response(self, provider: str, translated_text: str, 
                    success: bool = True, error: Optional[str] = None):
        """
        Log AI translation response.
        
        Args:
            provider: AI provider name
            translated_text: Translated text (if successful)
            success: Whether request was successful
            error: Error message (if failed)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if success:
            log_entry = f"""[{timestamp}] RESPONSE - SUCCESS
Provider: {provider}
Translated Text ({len(translated_text)} chars):
{'-' * 50}
{translated_text}
{'-' * 50}

"""
        else:
            log_entry = f"""[{timestamp}] RESPONSE - ERROR
Provider: {provider}
Error:
{'-' * 50}
{error}
{'-' * 50}

"""
        
        with self._lock:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)

    def log_error(self, provider: str, message: str, details: Optional[Dict[str, Any]] = None):
        """Log a structured non-HTTP error with optional details."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = ""
        if details:
            try:
                body = json.dumps(details, indent=2, ensure_ascii=False)
            except Exception:
                body = str(details)
        log_entry = f"""[{timestamp}] ERROR
Provider: {provider}
Message: {message}
Details:
{'-' * 50}
{body}
{'-' * 50}

"""
        with self._lock:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)

    def log_http_error(self, provider: str, endpoint: str, status_code: int,
                       request_id: Optional[str] = None,
                       error_code: Optional[str] = None,
                       error_type: Optional[str] = None,
                       response_excerpt: Optional[str] = None,
                       duration_ms: Optional[int] = None,
                       model: Optional[str] = None,
                       headers_excerpt: Optional[Dict[str, Any]] = None):
        """Log an HTTP error with useful context (no secrets)."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Sanitize headers (drop auth keys)
        redacted_headers = {}
        try:
            for k, v in (headers_excerpt or {}).items():
                lk = str(k).lower()
                if any(x in lk for x in ("authorization", "api-key", "x-api-key", "cookie")):
                    redacted_headers[k] = "<redacted>"
                else:
                    redacted_headers[k] = v
        except Exception:
            redacted_headers = {}

        response_excerpt = (response_excerpt or "").strip()
        if len(response_excerpt) > 2000:
            response_excerpt = response_excerpt[:2000] + "\n[...truncated...]"

        log_entry = f"""[{timestamp}] HTTP ERROR
Provider: {provider}
Endpoint: {endpoint}
Model: {model or ''}
Status: {status_code}
Request-Id: {request_id or ''}
Error Code: {error_code or ''}
Error Type: {error_type or ''}
Duration: {duration_ms or ''} ms
Headers:
{json.dumps(redacted_headers, indent=2)}
Response (excerpt):
{'-' * 50}
{response_excerpt}
{'-' * 50}

"""
        with self._lock:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
    
    def log_character_limit_retry(self, provider: str, original_length: int, 
                                 max_length: int):
        """
        Log character limit retry attempt.
        
        Args:
            provider: AI provider name
            original_length: Length of first translation
            max_length: Required maximum length
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_entry = f"""[{timestamp}] CHARACTER LIMIT RETRY
Provider: {provider}
Original translation: {original_length} chars
Required limit: {max_length} chars
Retrying with stricter instructions...

"""
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    
    def get_log_file_path(self) -> str:
        """Get the current log file path."""
        return str(self.log_file)


# Global logger instance
_logger_instance: Optional[AILogger] = None


def get_ai_logger() -> AILogger:
    """Get or create global AI logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = AILogger()
    return _logger_instance


def log_ai_request(provider: str, model: str, text: str,
                  target_language: str, max_length: Optional[int] = None,
                  is_keywords: bool = False, seed: Optional[int] = None):
    """Convenience function to log AI request."""
    logger = get_ai_logger()
    logger.log_request(provider, model, text, target_language, max_length, is_keywords, seed)


def log_ai_response(provider: str, translated_text: str = "", 
                   success: bool = True, error: Optional[str] = None):
    """Convenience function to log AI response."""
    logger = get_ai_logger()
    logger.log_response(provider, translated_text, success, error)


def log_character_limit_retry(provider: str, original_length: int, max_length: int):
    """Convenience function to log character limit retry."""
    logger = get_ai_logger()
    logger.log_character_limit_retry(provider, original_length, max_length)

def log_ai_error(provider: str, message: str, details: Optional[Dict[str, Any]] = None):
    """Convenience function to log non-HTTP errors with details."""
    logger = get_ai_logger()
    logger.log_error(provider, message, details)

def log_ai_http_error(provider: str, endpoint: str, status_code: int,
                      request_id: Optional[str] = None,
                      error_code: Optional[str] = None,
                      error_type: Optional[str] = None,
                      response_excerpt: Optional[str] = None,
                      duration_ms: Optional[int] = None,
                      model: Optional[str] = None,
                      headers_excerpt: Optional[Dict[str, Any]] = None):
    """Convenience function to log HTTP errors."""
    logger = get_ai_logger()
    logger.log_http_error(provider, endpoint, status_code, request_id, error_code, error_type, response_excerpt, duration_ms, model, headers_excerpt)
