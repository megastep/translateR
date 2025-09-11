"""
AI Provider System

Handles integration with multiple AI providers for translation services.
Author: Emre Ertunç
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import requests
import os
import time
from ai_logger import (
    log_ai_request,
    log_ai_response,
    log_character_limit_retry,
    log_ai_http_error,
    log_ai_error,
)


class AIProvider(ABC):
    """Abstract base class for AI translation providers."""
    
    @abstractmethod
    def translate(self, text: str, target_language: str, 
                  max_length: Optional[int] = None, 
                  is_keywords: bool = False,
                  seed: Optional[int] = None) -> str:
        """
        Translate text to target language.
        
        Args:
            text: Text to translate
            target_language: Target language name
            max_length: Maximum character length for translation
            is_keywords: Whether the text is keywords (affects formatting)
            seed: Optional deterministic seed reused across locales
            Returns:
                Translated text
            """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get provider name."""
        pass


class AnthropicProvider(AIProvider):
    """Anthropic Claude AI provider."""
    
    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model
    
    def translate(self, text: str, target_language: str,
                  max_length: Optional[int] = None,
                  is_keywords: bool = False,
                  seed: Optional[int] = None) -> str:
        """Translate using Anthropic Claude."""
        # Log the request
        log_ai_request("Anthropic Claude", self.model, text, target_language, max_length, is_keywords, seed)
        
        try:
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            
            # Build system message
            system_message = (
                f"You are a professional translator specializing in App Store metadata translation. "
                f"Translate the following text to {target_language}. "
                f"Maintain the marketing tone and style of the original text."
            )
            
            if is_keywords:
                system_message += " For keywords, provide a comma-separated list and keep it concise."
            
            if max_length:
                system_message += (
                    f" CRITICAL: Your translation MUST be EXACTLY {max_length} characters or fewer "
                    f"INCLUDING ALL SPACES, PUNCTUATION, AND SPECIAL CHARACTERS. Count every single "
                    f"character including spaces between words. Do not add ellipsis (...) at the end. "
                    f"Create a concise but meaningful translation that captures the essence of the "
                    f"original message while staying within the character limit."
                )
            
            data = {
                "model": self.model,
                "system": system_message,
                "max_tokens": 1000,
                "messages": [
                    {"role": "user", "content": text}
                ]
            }
            if seed is not None:
                data["metadata"] = {"seed": str(seed)}
            
            start = time.monotonic()
            response = requests.post(url, headers=headers, json=data)
            duration_ms = int((time.monotonic() - start) * 1000)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as http_err:
                rid = response.headers.get('x-request-id') or response.headers.get('request-id') or response.headers.get('X-Request-Id')
                err_code = None
                err_type = None
                resp_text = None
                try:
                    resp_text = response.text
                    j = response.json()
                    # Anthropic error shape: {"error": {"type": "...", "message": "..."}}
                    if isinstance(j, dict) and 'error' in j:
                        err = j.get('error') or {}
                        err_type = err.get('type')
                        err_code = err.get('code') or err.get('type')
                        msg = err.get('message') or str(http_err)
                        resp_text = msg
                except Exception:
                    pass
                log_ai_http_error(
                    provider="Anthropic Claude",
                    endpoint=url,
                    status_code=response.status_code,
                    request_id=rid,
                    error_code=err_code,
                    error_type=err_type,
                    response_excerpt=resp_text,
                    duration_ms=duration_ms,
                    model=self.model,
                    headers_excerpt={k: v for k, v in response.headers.items() if k.lower() in ("x-request-id", "ratelimit-remaining", "ratelimit-reset")},
                )
                log_ai_response("Anthropic Claude", "", success=False, error=str(http_err))
                raise
            
            response_data = response.json()
            
            if "content" in response_data and isinstance(response_data["content"], list):
                translated_text = response_data["content"][0]["text"]
            else:
                raise ValueError("Unexpected API response format")
            
            # Check character limit and retry if needed
            if max_length and len(translated_text) > max_length:
                log_character_limit_retry("Anthropic Claude", len(translated_text), max_length)
                
                # Try again with even stricter instructions
                system_message += f" The text MUST be under {max_length} characters INCLUDING SPACES AND PUNCTUATION. Count every character. Prioritize brevity."
                data["system"] = system_message
                
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                response_data = response.json()
                translated_text = response_data["content"][0]["text"]
            
            # Log successful response
            log_ai_response("Anthropic Claude", translated_text, success=True)
            return translated_text.strip()
            
        except requests.exceptions.HTTPError as e:
            # Already logged above; rethrow with clearer message
            raise Exception(f"Anthropic API error {e.response.status_code}: {e}")
        except Exception as e:
            log_ai_error("Anthropic Claude", "Unhandled error during translation", {"error": str(e), "model": self.model})
            log_ai_response("Anthropic Claude", "", success=False, error=str(e))
            raise Exception(f"Anthropic translation failed: {str(e)}")
    
    def get_name(self) -> str:
        return "Anthropic Claude"


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider."""
    
    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model
    
    def translate(self, text: str, target_language: str,
                  max_length: Optional[int] = None,
                  is_keywords: bool = False,
                  seed: Optional[int] = None) -> str:
        """Translate using OpenAI GPT."""
        # Log the request
        log_ai_request("OpenAI GPT", self.model, text, target_language, max_length, is_keywords, seed)
        
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Build system message
            system_message = (
                f"You are a professional translator specializing in App Store metadata translation. "
                f"Translate the following text to {target_language}. "
                f"Maintain the marketing tone, formatting and style of the original text."
            )
            
            if is_keywords:
                system_message += " For keywords, provide a comma-separated list and keep it concise."
            
            if max_length:
                system_message += (
                    f" Create a concise but meaningful translation that captures the essence of the original message."
                )
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": text}
                ],
                "max_completion_tokens" if self.model.startswith("gpt-5") else "max_tokens": 1000,
                "temperature": 1.0 if self.model.startswith("gpt-5") else 0.7
            }
            if seed is not None:
                # Some models may reject seed; we'll retry without it if needed
                data["seed"] = seed
            
            # Send with optional one-time retry without seed if unsupported
            def _send(current_data):
                start = time.monotonic()
                resp = requests.post(url, headers=headers, json=current_data)
                dur = int((time.monotonic() - start) * 1000)
                return resp, dur

            response, duration_ms = _send(data)
            if response.status_code >= 400 and seed is not None:
                # Check if error mentions seed and retry once without it
                try:
                    j = response.json()
                    msg = (j.get('error', {}) or {}).get('message', '')
                except Exception:
                    msg = response.text or ''
                if 'seed' in (msg or '').lower():
                    # Log and retry without seed
                    log_ai_error("OpenAI GPT", "Retrying without seed due to model not supporting it", {"model": self.model, "status": response.status_code, "message": msg})
                    data.pop("seed", None)
                    response, duration_ms = _send(data)

            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as http_err:
                rid = response.headers.get('x-request-id') or response.headers.get('request-id') or response.headers.get('X-Request-Id')
                err_code = None
                err_type = None
                resp_text = None
                try:
                    resp_text = response.text
                    j = response.json()
                    # OpenAI error shape: {"error": {"type": "invalid_request_error", "message": "...", "code": "..."}}
                    if isinstance(j, dict) and 'error' in j:
                        err = j.get('error') or {}
                        err_type = err.get('type')
                        err_code = err.get('code')
                        msg = err.get('message') or str(http_err)
                        resp_text = msg
                except Exception:
                    pass
                log_ai_http_error(
                    provider="OpenAI GPT",
                    endpoint=url,
                    status_code=response.status_code,
                    request_id=rid,
                    error_code=err_code,
                    error_type=err_type,
                    response_excerpt=resp_text,
                    duration_ms=duration_ms,
                    model=self.model,
                    headers_excerpt={k: v for k, v in response.headers.items() if k.lower() in ("x-request-id", "x-ratelimit-remaining-requests", "x-ratelimit-reset-requests")},
                )
                log_ai_response("OpenAI GPT", "", success=False, error=str(http_err))
                raise
            
            response_data = response.json()
            
            if "choices" in response_data and len(response_data["choices"]) > 0:
                translated_text = response_data["choices"][0]["message"]["content"]
            else:
                raise ValueError("Unexpected API response format")
            
            # Check character limit and retry if needed
            if max_length and len(translated_text) > max_length:
                log_character_limit_retry("OpenAI GPT", len(translated_text), max_length)
                
                # Try again with even stricter instructions
                system_message += f" The text MUST be under {max_length} characters INCLUDING SPACES AND PUNCTUATION. Count every character. Prioritize brevity."
                data["messages"][0]["content"] = system_message
                
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                response_data = response.json()
                translated_text = response_data["choices"][0]["message"]["content"]
            
            # Log successful response
            log_ai_response("OpenAI GPT", translated_text, success=True)
            return translated_text.strip()
            
        except requests.exceptions.HTTPError as e:
            raise Exception(f"OpenAI API error {e.response.status_code}: {e}")
        except Exception as e:
            log_ai_error("OpenAI GPT", "Unhandled error during translation", {"error": str(e), "model": self.model})
            log_ai_response("OpenAI GPT", "", success=False, error=str(e))
            raise Exception(f"OpenAI translation failed: {str(e)}")
    
    def get_name(self) -> str:
        return "OpenAI GPT"


class GoogleGeminiProvider(AIProvider):
    """Google Gemini provider."""
    
    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model
    
    def translate(self, text: str, target_language: str,
                  max_length: Optional[int] = None,
                  is_keywords: bool = False,
                  seed: Optional[int] = None) -> str:
        """Translate using Google Gemini."""
        # Log the request
        log_ai_request("Google Gemini", self.model, text, target_language, max_length, is_keywords, seed)
        
        try:
            url = f"https://generativelanguage.googleapis.com/v1/models/{self.model}:generateContent?key={self.api_key}"
            headers = {
                "Content-Type": "application/json"
            }
            
            # Build prompt
            prompt = (
                f"You are a professional translator specializing in App Store metadata translation. "
                f"Translate the following text to {target_language}. "
                f"Maintain the marketing tone and style of the original text."
            )
            
            if is_keywords:
                prompt += " For keywords, provide a comma-separated list and keep it concise."
            
            if max_length:
                prompt += (
                    f" CRITICAL: Your translation MUST be EXACTLY {max_length} characters or fewer "
                    f"INCLUDING ALL SPACES, PUNCTUATION, AND SPECIAL CHARACTERS. Count every single "
                    f"character including spaces between words. Do not add ellipsis (...) at the end. "
                    f"Create a concise but meaningful translation that captures the essence of the "
                    f"original message while staying within the character limit."
                )
            
            prompt += f"\n\nText to translate: {text}"
            
            data = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 8000
                }
            }
            if seed is not None:
                try:
                    data["generationConfig"]["seed"] = int(seed)
                except Exception:
                    pass
            
            def _send(current_data):
                start = time.monotonic()
                resp = requests.post(url, headers=headers, json=current_data)
                dur = int((time.monotonic() - start) * 1000)
                return resp, dur

            response, duration_ms = _send(data)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as http_err:
                rid = response.headers.get('x-request-id') or response.headers.get('request-id') or response.headers.get('X-Request-Id')
                err_code = None
                err_type = None
                resp_text = None
                try:
                    resp_text = response.text
                    j = response.json()
                    # Gemini error shape: {"error": {"status": "...", "message": "...", "code": 400}}
                    if isinstance(j, dict) and 'error' in j:
                        err = j.get('error') or {}
                        err_type = err.get('status')
                        err_code = str(err.get('code')) if err.get('code') is not None else None
                        msg = err.get('message') or str(http_err)
                        resp_text = msg
                except Exception:
                    pass
                # Retry once without seed if unsupported
                if seed is not None and (resp_text or '').lower().find('seed') != -1 and isinstance(data.get('generationConfig'), dict):
                    log_ai_error("Google Gemini", "Retrying without seed due to model not supporting it", {"model": self.model, "status": response.status_code, "message": resp_text})
                    try:
                        data['generationConfig'].pop('seed', None)
                    except Exception:
                        pass
                    response, duration_ms = _send(data)
                    try:
                        response.raise_for_status()
                    except requests.exceptions.HTTPError:
                        # fall through to log below
                        pass
                    else:
                        # Success on retry; continue processing
                        resp_text = None
                        err_code = None
                        err_type = None
                        http_err = None  # type: ignore
                if response.status_code >= 400:
                    log_ai_http_error(
                        provider="Google Gemini",
                        endpoint=url,
                        status_code=response.status_code,
                        request_id=rid,
                        error_code=err_code,
                        error_type=err_type,
                        response_excerpt=resp_text,
                        duration_ms=duration_ms,
                        model=self.model,
                        headers_excerpt={k: v for k, v in response.headers.items() if k.lower() in ("x-request-id", "x-ratelimit-limit", "x-ratelimit-remaining")},
                    )
                    log_ai_response("Google Gemini", "", success=False, error=str(http_err))
                    raise
            
            response_data = response.json()
            
            if ("candidates" in response_data and 
                len(response_data["candidates"]) > 0 and
                "content" in response_data["candidates"][0] and
                "parts" in response_data["candidates"][0]["content"] and
                len(response_data["candidates"][0]["content"]["parts"]) > 0):
                translated_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
            elif ("candidates" in response_data and 
                  len(response_data["candidates"]) > 0 and
                  response_data["candidates"][0].get("finishReason") == "MAX_TOKENS"):
                raise ValueError("Translation too long - exceeded token limit. Try shorter text.")
            else:
                raise ValueError("Unexpected API response format")
            
            # Check character limit and retry if needed
            if max_length and len(translated_text) > max_length:
                log_character_limit_retry("Google Gemini", len(translated_text), max_length)
                
                # Try again with even stricter instructions
                prompt += f" The text MUST be under {max_length} characters INCLUDING SPACES AND PUNCTUATION. Count every character. Prioritize brevity."
                data["contents"][0]["parts"][0]["text"] = prompt
                
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                response_data = response.json()
                translated_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
            
            # Log successful response
            log_ai_response("Google Gemini", translated_text, success=True)
            return translated_text.strip()
            
        except requests.exceptions.HTTPError as e:
            raise Exception(f"Google Gemini API error {e.response.status_code}: {e}")
        except Exception as e:
            log_ai_error("Google Gemini", "Unhandled error during translation", {"error": str(e), "model": self.model})
            log_ai_response("Google Gemini", "", success=False, error=str(e))
            raise Exception(f"Google Gemini translation failed: {str(e)}")
    
    def get_name(self) -> str:
        return "Google Gemini"


class AIProviderManager:
    """Manages multiple AI providers and handles provider selection."""
    
    def __init__(self):
        self.providers: Dict[str, AIProvider] = {}
    
    def add_provider(self, name: str, provider: AIProvider):
        """Add an AI provider."""
        self.providers[name] = provider
    
    def get_provider(self, name: str) -> Optional[AIProvider]:
        """Get a specific AI provider."""
        return self.providers.get(name)
    
    def list_providers(self) -> List[str]:
        """List all available provider names."""
        return list(self.providers.keys())
