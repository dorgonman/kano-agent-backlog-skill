"""Tests for tokenizer adapter functionality.

This module tests both HeuristicTokenizer and TiktokenAdapter with:
- Adapter resolution and factory functions
- Token counting with various text types
- Fallback behavior for unknown models
- Conditional testing based on tiktoken availability
"""

import pytest
from typing import Optional
from unittest.mock import Mock, patch

from kano_backlog_core.tokenizer import (
    HeuristicTokenizer,
    TiktokenAdapter,
    TokenCount,
    TokenizerAdapter,
    resolve_tokenizer,
    resolve_model_max_tokens,
    DEFAULT_MAX_TOKENS,
    MODEL_MAX_TOKENS,
)

# Check if tiktoken is available
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


class TestHeuristicTokenizer:
    """Test suite for HeuristicTokenizer."""

    def test_heuristic_tokenizer_creation(self) -> None:
        """Test HeuristicTokenizer can be created with valid parameters."""
        tokenizer = HeuristicTokenizer("test-model")
        assert tokenizer.model_name == "test-model"
        assert isinstance(tokenizer, TokenizerAdapter)

    def test_heuristic_tokenizer_creation_with_max_tokens(self) -> None:
        """Test HeuristicTokenizer creation with custom max_tokens."""
        tokenizer = HeuristicTokenizer("test-model", max_tokens=1024)
        assert tokenizer.model_name == "test-model"
        assert tokenizer.max_tokens() == 1024

    def test_heuristic_tokenizer_empty_model_name_raises(self) -> None:
        """Test HeuristicTokenizer raises error for empty model name."""
        with pytest.raises(ValueError, match="model_name must be non-empty"):
            HeuristicTokenizer("")

    @pytest.mark.parametrize("text,expected_min_tokens", [
        ("Hello world", 2),  # At least 2 tokens
        ("Hello, world!", 4),  # Hello, world, !
        ("", 0),  # Empty text
        ("a", 1),  # Single character
        ("test_function_name", 1),  # Single token with underscore
        ("你好世界", 4),  # CJK characters (each char is a token)
        ("Hello 你好", 3),  # Mixed ASCII and CJK
    ])
    def test_heuristic_token_counting(self, text: str, expected_min_tokens: int) -> None:
        """Test HeuristicTokenizer token counting with various inputs."""
        tokenizer = HeuristicTokenizer("test-model")
        result = tokenizer.count_tokens(text)
        
        assert isinstance(result, TokenCount)
        assert result.count >= expected_min_tokens
        assert result.method == "heuristic"
        assert result.tokenizer_id == "heuristic:test-model"
        assert result.is_exact is False

    def test_heuristic_tokenizer_none_text_raises(self) -> None:
        """Test HeuristicTokenizer raises error for None text."""
        tokenizer = HeuristicTokenizer("test-model")
        with pytest.raises(ValueError, match="text must be a string"):
            tokenizer.count_tokens(None)

    def test_heuristic_max_tokens_default(self) -> None:
        """Test HeuristicTokenizer uses default max tokens for unknown model."""
        tokenizer = HeuristicTokenizer("unknown-model")
        assert tokenizer.max_tokens() == DEFAULT_MAX_TOKENS

    def test_heuristic_max_tokens_known_model(self) -> None:
        """Test HeuristicTokenizer uses known model max tokens."""
        tokenizer = HeuristicTokenizer("text-embedding-3-small")
        assert tokenizer.max_tokens() == MODEL_MAX_TOKENS["text-embedding-3-small"]

    def test_heuristic_max_tokens_override(self) -> None:
        """Test HeuristicTokenizer respects max_tokens override."""
        tokenizer = HeuristicTokenizer("text-embedding-3-small", max_tokens=2048)
        assert tokenizer.max_tokens() == 2048


