"""Tokenizer adapter interfaces and defaults."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type, Tuple

from .chunking import token_spans

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS = 8192

# Model to max tokens mapping with expanded OpenAI model support
MODEL_MAX_TOKENS: Dict[str, int] = {
    # OpenAI embedding models
    "text-embedding-ada-002": 8192,
    "text-embedding-3-small": 8192,
    "text-embedding-3-large": 8192,
    # OpenAI GPT models
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-16k": 16384,
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    # OpenAI legacy models
    "text-davinci-003": 4097,
    "text-davinci-002": 4097,
    "code-davinci-002": 8001,
    # HuggingFace sentence-transformers models
    "sentence-transformers/all-MiniLM-L6-v2": 512,
    "sentence-transformers/all-mpnet-base-v2": 512,
    "sentence-transformers/all-MiniLM-L12-v2": 512,
    "sentence-transformers/paraphrase-MiniLM-L6-v2": 512,
    "sentence-transformers/paraphrase-mpnet-base-v2": 512,
    "sentence-transformers/multi-qa-MiniLM-L6-cos-v1": 512,
    "sentence-transformers/multi-qa-mpnet-base-cos-v1": 512,
    "sentence-transformers/distilbert-base-nli-stsb-mean-tokens": 512,
    "sentence-transformers/roberta-base-nli-stsb-mean-tokens": 512,
    "sentence-transformers/stsb-roberta-large": 512,
    # HuggingFace BERT family models
    "bert-base-uncased": 512,
    "bert-base-cased": 512,
    "bert-large-uncased": 512,
    "bert-large-cased": 512,
    "distilbert-base-uncased": 512,
    "distilbert-base-cased": 512,
    # HuggingFace RoBERTa family models
    "roberta-base": 512,
    "roberta-large": 1024,
    "distilroberta-base": 512,
    # HuggingFace other popular models
    "microsoft/DialoGPT-medium": 1024,
    "microsoft/DialoGPT-large": 1024,
    "facebook/bart-base": 1024,
    "facebook/bart-large": 1024,
    "t5-small": 512,
    "t5-base": 512,
    "t5-large": 512,
}

# Model to encoding mapping for tiktoken
MODEL_TO_ENCODING: Dict[str, str] = {
    # GPT-4 and newer models use cl100k_base
    "gpt-4": "cl100k_base",
    "gpt-4-32k": "cl100k_base", 
    "gpt-4-turbo": "cl100k_base",
    "gpt-4o": "cl100k_base",
    "gpt-4o-mini": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    "gpt-3.5-turbo-16k": "cl100k_base",
    "text-embedding-ada-002": "cl100k_base",
    "text-embedding-3-small": "cl100k_base",
    "text-embedding-3-large": "cl100k_base",
    # Legacy models use different encodings
    "text-davinci-003": "p50k_base",
    "text-davinci-002": "p50k_base",
    "code-davinci-002": "p50k_base",
}


@dataclass(frozen=True)
class TokenCount:
    """Token count information."""

    count: int
    method: str
    tokenizer_id: str
    is_exact: bool
    model_max_tokens: Optional[int] = None


class TokenizerAdapter(ABC):
    """Abstract base class for tokenizer adapters."""

    def __init__(self, model_name: str, max_tokens: Optional[int] = None) -> None:
        if not model_name:
            raise ValueError("model_name must be non-empty")
        self._model_name = model_name
        self._max_tokens = max_tokens

    @property
    def model_name(self) -> str:
        """Return the model name for this adapter."""
        return self._model_name

    @property
    @abstractmethod
    def adapter_id(self) -> str:
        """Unique identifier for this adapter."""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> TokenCount:
        """Count tokens for the given text."""

    @abstractmethod
    def max_tokens(self) -> int:
        """Return the max token budget for the model."""


class HeuristicTokenizer(TokenizerAdapter):
    """Tokenizer adapter using deterministic heuristics with configurable ratios."""

    def __init__(self, model_name: str, max_tokens: Optional[int] = None, chars_per_token: float = 4.0) -> None:
        super().__init__(model_name, max_tokens)
        if chars_per_token <= 0:
            raise ValueError("chars_per_token must be positive")
        self._chars_per_token = chars_per_token

    @property
    def adapter_id(self) -> str:
        """Unique identifier for this adapter."""
        return "heuristic"

    @property
    def chars_per_token(self) -> float:
        """Get the configured chars-per-token ratio."""
        return self._chars_per_token

    def count_tokens(self, text: str) -> TokenCount:
        if text is None:
            raise ValueError("text must be a string")
        
        # Use character-based estimation with language detection
        token_count = self._estimate_tokens_with_language_detection(text)
        
        return TokenCount(
            count=token_count,
            method="heuristic",
            tokenizer_id=f"heuristic:{self._model_name}:chars_{self._chars_per_token}",
            is_exact=False,
            model_max_tokens=self.max_tokens(),
        )

    def _estimate_tokens_with_language_detection(self, text: str) -> int:
        """Estimate token count using character-based approach with language detection."""
        if not text:
            return 0
        
        # For very short text, use a more conservative approach
        if len(text) <= 3:
            return 1
        
        # Detect text composition for adaptive estimation
        char_count = len(text)
        cjk_count = sum(1 for ch in text if self._is_cjk_char(ch))
        
        # Calculate CJK ratio to adjust estimation
        cjk_ratio = cjk_count / char_count if char_count > 0 else 0
        
        if cjk_ratio > 0.5:
            # Predominantly CJK text - each character is roughly a token
            # Use a lower ratio since CJK characters are typically 1 token each
            effective_ratio = 1.2  # Slightly more than 1 to account for punctuation
        elif cjk_ratio > 0.1:
            # Mixed text - blend the ratios
            # Weight towards CJK behavior for mixed content
            cjk_weight = min(cjk_ratio * 3, 0.7)  # Cap the CJK influence
            ascii_weight = 1 - cjk_weight
            effective_ratio = (1.2 * cjk_weight + self._chars_per_token * ascii_weight)
        else:
            # Predominantly ASCII/Latin text - use configured ratio
            effective_ratio = self._chars_per_token
        
        # Calculate estimated tokens
        estimated_tokens = max(1, int(char_count / effective_ratio))
        
        # For punctuation-heavy text, add some tokens
        punct_count = sum(1 for ch in text if not ch.isalnum() and not ch.isspace() and not self._is_cjk_char(ch))
        if punct_count > 0:
            # Add roughly half the punctuation marks as additional tokens
            estimated_tokens += max(0, punct_count // 2)
        
        return estimated_tokens

    def _is_cjk_char(self, ch: str) -> bool:
        """Check if character is CJK (Chinese, Japanese, Korean)."""
        code = ord(ch)
        return (
            0x3400 <= code <= 0x4DBF  # CJK Ext A
            or 0x4E00 <= code <= 0x9FFF  # CJK Unified
            or 0x3040 <= code <= 0x30FF  # Hiragana/Katakana
            or 0xAC00 <= code <= 0xD7AF  # Hangul
        )

    def max_tokens(self) -> int:
        if self._max_tokens is not None:
            return self._max_tokens
        return resolve_model_max_tokens(self._model_name)



class TiktokenAdapter(TokenizerAdapter):
    """Tokenizer using the tiktoken library (OpenAI models)."""

    def __init__(self, model_name: str, encoding: Any = None, max_tokens: Optional[int] = None) -> None:
        super().__init__(model_name, max_tokens)
        
        # Check if tiktoken is available
        try:
            import tiktoken
        except ImportError:
            raise ImportError(
                "tiktoken package required for TiktokenAdapter. "
                "Install with: pip install tiktoken"
            )
        
        if encoding:
            # Use provided encoding directly
            self._encoding = encoding
            self._encoding_name = getattr(encoding, 'name', 'custom')
        else:
            # Resolve encoding based on model name
            self._encoding, self._encoding_name = self._resolve_encoding(tiktoken, model_name)

    def _resolve_encoding(self, tiktoken_module: Any, model_name: str) -> Tuple[Any, str]:
        """Resolve the appropriate encoding for the given model.
        
        Args:
            tiktoken_module: The imported tiktoken module
            model_name: Name of the model
            
        Returns:
            Tuple of (encoding, encoding_name)
        """
        # First try to get encoding directly for the model
        try:
            encoding = tiktoken_module.encoding_for_model(model_name)
            return encoding, encoding.name
        except KeyError:
            # Model not found, try our mapping
            if model_name in MODEL_TO_ENCODING:
                encoding_name = MODEL_TO_ENCODING[model_name]
                try:
                    encoding = tiktoken_module.get_encoding(encoding_name)
                    logger.debug(f"Using {encoding_name} encoding for model {model_name}")
                    return encoding, encoding_name
                except Exception as e:
                    logger.warning(f"Failed to load {encoding_name} encoding: {e}")
            
            # Fallback to cl100k_base (most common for newer models)
            try:
                encoding = tiktoken_module.get_encoding("cl100k_base")
                logger.info(f"Using cl100k_base fallback encoding for unknown model: {model_name}")
                return encoding, "cl100k_base"
            except Exception as e:
                logger.warning(f"Failed to load cl100k_base encoding: {e}")
                
                # Final fallback to p50k_base
                try:
                    encoding = tiktoken_module.get_encoding("p50k_base")
                    logger.info(f"Using p50k_base fallback encoding for model: {model_name}")
                    return encoding, "p50k_base"
                except Exception as e:
                    raise RuntimeError(f"Failed to load any tiktoken encoding: {e}")

    @property
    def adapter_id(self) -> str:
        """Unique identifier for this adapter."""
        return "tiktoken"

    @property
    def encoding_name(self) -> str:
        """Get the name of the encoding being used."""
        return self._encoding_name

    def count_tokens(self, text: str) -> TokenCount:
        if text is None:
            return TokenCount(
                count=0,
                method="tiktoken",
                tokenizer_id=f"tiktoken:{self._model_name}:{self._encoding_name}",
                is_exact=True,
                model_max_tokens=self.max_tokens(),
            )
        
        try:
            # tiktoken encode can fail on special tokens if not allowed, 
            # but for counting we generally want to process them or ignore them.
            # "all" allows special tokens.
            tokens = self._encoding.encode(text, disallowed_special=())
            return TokenCount(
                count=len(tokens),
                method="tiktoken",
                tokenizer_id=f"tiktoken:{self._model_name}:{self._encoding_name}",
                is_exact=True,
                model_max_tokens=self.max_tokens(),
            )
        except Exception as e:
            logger.error(f"TikToken encoding failed for model {self._model_name}: {e}")
            # This should not happen in normal operation, but if it does,
            # we need to raise an exception since this adapter promises exact counts
            raise RuntimeError(f"TikToken tokenization failed: {e}")

    def max_tokens(self) -> int:
        if self._max_tokens is not None:
            return self._max_tokens
        return resolve_model_max_tokens(self._model_name)


def resolve_model_max_tokens(
    model_name: str,
    overrides: Optional[Dict[str, int]] = None,
    default: int = DEFAULT_MAX_TOKENS,
) -> int:
    """Resolve max token budget for a model with optional overrides."""
    if overrides and model_name in overrides:
        return overrides[model_name]
    if model_name in MODEL_MAX_TOKENS:
        return MODEL_MAX_TOKENS[model_name]
    return default


def get_supported_huggingface_models() -> List[str]:
    """Get list of HuggingFace models with known token limits.
    
    Returns:
        List of model names that have predefined token limits.
    """
    return [model for model in MODEL_MAX_TOKENS.keys() 
            if model.startswith(('sentence-transformers/', 'bert-', 'distilbert-', 
                               'roberta-', 'distilroberta-', 'microsoft/', 
                               'facebook/', 't5-'))]


def is_sentence_transformers_model(model_name: str) -> bool:
    """Check if a model name corresponds to a sentence-transformers model.
    
    Args:
        model_name: The HuggingFace model identifier
        
    Returns:
        True if the model is a sentence-transformers model
    """
    return model_name.startswith('sentence-transformers/')


def suggest_huggingface_model(task_type: str = "embedding") -> str:
    """Suggest an appropriate HuggingFace model for a given task.
    
    Args:
        task_type: Type of task ("embedding", "classification", "generation")
        
    Returns:
        Recommended model name for the task
    """
    recommendations = {
        "embedding": "sentence-transformers/all-MiniLM-L6-v2",
        "semantic_search": "sentence-transformers/all-mpnet-base-v2", 
        "classification": "bert-base-uncased",
        "generation": "t5-base",
        "question_answering": "bert-large-uncased",
    }
    
    return recommendations.get(task_type, "sentence-transformers/all-MiniLM-L6-v2")


class HuggingFaceAdapter(TokenizerAdapter):
    """HuggingFace tokenizer adapter for transformer models.
    
    Supports a wide range of HuggingFace models including:
    - sentence-transformers models for semantic similarity
    - BERT family models (bert-base-uncased, distilbert, etc.)
    - RoBERTa family models
    - T5, BART, and other transformer architectures
    
    Features:
    - Automatic model detection and tokenizer loading
    - Configurable model selection with validation
    - Graceful fallback when transformers not available
    - Support for custom max_tokens override
    """

    def __init__(self, model_name: str, max_tokens: Optional[int] = None) -> None:
        # Validate model name format before calling parent constructor
        if model_name and not self._is_valid_model_name(model_name):
            raise ValueError(f"Invalid HuggingFace model name format: {model_name}")
        
        super().__init__(model_name, max_tokens)
        try:
            from transformers import AutoTokenizer
            
            # Load tokenizer with error handling
            self._tokenizer = self._load_tokenizer_safely(AutoTokenizer, model_name)
            
        except ImportError:
            raise ImportError("transformers package required for HuggingFaceAdapter")
        except Exception as e:
            raise ValueError(f"Failed to load HuggingFace tokenizer for {model_name}: {e}")

    def _is_valid_model_name(self, model_name: str) -> bool:
        """Validate HuggingFace model name format."""
        if not model_name or not isinstance(model_name, str):
            return False
        
        # Allow common patterns:
        # - organization/model-name (e.g., sentence-transformers/all-MiniLM-L6-v2)
        # - simple model names (e.g., bert-base-uncased)
        # - microsoft/model-name, facebook/model-name, etc.
        import re
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?(/[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?)*$'
        return bool(re.match(pattern, model_name))

    def _load_tokenizer_safely(self, AutoTokenizer, model_name: str):
        """Load tokenizer with comprehensive error handling."""
        try:
            # Try loading with default settings
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            return tokenizer
        except Exception as e:
            # Try with additional options for problematic models
            try:
                tokenizer = AutoTokenizer.from_pretrained(
                    model_name, 
                    use_fast=False,  # Fallback to slow tokenizer
                    trust_remote_code=False  # Security: don't execute remote code
                )
                return tokenizer
            except Exception as e2:
                # If both attempts fail, raise the original error
                raise e

    @property
    def adapter_id(self) -> str:
        """Unique identifier for this adapter."""
        return "huggingface"

    def count_tokens(self, text: str) -> TokenCount:
        if text is None:
            return TokenCount(
                count=0,
                method="huggingface",
                tokenizer_id=f"huggingface:{self._model_name}",
                is_exact=True,
                model_max_tokens=self.max_tokens(),
            )
        
        try:
            # Use add_special_tokens=True for consistency with model behavior
            tokens = self._tokenizer.encode(text, add_special_tokens=True)
            return TokenCount(
                count=len(tokens),
                method="huggingface",
                tokenizer_id=f"huggingface:{self._model_name}",
                is_exact=True,
                model_max_tokens=self.max_tokens(),
            )
        except Exception as e:
            logger.warning(f"HuggingFace tokenization failed for {self._model_name}: {e}")
            # Fallback to heuristic counting
            from .chunking import token_spans
            spans = token_spans(text)
            return TokenCount(
                count=len(spans),
                method="huggingface_fallback",
                tokenizer_id=f"huggingface_fallback:{self._model_name}",
                is_exact=False,
                model_max_tokens=self.max_tokens(),
            )

    def max_tokens(self) -> int:
        if self._max_tokens is not None:
            return self._max_tokens
        return resolve_model_max_tokens(self._model_name)

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model and tokenizer.
        
        Returns:
            Dictionary with model information including:
            - model_name: The HuggingFace model identifier
            - vocab_size: Size of the tokenizer vocabulary
            - max_tokens: Maximum token limit for the model
            - tokenizer_type: Type of tokenizer (fast/slow)
            - special_tokens: Information about special tokens
        """
        try:
            info = {
                "model_name": self._model_name,
                "max_tokens": self.max_tokens(),
                "adapter_id": self.adapter_id,
            }
            
            if hasattr(self, '_tokenizer'):
                info.update({
                    "vocab_size": self._tokenizer.vocab_size,
                    "tokenizer_type": "fast" if getattr(self._tokenizer, 'is_fast', False) else "slow",
                    "special_tokens": {
                        "pad_token": getattr(self._tokenizer, 'pad_token', None),
                        "unk_token": getattr(self._tokenizer, 'unk_token', None),
                        "cls_token": getattr(self._tokenizer, 'cls_token', None),
                        "sep_token": getattr(self._tokenizer, 'sep_token', None),
                        "mask_token": getattr(self._tokenizer, 'mask_token', None),
                    }
                })
            
            return info
        except Exception as e:
            logger.warning(f"Failed to get model info for {self._model_name}: {e}")
            return {
                "model_name": self._model_name,
                "max_tokens": self.max_tokens(),
                "adapter_id": self.adapter_id,
                "error": str(e)
            }


