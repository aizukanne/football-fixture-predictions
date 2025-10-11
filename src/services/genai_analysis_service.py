"""
GenAI Analysis Service - AI provider integration for match analysis.
Supports Google Gemini and Claude AI with manual provider selection.
"""

import json
import time
from typing import Dict, Any, Tuple
from decimal import Decimal

# AI Provider imports
import google.generativeai as genai
import anthropic

from ..config.genai_config import GENAI_CONFIG, SYSTEM_INSTRUCTION, get_active_provider, validate_configuration


class GenAIAnalysisService:
    """Service for generating AI-powered match analysis."""
    
    def __init__(self):
        """Initialize AI providers based on configuration."""
        self.gemini_model = None
        self.claude_client = None
        
        # Validate configuration
        is_valid, error_msg = validate_configuration()
        if not is_valid:
            raise ValueError(f"Configuration error: {error_msg}")
        
        # Initialize the active provider
        active_provider = get_active_provider()
        if active_provider == 'gemini':
            self._init_gemini()
        elif active_provider == 'claude':
            self._init_claude()
        else:
            raise ValueError(f"Unknown provider: {active_provider}")
        
        print(f"GenAI Analysis Service initialized with provider: {active_provider}")
    
    def _init_gemini(self):
        """Initialize Google Gemini."""
        config = GENAI_CONFIG['gemini']
        
        if not config['api_key']:
            raise ValueError("Gemini API key not found. Set GEMINI_API_KEY environment variable")
        
        genai.configure(api_key=config['api_key'])
        
        generation_config = {
            "temperature": config['temperature'],
            "max_output_tokens": config['max_output_tokens'],
            "response_mime_type": "text/plain",
        }
        
        self.gemini_model = genai.GenerativeModel(
            model_name=config['model'],
            generation_config=generation_config,
            system_instruction=SYSTEM_INSTRUCTION
        )
        print("Gemini initialized successfully")
    
    def _init_claude(self):
        """Initialize Claude AI."""
        config = GENAI_CONFIG['claude']
        
        if not config['api_key']:
            raise ValueError("Claude API key not found. Set ANTHROPIC_API_KEY environment variable")
        
        self.claude_client = anthropic.Anthropic(api_key=config['api_key'])
        print("Claude initialized successfully")
    
    def generate_analysis(self, context: dict) -> Tuple[str, str, int]:
        """
        Generate match analysis using the manually configured AI provider.
        
        Args:
            context: Complete fixture and parameter context
            
        Returns:
            Tuple of (analysis_text, provider_used, generation_time_ms)
            
        Raises:
            Exception: If provider is not initialized or generation fails
        """
        active_provider = get_active_provider()
        
        if active_provider == 'gemini':
            if not self.gemini_model:
                raise Exception("Gemini provider not initialized")
            return self._generate_with_gemini(context)
        
        elif active_provider == 'claude':
            if not self.claude_client:
                raise Exception("Claude provider not initialized")
            return self._generate_with_claude(context)
        
        else:
            raise Exception(f"Invalid active_provider: {active_provider}. Must be 'gemini' or 'claude'")
    
    def _generate_with_gemini(self, context: dict) -> Tuple[str, str, int]:
        """
        Generate analysis using Gemini.
        
        Args:
            context: Complete fixture context
            
        Returns:
            Tuple of (analysis_text, provider='gemini', generation_time_ms)
        """
        start_time = time.time()
        
        try:
            # Convert context to JSON string for prompt
            prompt = json.dumps(context, default=self._decimal_default, indent=2)
            
            # Generate content
            response = self.gemini_model.generate_content(prompt)
            
            # Extract text from response
            if hasattr(response, 'candidates') and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    if len(candidate.content.parts) > 0:
                        analysis_text = candidate.content.parts[0].text
                    else:
                        raise Exception("No text parts in Gemini response")
                else:
                    raise Exception("Invalid Gemini response structure")
            else:
                raise Exception("No candidates in Gemini response")
            
            generation_time_ms = int((time.time() - start_time) * 1000)
            
            print(f"Gemini generation completed in {generation_time_ms}ms")
            return analysis_text, 'gemini', generation_time_ms
            
        except Exception as e:
            print(f"Gemini generation error: {e}")
            raise Exception(f"Gemini generation failed: {str(e)}")
    
    def _generate_with_claude(self, context: dict) -> Tuple[str, str, int]:
        """
        Generate analysis using Claude.
        
        Args:
            context: Complete fixture context
            
        Returns:
            Tuple of (analysis_text, provider='claude', generation_time_ms)
        """
        start_time = time.time()
        
        try:
            # Convert context to JSON string
            prompt = json.dumps(context, default=self._decimal_default, indent=2)
            
            # Get Claude configuration
            config = GENAI_CONFIG['claude']
            
            # Generate content
            response = self.claude_client.messages.create(
                model=config['model'],
                max_tokens=config['max_tokens'],
                temperature=config['temperature'],
                system=SYSTEM_INSTRUCTION,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Extract text from response
            if hasattr(response, 'content') and len(response.content) > 0:
                analysis_text = response.content[0].text
            else:
                raise Exception("No content in Claude response")
            
            generation_time_ms = int((time.time() - start_time) * 1000)
            
            print(f"Claude generation completed in {generation_time_ms}ms")
            return analysis_text, 'claude', generation_time_ms
            
        except Exception as e:
            print(f"Claude generation error: {e}")
            raise Exception(f"Claude generation failed: {str(e)}")
    
    @staticmethod
    def _decimal_default(obj):
        """
        Handle Decimal serialization for JSON.
        
        Args:
            obj: Object to serialize
            
        Returns:
            Float representation of Decimal, or raises TypeError
        """
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    def get_provider_info(self) -> dict:
        """
        Get information about the current provider configuration.
        
        Returns:
            Dictionary with provider information
        """
        active_provider = get_active_provider()
        config = GENAI_CONFIG[active_provider]
        
        return {
            'active_provider': active_provider,
            'model': config['model'],
            'temperature': config['temperature'],
            'max_tokens': config.get('max_output_tokens') or config.get('max_tokens'),
            'initialized': (self.gemini_model is not None) if active_provider == 'gemini' else (self.claude_client is not None)
        }