"""
OpenAI Chat Completions API utility for vcon-server
Provides a unified interface for the new Responses API
"""

import os
import logging
from typing import Dict, List, Optional, Any, Union
from openai import OpenAI

logger = logging.getLogger(__name__)

class OpenAIChatClient:
    """
    Wrapper for OpenAI's Chat Completions API (the one that actually exists)
    """
    
    def __init__(self, api_key: Optional[str] = None, timeout: float = 120.0, max_retries: int = 0):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = OpenAI(
            api_key=self.api_key,
            timeout=timeout,
            max_retries=max_retries
        )
        
    def create_completion(
        self,
        input_text: str,
        instructions: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        response_format: Optional[Dict] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a completion using the Chat Completions API
        
        Args:
            input_text: The user input/prompt
            instructions: System instructions (system message)
            model: Model to use
            temperature: Sampling temperature
            response_format: For structured outputs (JSON)
            tools: List of tools/functions to make available
            **kwargs: Additional parameters
            
        Returns:
            Dict containing response data and metadata
        """
        try:
            # Build messages array
            messages = []
            
            # Add system message if provided
            if instructions:
                messages.append({"role": "system", "content": instructions})
            
            # Add user message
            messages.append({"role": "user", "content": input_text})
            
            # Build request parameters
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                **kwargs
            }
            
            # Add structured output format if provided
            if response_format:
                params["response_format"] = response_format
            
            # Add tools if provided
            if tools:
                params["tools"] = tools
            
            # Make the API call
            response = self.client.chat.completions.create(**params)
            
            # Extract response data
            result = {
                "text": response.choices[0].message.content,
                "model": response.model,
                "usage": response.usage.dict() if response.usage else None,
                "raw_response": response
            }
            
            # Handle tool calls if present
            if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                result["tool_calls"] = response.choices[0].message.tool_calls
            
            return result
            
        except Exception as e:
            logger.error(f"OpenAI Chat Completions API error: {str(e)}")
            raise

# Legacy compatibility function for easier migration
def migrate_to_chat_completions(
    messages: List[Dict[str, str]],
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    api_key: Optional[str] = None,
    timeout: float = 120.0,
    max_retries: int = 0,
    **kwargs
) -> Dict[str, Any]:
    """
    Use the actual Chat Completions API
    """
    client = OpenAIChatClient(api_key=api_key, timeout=timeout, max_retries=max_retries)
    
    # Extract system and user messages
    instructions = None
    user_input = ""
    
    for message in messages:
        if message.get("role") == "system":
            instructions = message.get("content", "")
        elif message.get("role") == "user":
            user_input = message.get("content", "")
    
    return client.create_completion(
        input_text=user_input,
        instructions=instructions,
        model=model,
        temperature=temperature,
        **kwargs
    )