class TokenizerRegistry:
    """Registry for tokenizer adapters with fallback chain."""

    def __init__(self) -> None:
        self._adapters: Dict[str, Tuple[Type[TokenizerAdapter], Dict[str, Any]]] = {}
        self._fallback_chain: List[str] = ["tiktoken", "huggingface", "heuristic"]
        self._register_default_adapters()

    def _register_default_adapters(self) -> None:
        """Register default tokenizer adapters."""
        self.register("heuristic", HeuristicTokenizer, chars_per_token=4.0)
        self.register("tiktoken", TiktokenAdapter)
        self.register("huggingface", HuggingFaceAdapter)

    def register(
        self, 
        name: str, 
        adapter_class: Type[TokenizerAdapter], 
        **default_kwargs: Any
    ) -> None:
        """Register an adapter with default configuration.
        
        Args:
            name: Adapter name for resolution
            adapter_class: TokenizerAdapter subclass
            **default_kwargs: Default keyword arguments for adapter creation
        """
        if not name:
            raise ValueError("Adapter name must be non-empty")
        if not issubclass(adapter_class, TokenizerAdapter):
            raise ValueError("Adapter class must inherit from TokenizerAdapter")
        
        self._adapters[name.lower().strip()] = (adapter_class, default_kwargs)
        logger.debug(f"Registered tokenizer adapter: {name}")

    def set_fallback_chain(self, chain: List[str]) -> None:
        """Set the fallback chain for adapter resolution.
        
        Args:
            chain: List of adapter names in fallback order
        """
        if not chain:
            raise ValueError("Fallback chain must not be empty")
        
        # Validate all adapters in chain are registered
        for adapter_name in chain:
            if adapter_name.lower().strip() not in self._adapters:
                raise ValueError(f"Unknown adapter in fallback chain: {adapter_name}")
        
        self._fallback_chain = [name.lower().strip() for name in chain]
        logger.debug(f"Set fallback chain: {self._fallback_chain}")

    def resolve(
        self, 
        adapter_name: Optional[str] = None, 
        model_name: str = "default-model",
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> TokenizerAdapter:
        """Resolve adapter by name or use fallback chain.
        
        Args:
            adapter_name: Specific adapter name, or None for auto-resolution
            model_name: Model name for the adapter
            max_tokens: Optional max tokens override
            **kwargs: Additional adapter-specific arguments
            
        Returns:
            Configured TokenizerAdapter instance
            
        Raises:
            RuntimeError: If no adapter can be created
        """
        errors: List[str] = []
        
        # Try specific adapter first
        if adapter_name and adapter_name.lower().strip() != "auto":
            try:
                return self._create_adapter(
                    adapter_name.lower().strip(), 
                    model_name, 
                    max_tokens, 
                    **kwargs
                )
            except Exception as e:
                error_msg = f"{adapter_name}: {e}"
                errors.append(error_msg)
                logger.warning(f"Failed to create requested adapter {adapter_name}: {e}")
        
        # Try fallback chain
        for fallback_name in self._fallback_chain:
            try:
                adapter = self._create_adapter(fallback_name, model_name, max_tokens, **kwargs)
                if errors:
                    logger.info(f"Using fallback adapter {fallback_name} after errors: {errors}")
                return adapter
            except Exception as e:
                error_msg = f"{fallback_name}: {e}"
                errors.append(error_msg)
                logger.debug(f"Fallback adapter {fallback_name} failed: {e}")
        
        raise RuntimeError(f"No tokenizer adapter available. Errors: {errors}")

    def _create_adapter(
        self, 
        adapter_name: str, 
        model_name: str, 
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> TokenizerAdapter:
        """Create adapter instance with error handling."""
        if adapter_name not in self._adapters:
            raise ValueError(f"Unknown adapter: {adapter_name}")
        
        adapter_class, default_kwargs = self._adapters[adapter_name]
        
        # Merge default kwargs with provided kwargs
        merged_kwargs = {**default_kwargs, **kwargs}
        if max_tokens is not None:
            merged_kwargs["max_tokens"] = max_tokens
        
        try:
            return adapter_class(model_name, **merged_kwargs)
        except ImportError as e:
            # Re-raise ImportError with helpful message
            if "tiktoken" in str(e):
                raise ImportError(
                    f"TikToken adapter requires tiktoken package. "
                    f"Install with: pip install tiktoken. Original error: {e}"
                )
            elif "transformers" in str(e):
                raise ImportError(
                    f"HuggingFace adapter requires transformers package. "
                    f"Install with: pip install transformers. Original error: {e}"
                )
            else:
                raise ImportError(f"Missing dependency for {adapter_name} adapter: {e}")
        except Exception as e:
            # Wrap other exceptions with context
            raise RuntimeError(f"Failed to create {adapter_name} adapter: {e}")

    def list_adapters(self) -> List[str]:
        """List all registered adapter names."""
        return list(self._adapters.keys())

    def get_fallback_chain(self) -> List[str]:
        """Get current fallback chain."""
        return self._fallback_chain.copy()


# Global registry instance
_default_registry = TokenizerRegistry()


def resolve_tokenizer(
    adapter_name: str,
    model_name: str,
    max_tokens: Optional[int] = None,
    registry: Optional[TokenizerRegistry] = None,
) -> TokenizerAdapter:
    """Resolve a tokenizer adapter by name.
    
    Args:
        adapter_name: Name of the adapter to resolve
        model_name: Model name for the adapter
        max_tokens: Optional max tokens override
        registry: Optional registry instance (uses default if None)
        
    Returns:
        Configured TokenizerAdapter instance
        
    Raises:
        ValueError: If adapter_name is unknown
        ImportError: If required dependencies are missing
    """
    if registry is None:
        registry = _default_registry
    
    adapter_name_clean = adapter_name.lower().strip()
    
    # Handle "auto" - use fallback chain
    if adapter_name_clean == "auto":
        return registry.resolve(
            adapter_name=None,  # Use fallback chain
            model_name=model_name,
            max_tokens=max_tokens
        )
    
    # For specific adapter names, try direct resolution without fallback
    # to maintain backward compatibility with error handling
    if adapter_name_clean in registry.list_adapters():
        try:
            return registry._create_adapter(
                adapter_name_clean,
                model_name,
                max_tokens
            )
        except ImportError:
            # Re-raise ImportError for backward compatibility
            raise
        except Exception as e:
            # Convert other exceptions to ValueError for backward compatibility
            raise ValueError(f"Failed to create {adapter_name} adapter: {e}")
    
    # Unknown adapter - raise ValueError for backward compatibility
    raise ValueError(f"Unknown tokenizer adapter: {adapter_name}")


def get_default_registry() -> TokenizerRegistry:
    """Get the default tokenizer registry instance."""
    return _default_registry


def resolve_tokenizer_with_fallback(
    adapter_name: Optional[str] = None,
    model_name: str = "default-model",
    max_tokens: Optional[int] = None,
    registry: Optional[TokenizerRegistry] = None,
    **kwargs: Any
) -> TokenizerAdapter:
    """Resolve tokenizer with full fallback chain support.
    
    This is the enhanced version that supports fallback chains and
    graceful degradation. Use this for new code that wants the full
    registry functionality.
    
    Args:
        adapter_name: Specific adapter name, or None for auto-resolution
        model_name: Model name for the adapter
        max_tokens: Optional max tokens override
        registry: Optional registry instance (uses default if None)
        **kwargs: Additional adapter-specific arguments
        
    Returns:
        Configured TokenizerAdapter instance
        
    Raises:
        RuntimeError: If no adapter can be created
    """
    if registry is None:
        registry = _default_registry
    
    return registry.resolve(
        adapter_name=adapter_name,
        model_name=model_name,
        max_tokens=max_tokens,
        **kwargs
    )