@pytest.mark.skipif(not TIKTOKEN_AVAILABLE, reason="tiktoken not installed")
class TestTiktokenAdapter:
    """Test suite for TiktokenAdapter (requires tiktoken)."""

    def test_tiktoken_adapter_creation(self) -> None:
        """Test TiktokenAdapter can be created with valid parameters."""
        tokenizer = TiktokenAdapter("text-embedding-3-small")
        assert tokenizer.model_name == "text-embedding-3-small"
        assert isinstance(tokenizer, TokenizerAdapter)

    def test_tiktoken_adapter_creation_with_max_tokens(self) -> None:
        """Test TiktokenAdapter creation with custom max_tokens."""
        tokenizer = TiktokenAdapter("text-embedding-3-small", max_tokens=1024)
        assert tokenizer.model_name == "text-embedding-3-small"
        assert tokenizer.max_tokens() == 1024

    def test_tiktoken_adapter_empty_model_name_raises(self) -> None:
        """Test TiktokenAdapter raises error for empty model name."""
        with pytest.raises(ValueError, match="model_name must be non-empty"):
            TiktokenAdapter("")

    @pytest.mark.parametrize("text,expected_min_tokens", [
        ("Hello world", 2),  # At least 2 tokens
        ("Hello, world!", 3),  # Punctuation handling
        ("", 0),  # Empty text
        ("a", 1),  # Single character
        ("The quick brown fox jumps over the lazy dog", 8),  # Longer text
    ])
    def test_tiktoken_token_counting(self, text: str, expected_min_tokens: int) -> None:
        """Test TiktokenAdapter token counting with various inputs."""
        tokenizer = TiktokenAdapter("text-embedding-3-small")
        result = tokenizer.count_tokens(text)
        
        assert isinstance(result, TokenCount)
        assert result.count >= expected_min_tokens
        assert result.method == "tiktoken"
        assert result.tokenizer_id == "tiktoken:text-embedding-3-small"
        assert result.is_exact is True

    def test_tiktoken_none_text_handling(self) -> None:
        """Test TiktokenAdapter handles None text gracefully."""
        tokenizer = TiktokenAdapter("text-embedding-3-small")
        result = tokenizer.count_tokens(None)
        
        assert isinstance(result, TokenCount)
        assert result.count == 0
        assert result.method == "tiktoken"
        assert result.is_exact is True

    def test_tiktoken_fallback_to_cl100k_base(self) -> None:
        """Test TiktokenAdapter falls back to cl100k_base for unknown models."""
        # This should not raise an error even for unknown model names
        tokenizer = TiktokenAdapter("unknown-model-name")
        result = tokenizer.count_tokens("Hello world")
        
        assert isinstance(result, TokenCount)
        assert result.count > 0
        assert result.method == "tiktoken"
        assert result.tokenizer_id == "tiktoken:unknown-model-name"

    def test_tiktoken_with_custom_encoding(self) -> None:
        """Test TiktokenAdapter with custom encoding."""
        import tiktoken
        custom_encoding = tiktoken.get_encoding("cl100k_base")
        
        tokenizer = TiktokenAdapter("custom-model", encoding=custom_encoding)
        result = tokenizer.count_tokens("Hello world")
        
        assert isinstance(result, TokenCount)
        assert result.count > 0
        assert result.method == "tiktoken"

    def test_tiktoken_max_tokens_default(self) -> None:
        """Test TiktokenAdapter uses default max tokens for unknown model."""
        tokenizer = TiktokenAdapter("unknown-model")
        assert tokenizer.max_tokens() == DEFAULT_MAX_TOKENS

    def test_tiktoken_max_tokens_known_model(self) -> None:
        """Test TiktokenAdapter uses known model max tokens."""
        tokenizer = TiktokenAdapter("text-embedding-3-small")
        assert tokenizer.max_tokens() == MODEL_MAX_TOKENS["text-embedding-3-small"]

    def test_tiktoken_max_tokens_override(self) -> None:
        """Test TiktokenAdapter respects max_tokens override."""
        tokenizer = TiktokenAdapter("text-embedding-3-small", max_tokens=2048)
        assert tokenizer.max_tokens() == 2048


