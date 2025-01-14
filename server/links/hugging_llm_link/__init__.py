"""
This module implements an LLM analysis service using HuggingFace's API to process vCon
transcripts. It provides functionality to analyze transcribed conversations in vCon
documents using language models and stores the results. The module includes retry logic,
error tracking, and metrics collection.

Key Components:
- LLMConfig: Configuration settings for the LLM service
- HuggingFaceLLM: Handles API communication with HuggingFace
- VConLLMProcessor: Processes vCon documents for LLM analysis

Dependencies:
- HuggingFace API for language model inference
- Redis for vCon document storage
- Tenacity for retry logic
- Custom logging and metrics utilities
"""

# Standard library imports
import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

# Third-party imports
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    RetryError,
    before_sleep_log,
)
import transformers
import anyio

# Local imports
from lib.logging_utils import init_logger
from lib.error_tracking import init_error_tracker
from lib.metrics import init_metrics, stats_gauge, stats_count
from server.lib.vcon_redis import VconRedis

# Initialize services
init_error_tracker()
init_metrics()
logger = init_logger(__name__)


@dataclass
class LLMConfig:
    """Configuration settings for the LLM service."""

    huggingface_api_key: Optional[str] = None
    model: str = "meta-llama/Llama-2-70b-chat-hf"
    use_local_model: bool = False
    max_length: int = 1000
    temperature: float = 0.7

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "LLMConfig":
        return cls(
            huggingface_api_key=config_dict.get("HUGGINGFACE_API_KEY"),
            model=config_dict.get("model", cls.model),
            use_local_model=config_dict.get("use_local_model", False),
            max_length=config_dict.get("max_length", cls.max_length),
            temperature=config_dict.get("temperature", cls.temperature),
        )


class BaseLLM(ABC):
    """Abstract base class for LLM implementations."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    def analyze(self, text: str) -> Optional[Dict[str, Any]]:
        """Process text with LLM and return results."""
        pass


class HuggingFaceLLM(BaseLLM):
    """API-based LLM implementation."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)

    @retry(
        wait=wait_exponential(multiplier=2, min=1, max=65),
        stop=stop_after_attempt(6),
        before_sleep=before_sleep_log(logger, logging.INFO),
    )
    async def analyze(self, text: str) -> Optional[Dict[str, Any]]:
        """Process text using HuggingFace's API.

        Args:
            text: Text to analyze

        Returns:
            Dict containing:
                - summary: Brief summary of the conversation
                - sentiment: Overall sentiment analysis
                - key_points: List of key discussion points

        Raises:
            Exception: If the API request fails after all retry attempts
            RetryError: If max retry attempts are exceeded
        """
        headers = {"Authorization": f"Bearer {self.config.huggingface_api_key}"}
        api_url = f"https://api-inference.huggingface.co/models/{self.config.model}"

        prompt = f"""Analyze the following conversation and provide:
1. A brief summary
2. The overall sentiment
3. Key discussion points

Conversation:
{text}

Provide the response in JSON format with keys: summary, sentiment, key_points"""

        response = await anyio.to_thread.run_sync(
            lambda: requests.post(
                api_url,
                headers=headers,
                json={
                    "inputs": prompt,
                    "parameters": {
                        "max_length": self.config.max_length,
                        "temperature": self.config.temperature,
                    },
                },
            )
        )

        if response.status_code != 200:
            raise Exception(f"Hugging Face API error: {response.text}")

        result = response.json()

        return {
            "analysis": result[0]["generated_text"],
            "model": self.config.model,
            "parameters": {
                "max_length": self.config.max_length,
                "temperature": self.config.temperature,
            },
        }


class LocalHuggingFaceLLM(BaseLLM):
    """Local model-based LLM implementation."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        logger.info(f"Initializing local model: {self.config.model}")
        device = "cuda" if transformers.is_torch_available() else "cpu"
        logger.info(f"Using device: {device}")
        self.pipeline = transformers.pipeline(
            "text-generation",
            model=self.config.model,
            device=device,
        )
        logger.info("Local model initialized successfully")

    @retry(
        wait=wait_exponential(multiplier=2, min=1, max=65),
        stop=stop_after_attempt(6),
        before_sleep=before_sleep_log(logger, logging.INFO),
    )
    def analyze(self, text: str) -> Optional[Dict[str, Any]]:
        """Process text using local HuggingFace model."""
        try:
            logger.info(f"Starting local model analysis with {self.config.model}")
            prompt = f"""Analyze the following conversation and provide:
1. A brief summary
2. The overall sentiment
3. Key discussion points

Conversation:
{text}

Provide the response in JSON format with keys: summary, sentiment, key_points"""

            logger.debug(f"Input text length: {len(text)} characters")
            result = self.pipeline(
                prompt,
                max_length=self.config.max_length,
                temperature=self.config.temperature,
            )
            logger.info("Local model analysis completed successfully")

            return {
                "analysis": result[0]["generated_text"],
                "model": self.config.model,
                "parameters": {
                    "max_length": self.config.max_length,
                    "temperature": self.config.temperature,
                },
            }
        except Exception as e:
            logger.error(f"Local LLM error: {str(e)}")
            raise


class VConLLMProcessor:
    """Processes vCon documents for LLM analysis.

    This class orchestrates the LLM analysis workflow:
    1. Retrieves vCon documents from Redis
    2. Extracts transcripts from the documents
    3. Processes transcripts with LLM
    4. Updates vCon documents with analysis results
    5. Stores updated documents back to Redis
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self.llm = LocalHuggingFaceLLM(config) if config.use_local_model else HuggingFaceLLM(config)
        self.vcon_redis = VconRedis()

    def _get_llm_analysis(self, vcon) -> Optional[Dict]:
        """Get existing LLM analysis from vCon."""
        return next((a for a in vcon.analysis if a["type"] == "llm_analysis"), None)

    def _get_transcript_text(self, vcon) -> str:
        """Extract transcript text from vCon document."""
        transcript_text = ""
        for analysis in vcon.analysis:
            if analysis["type"] == "transcript":
                transcript = analysis["body"].get("transcript", "")
                if transcript:
                    transcript_text += transcript + "\n"
        return transcript_text.strip()

    def process_vcon(self, vcon_uuid: str, link_name: str) -> str:
        """Process a vCon document by analyzing its transcripts with LLM.

        Workflow:
        1. Retrieves vCon from Redis
        2. Extracts transcript text
        3. Processes text with LLM
        4. Updates vCon with analysis results
        5. Stores updated vCon back to Redis

        Args:
            vcon_uuid: UUID of the vCon to process
            link_name: Name of the link being processed

        Returns:
            str: UUID of the processed vCon

        Side Effects:
            - Updates vCon document in Redis
            - Records metrics and logs
        """
        logger.info("Starting huggingface LLM analysis for vCon: %s", vcon_uuid)

        vcon = self.vcon_redis.get_vcon(vcon_uuid)

        if self._get_llm_analysis(vcon):
            logger.info("VCon %s already has LLM analysis", vcon_uuid)
            return vcon_uuid

        transcript_text = self._get_transcript_text(vcon)
        if not transcript_text:
            logger.info("No transcript found in vCon: %s", vcon_uuid)
            return vcon_uuid

        try:
            start = time.time()
            result = self.llm.analyze(transcript_text)
            stats_gauge("conserver.link.huggingface.llm_time", time.time() - start)
        except (RetryError, Exception) as e:
            logger.error("Failed to analyze vCon %s: %s", vcon_uuid, str(e))
            stats_count("conserver.link.huggingface.llm_failures")
            return vcon_uuid

        self._add_analysis_to_vcon(vcon, result)

        self.vcon_redis.store_vcon(vcon)
        logger.info("Finished huggingface LLM analysis for vCon: %s", vcon_uuid)
        return vcon_uuid

    def _add_analysis_to_vcon(self, vcon, result: Dict):
        """Add LLM analysis to vCon."""
        vendor_schema = {
            "opts": {
                "model": self.config.model,
                "max_length": self.config.max_length,
                "temperature": self.config.temperature,
            }
        }

        vcon.add_analysis(
            type="llm_analysis",
            vendor="huggingface",
            body=result,
            extra={"vendor_schema": vendor_schema},
        )


def run(vcon_uuid: str, link_name: str, opts: Dict = None) -> str:
    """Main entry point for the LLM analysis service.

    Args:
        vcon_uuid: UUID of the vCon to process
        link_name: Name of the link being processed
        opts: Optional configuration overrides

    Returns:
        str: UUID of the processed vCon
    """
    config = LLMConfig.from_dict(opts or {})
    processor = VConLLMProcessor(config)
    return processor.process_vcon(vcon_uuid, link_name)
