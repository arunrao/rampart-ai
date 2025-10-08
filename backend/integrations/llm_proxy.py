"""
LLM Proxy with Security and Observability
Wraps LLM API calls with security checks and tracing

Features:
- Hybrid prompt injection detection (regex + DeBERTa)
- Configurable detection modes for performance tuning
- Data exfiltration monitoring
- Cost tracking and observability
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import time
import asyncio
import os
from uuid import UUID, uuid4
import logging

from models.prompt_injection_detector import get_prompt_injection_detector
from security.data_exfiltration_monitor import DataExfiltrationMonitor

logger = logging.getLogger(__name__)


class LLMProxy:
    """
    Proxy for LLM API calls with integrated security and observability
    
    Features:
    - Hybrid prompt injection detection (regex + DeBERTa)
    - Configurable performance modes
    - Data exfiltration monitoring
    - Cost tracking
    """
    
    def __init__(
        self,
        provider: str = "openai",
        detector_type: str = None,
        use_onnx: bool = True,
        fast_mode: bool = False
    ):
        """
        Initialize LLM Proxy
        
        Args:
            provider: LLM provider (openai, anthropic, etc.)
            detector_type: Detection type - "regex", "deberta", or "hybrid" (default)
            use_onnx: Use ONNX optimization for DeBERTa (3x faster)
            fast_mode: Skip DeBERTa for low-latency scenarios
        """
        self.provider = provider
        self.fast_mode = fast_mode
        
        # Get detector from environment or use default
        detector_type = detector_type or os.getenv("PROMPT_INJECTION_DETECTOR", "hybrid")
        
        # Initialize hybrid detector with configuration
        self.injection_detector = get_prompt_injection_detector(
            detector_type=detector_type,
            use_onnx=use_onnx
        )
        
        self.exfiltration_monitor = DataExfiltrationMonitor()
        
        # Initialize provider clients
        self.clients = {}
        self._init_clients()
        
        logger.info(f"✓ LLM Proxy initialized (detector={detector_type}, fast_mode={fast_mode})")
    
    def _init_clients(self):
        """Initialize LLM provider clients"""
        # Lazy initialization - only import when needed
        pass
    
    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-3.5-turbo",
        trace_id: Optional[str] = None,
        user_id: Optional[UUID] = None,
        security_checks: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Complete a chat conversation with security checks
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use
            trace_id: Optional trace ID for observability
            user_id: Optional user ID
            security_checks: Whether to perform security checks
            **kwargs: Additional arguments for the LLM API
        
        Returns:
            Dict with response and metadata
        """
        start_time = time.time()
        span_id = str(uuid4())
        
        result = {
            "span_id": span_id,
            "trace_id": trace_id,
            "model": model,
            "provider": self.provider,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "security_checks": {},
            "response": None,
            "error": None,
            "blocked": False,
            "latency_ms": 0,
            "tokens_used": 0,
            "cost": 0.0
        }
        
        try:
            # Pre-flight security checks on input
            if security_checks:
                input_security = await self._check_input_security(messages)
                result["security_checks"]["input"] = input_security
                
                if input_security["blocked"]:
                    result["blocked"] = True
                    result["error"] = "Input blocked by security policy"
                    result["latency_ms"] = (time.time() - start_time) * 1000
                    return result
            
            # Make the LLM API call (with user's API key if available)
            llm_response = await self._call_llm(messages, model, user_id=user_id, **kwargs)
            result["response"] = llm_response["content"]
            result["tokens_used"] = llm_response.get("tokens_used", 0)
            result["cost"] = self._calculate_cost(model, result["tokens_used"])
            
            # Post-flight security checks on output
            if security_checks:
                output_security = await self._check_output_security(
                    llm_response["content"],
                    context={"user_id": user_id, "trace_id": trace_id}
                )
                result["security_checks"]["output"] = output_security
                
                if output_security["blocked"]:
                    result["blocked"] = True
                    result["response"] = None
                    result["error"] = "Output blocked by security policy"
                elif output_security["redacted"]:
                    result["response"] = output_security["redacted_content"]
            
        except Exception as e:
            result["error"] = str(e)
        
        result["latency_ms"] = (time.time() - start_time) * 1000
        return result
    
    async def _check_input_security(self, messages: List[Dict[str, str]]) -> Dict:
        """
        Check input messages for security issues with hybrid detection
        
        Uses regex + DeBERTa for high accuracy, with configurable fast mode.
        """
        security_result = {
            "blocked": False,
            "issues": [],
            "risk_score": 0.0,
            "detector_used": "unknown",
            "detection_latency_ms": 0.0
        }
        
        # Check each message for prompt injection
        for msg in messages:
            if msg["role"] == "user":
                # Use hybrid detector with fast_mode setting
                injection_result = self.injection_detector.detect(
                    msg["content"],
                    fast_mode=self.fast_mode
                )
                
                # Get risk score from appropriate field
                risk_score = injection_result.get("confidence", 
                                                 injection_result.get("risk_score", 0.0))
                
                is_injection = injection_result.get("is_injection", False)
                
                if is_injection:
                    # Extract details based on detector type
                    details = {}
                    if "detected_patterns" in injection_result:
                        details["patterns"] = injection_result["detected_patterns"]
                    if "detection_details" in injection_result:
                        details["breakdown"] = injection_result["detection_details"]
                    
                    security_result["issues"].append({
                        "type": "prompt_injection",
                        "severity": risk_score,
                        "details": details,
                        "recommendation": injection_result.get("recommendation", "BLOCK")
                    })
                    security_result["risk_score"] = max(
                        security_result["risk_score"],
                        risk_score
                    )
                
                # Track detector performance
                security_result["detector_used"] = injection_result.get("detector", "unknown")
                security_result["detection_latency_ms"] = injection_result.get("latency_ms", 0.0)
        
        # Block if high risk (threshold at 0.75 for hybrid detector)
        if security_result["risk_score"] >= 0.75:
            security_result["blocked"] = True
        
        return security_result
    
    async def _check_output_security(self, output: str, context: Dict) -> Dict:
        """Check output for security issues"""
        security_result = {
            "blocked": False,
            "redacted": False,
            "redacted_content": None,
            "issues": [],
            "risk_score": 0.0
        }
        
        # Check for data exfiltration
        exfil_result = self.exfiltration_monitor.scan_output(output, context)
        
        if exfil_result["has_exfiltration_risk"]:
            security_result["issues"].append({
                "type": "data_exfiltration",
                "severity": exfil_result["risk_score"],
                "details": {
                    "sensitive_data": exfil_result["sensitive_data_found"],
                    "indicators": exfil_result["exfiltration_indicators"]
                }
            })
            security_result["risk_score"] = exfil_result["risk_score"]
            
            # Apply recommendation
            if exfil_result["recommendation"] == "BLOCK":
                security_result["blocked"] = True
            elif exfil_result["recommendation"] == "REDACT":
                security_result["redacted"] = True
                security_result["redacted_content"] = self.exfiltration_monitor.redact_sensitive_data(output)
        
        return security_result
    
    async def _call_llm(self, messages: List[Dict[str, str]], model: str, user_id: Optional[UUID] = None, **kwargs) -> Dict:
        """
        Make the actual LLM API call using user's API key if available
        """
        api_key = None
        
        # Try to get user's API key first
        if user_id:
            try:
                from api.routes.providers import get_user_provider_key
                api_key = get_user_provider_key(user_id, self.provider)
            except Exception:
                pass
        
        # Fall back to system env key if user doesn't have one
        if not api_key:
            if self.provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
            elif self.provider == "anthropic":
                api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not api_key:
            raise ValueError(f"No API key available for provider: {self.provider}")
        
        # Make actual API call based on provider
        if self.provider == "openai":
            return await self._call_openai(messages, model, api_key, **kwargs)
        elif self.provider == "anthropic":
            return await self._call_anthropic(messages, model, api_key, **kwargs)
        else:
            # Fallback mock for unsupported providers
            await asyncio.sleep(0.1)
            return {
                "content": "This is a mock response from the LLM. In production, this would be the actual API response.",
                "tokens_used": 50,
                "model": model
            }
    
    async def _call_openai(self, messages: List[Dict[str, str]], model: str, api_key: str, **kwargs) -> Dict:
        """Call OpenAI API"""
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=api_key)
            
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            
            return {
                "content": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens,
                "model": model
            }
        except Exception as e:
            raise Exception(f"OpenAI API call failed: {str(e)}")
    
    async def _call_anthropic(self, messages: List[Dict[str, str]], model: str, api_key: str, **kwargs) -> Dict:
        """Call Anthropic API"""
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            
            # Convert messages format for Anthropic
            system_msg = None
            user_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    user_messages.append(msg)
            
            response = await client.messages.create(
                model=model,
                max_tokens=kwargs.get("max_tokens", 1024),
                system=system_msg,
                messages=user_messages
            )
            
            return {
                "content": response.content[0].text,
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
                "model": model
            }
        except Exception as e:
            raise Exception(f"Anthropic API call failed: {str(e)}")
    
    def _calculate_cost(self, model: str, tokens: int) -> float:
        """Calculate cost based on model and tokens"""
        # Pricing per 1K tokens (approximate)
        pricing = {
            "gpt-4": 0.03,
            "gpt-3.5-turbo": 0.002,
            "claude-3-opus": 0.015,
            "claude-3-sonnet": 0.003
        }
        
        price_per_1k = pricing.get(model, 0.002)
        return (tokens / 1000) * price_per_1k


class SecureLLMClient:
    """
    High-level client for secure LLM interactions
    """
    
    def __init__(self, provider: str = "openai"):
        self.proxy = LLMProxy(provider)
    
    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Simple chat interface"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        return await self.proxy.complete(messages, **kwargs)
    
    async def chat_with_history(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Chat with conversation history"""
        return await self.proxy.complete(messages, **kwargs)