class TestTiktokenAdapterWithoutTiktoken:
    """Test TiktokenAdapter behavior when tiktoken is not available."""

    @pytest.mark.skipif(TIKTOKEN_AVAILABLE, reason="tiktoken is installed")
    def test_tiktoken_adapter_import_error(self) -> None:
        """Test TiktokenAdapter raises ImportError when tiktoken not available."""
        with pytest.raises(ImportError):
            TiktokenAdapter("text-embedding-3-small")

    def test_tiktoken_adapter_with_mocked_import_error(self) -> None:
        """Test TiktokenAdapter behavior with mocked import error."""
        # Since tiktoken is not available in this environment, 
        # TiktokenAdapter should raise ImportError
        if not TIKTOKEN_AVAILABLE:
            with pytest.raises(ImportError):
                TiktokenAdapter("text-embedding-3-small")
        else:
            pytest.skip("tiktoken is available, cannot test import error")


class TestResolveTokenizer:
    """Test suite for resolve_tokenizer factory function."""

    def test_resolve_heuristic_tokenizer(self) -> None:
        """Test resolve_tokenizer returns HeuristicTokenizer for 'heuristic'."""
        tokenizer = resolve_tokenizer("heuristic", "test-model")
        assert isinstance(tokenizer, HeuristicTokenizer)
        assert tokenizer.model_name == "test-model"

    def test_resolve_heuristic_tokenizer_case_insensitive(self) -> None:
        """Test resolve_tokenizer is case insensitive."""
        tokenizer = resolve_tokenizer("HEURISTIC", "test-model")
        assert isinstance(tokenizer, HeuristicTokenizer)
        
        tokenizer = resolve_tokenizer(" Heuristic ", "test-model")
        assert isinstance(tokenizer, HeuristicTokenizer)

    @pytest.mark.skipif(not TIKTOKEN_AVAILABLE, reason="tiktoken not installed")
    def test_resolve_tiktoken_adapter(self) -> None:
        """Test resolve_tokenizer returns TiktokenAdapter for 'tiktoken'."""
        tokenizer = resolve_tokenizer("tiktoken", "text-embedding-3-small")
        assert isinstance(tokenizer, TiktokenAdapter)
        assert tokenizer.model_name == "text-embedding-3-small"

    @pytest.mark.skipif(not TIKTOKEN_AVAILABLE, reason="tiktoken not installed")
    def test_resolve_tiktoken_adapter_case_insensitive(self) -> None:
        """Test resolve_tokenizer is case insensitive for tiktoken."""
        tokenizer = resolve_tokenizer("TIKTOKEN", "text-embedding-3-small")
        assert isinstance(tokenizer, TiktokenAdapter)
        
        tokenizer = resolve_tokenizer(" TikToken ", "text-embedding-3-small")
        assert isinstance(tokenizer, TiktokenAdapter)

    def test_resolve_tokenizer_with_max_tokens(self) -> None:
        """Test resolve_tokenizer passes max_tokens parameter."""
        tokenizer = resolve_tokenizer("heuristic", "test-model", max_tokens=1024)
        assert isinstance(tokenizer, HeuristicTokenizer)
        assert tokenizer.max_tokens() == 1024

    def test_resolve_tokenizer_unknown_adapter_raises(self) -> None:
        """Test resolve_tokenizer raises error for unknown adapter."""
        with pytest.raises(ValueError, match="Unknown tokenizer adapter: unknown"):
            resolve_tokenizer("unknown", "test-model")

    @pytest.mark.skipif(TIKTOKEN_AVAILABLE, reason="tiktoken is installed")
    def test_resolve_tiktoken_without_tiktoken_raises(self) -> None:
        """Test resolve_tokenizer raises ImportError for tiktoken when not available."""
        with pytest.raises(ImportError):
            resolve_tokenizer("tiktoken", "text-embedding-3-small")


class TestResolveModelMaxTokens:
    """Test suite for resolve_model_max_tokens function."""

    def test_resolve_known_model(self) -> None:
        """Test resolve_model_max_tokens returns correct value for known models."""
        for model_name, expected_tokens in MODEL_MAX_TOKENS.items():
            result = resolve_model_max_tokens(model_name)
            assert result == expected_tokens

    def test_resolve_unknown_model_default(self) -> None:
        """Test resolve_model_max_tokens returns default for unknown models."""
        result = resolve_model_max_tokens("unknown-model")
        assert result == DEFAULT_MAX_TOKENS

    def test_resolve_with_overrides(self) -> None:
        """Test resolve_model_max_tokens respects overrides."""
        overrides = {"custom-model": 4096, "text-embedding-3-small": 2048}
        
        # Override for custom model
        result = resolve_model_max_tokens("custom-model", overrides=overrides)
        assert result == 4096
        
        # Override for known model
        result = resolve_model_max_tokens("text-embedding-3-small", overrides=overrides)
        assert result == 2048
        
        # No override, use default
        result = resolve_model_max_tokens("unknown-model", overrides=overrides)
        assert result == DEFAULT_MAX_TOKENS

    def test_resolve_with_custom_default(self) -> None:
        """Test resolve_model_max_tokens respects custom default."""
        result = resolve_model_max_tokens("unknown-model", default=16384)
        assert result == 16384

    def test_resolve_empty_overrides(self) -> None:
        """Test resolve_model_max_tokens handles empty overrides."""
        result = resolve_model_max_tokens("text-embedding-3-small", overrides={})
        assert result == MODEL_MAX_TOKENS["text-embedding-3-small"]


class TestTokenizerIntegration:
    """Integration tests for tokenizer adapters."""

    def test_heuristic_vs_tiktoken_consistency(self) -> None:
        """Test that both tokenizers handle the same text consistently."""
        text = "This is a test sentence for tokenizer comparison."
        
        heuristic = HeuristicTokenizer("test-model")
        heuristic_result = heuristic.count_tokens(text)
        
        if TIKTOKEN_AVAILABLE:
            tiktoken_adapter = TiktokenAdapter("text-embedding-3-small")
            tiktoken_result = tiktoken_adapter.count_tokens(text)
            
            # Both should return positive token counts
            assert heuristic_result.count > 0
            assert tiktoken_result.count > 0
            
            # Methods should be different
            assert heuristic_result.method != tiktoken_result.method
            assert heuristic_result.is_exact != tiktoken_result.is_exact

    def test_deterministic_token_counting(self) -> None:
        """Test that token counting is deterministic."""
        text = "Deterministic test text for tokenizer validation."
        
        tokenizer = HeuristicTokenizer("test-model")
        
        # Multiple calls should return identical results
        result1 = tokenizer.count_tokens(text)
        result2 = tokenizer.count_tokens(text)
        
        assert result1.count == result2.count
        assert result1.method == result2.method
        assert result1.tokenizer_id == result2.tokenizer_id
        assert result1.is_exact == result2.is_exact

    @pytest.mark.parametrize("adapter_name,model_name", [
        ("heuristic", "any-model"),
        ("heuristic", "text-embedding-3-small"),
        pytest.param("tiktoken", "text-embedding-3-small", 
                    marks=pytest.mark.skipif(not TIKTOKEN_AVAILABLE, reason="tiktoken not installed")),
        pytest.param("tiktoken", "unknown-model", 
                    marks=pytest.mark.skipif(not TIKTOKEN_AVAILABLE, reason="tiktoken not installed")),
    ])
    def test_adapter_factory_integration(self, adapter_name: str, model_name: str) -> None:
        """Test adapter factory creates working tokenizers."""
        tokenizer = resolve_tokenizer(adapter_name, model_name)
        
        # Test basic functionality
        result = tokenizer.count_tokens("Hello world")
        assert isinstance(result, TokenCount)
        assert result.count > 0
        assert result.method in ["heuristic", "tiktoken"]
        assert tokenizer.model_name == model_name
        assert tokenizer.max_tokens() > 0


if __name__ == "__main__":
    pytest.main([__file__])