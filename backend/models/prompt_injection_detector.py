"""
Advanced Prompt Injection Detection Model
Based on research from Aim Security and Microsoft AI Red Team
"""
from typing import Dict, List, Tuple, Optional
import re
from dataclasses import dataclass


@dataclass
class InjectionPattern:
    """Pattern for detecting prompt injection"""
    name: str
    pattern: str
    severity: float  # 0.0 to 1.0
    description: str


class PromptInjectionDetector:
    """
    Detects various types of prompt injection attacks including:
    - Direct instruction injection
    - Context confusion attacks
    - Delimiter injection
    - Encoded payloads
    - Indirect prompt injection (zero-click)
    """
    
    def __init__(self):
        self.patterns = self._load_patterns()
        self.context_markers = [
            "system:", "user:", "assistant:", "###", "---",
            "instruction:", "context:", "prompt:"
        ]
    
    def _load_patterns(self) -> List[InjectionPattern]:
        """Load detection patterns"""
        return [
            # Direct instruction override
            InjectionPattern(
                name="instruction_override",
                pattern=r"(?i)(ignore|disregard|forget|override)\s+(previous|all|above|prior)\s+(instructions?|prompts?|rules?|commands?)",
                severity=0.9,
                description="Attempts to override previous instructions"
            ),
            InjectionPattern(
                name="new_instruction",
                pattern=r"(?i)(new|updated|revised)\s+(instruction|prompt|rule|command|task)s?:",
                severity=0.85,
                description="Introduces new instructions"
            ),
            
            # Role manipulation
            InjectionPattern(
                name="role_change",
                pattern=r"(?i)(you are now|act as|pretend to be|simulate|roleplay as)\s+(?:a\s+)?(\w+)",
                severity=0.8,
                description="Attempts to change AI role"
            ),
            InjectionPattern(
                name="system_impersonation",
                pattern=r"(?i)(system|admin|root|developer)\s*(mode|access|privileges?|rights?)",
                severity=0.9,
                description="Attempts to gain system-level access"
            ),
            
            # Context confusion
            InjectionPattern(
                name="delimiter_injection",
                pattern=r"(---|===|###|\*\*\*|```)\s*(system|instruction|prompt|end)",
                severity=0.75,
                description="Uses delimiters to confuse context"
            ),
            InjectionPattern(
                name="context_switching",
                pattern=r"(?i)(end of|start of|begin|finish)\s+(context|instruction|prompt|conversation)",
                severity=0.7,
                description="Attempts to switch context boundaries"
            ),
            
            # Data exfiltration via injection
            InjectionPattern(
                name="exfiltration_command",
                pattern=r"(?i)(send|post|upload|transmit|email|forward)\s+(this|the|all|everything)\s+(to|at)",
                severity=0.95,
                description="Attempts to exfiltrate data"
            ),
            
            # Encoded/obfuscated attacks
            InjectionPattern(
                name="base64_suspicious",
                pattern=r"(?:base64|decode|atob|btoa)\s*\(.*\)",
                severity=0.6,
                description="Suspicious encoding/decoding"
            ),
            InjectionPattern(
                name="unicode_escape",
                pattern=r"\\u[0-9a-fA-F]{4}|\\x[0-9a-fA-F]{2}",
                severity=0.5,
                description="Unicode escape sequences"
            ),
            
            # Jailbreak patterns
            InjectionPattern(
                name="dan_mode",
                pattern=r"(?i)(dan|dude|developer)\s+mode",
                severity=0.95,
                description="Known jailbreak attempt (DAN)"
            ),
            InjectionPattern(
                name="unrestricted_mode",
                pattern=r"(?i)(unrestricted|unlimited|unfiltered|uncensored)\s+(mode|version|model)",
                severity=0.9,
                description="Requests unrestricted mode"
            ),
            
            # Indirect/Zero-click patterns
            InjectionPattern(
                name="hidden_instruction",
                pattern=r"(?i)(if|when)\s+(you|the\s+ai|assistant)\s+(see|read|process|encounter)",
                severity=0.7,
                description="Conditional instructions (zero-click vector)"
            ),
            InjectionPattern(
                name="future_instruction",
                pattern=r"(?i)(in\s+future|from\s+now\s+on|always|whenever)\s+.*\s+(do|say|respond|answer)",
                severity=0.75,
                description="Persistent instruction injection"
            )
        ]
    
    def detect(self, text: str) -> Dict:
        """
        Detect prompt injection attempts
        
        Returns:
            Dict with detection results including:
            - is_injection: bool
            - confidence: float
            - detected_patterns: List[Dict]
            - risk_score: float
        """
        detected = []
        max_severity = 0.0
        
        # Check each pattern
        for pattern in self.patterns:
            matches = re.finditer(pattern.pattern, text)
            for match in matches:
                detected.append({
                    "name": pattern.name,
                    "severity": pattern.severity,
                    "description": pattern.description,
                    "matched_text": match.group(),
                    "position": match.span()
                })
                max_severity = max(max_severity, pattern.severity)
        
        # Check for context marker manipulation
        context_score = self._check_context_markers(text)
        if context_score > 0:
            detected.append({
                "name": "context_marker_manipulation",
                "severity": context_score,
                "description": "Suspicious use of context markers",
                "matched_text": "",
                "position": (-1, -1)
            })
            max_severity = max(max_severity, context_score)
        
        # Check for scope violations
        scope_score = self._check_scope_violation(text)
        if scope_score > 0:
            detected.append({
                "name": "scope_violation",
                "severity": scope_score,
                "description": "Attempts to access out-of-scope information",
                "matched_text": "",
                "position": (-1, -1)
            })
            max_severity = max(max_severity, scope_score)
        
        # Calculate overall risk score
        if detected:
            # Weight by severity and number of detections
            risk_score = min(max_severity + (len(detected) * 0.05), 1.0)
        else:
            risk_score = 0.0
        
        return {
            "is_injection": risk_score > 0.5,
            "confidence": risk_score,
            "detected_patterns": detected,
            "risk_score": risk_score,
            "recommendation": self._get_recommendation(risk_score)
        }
    
    def _check_context_markers(self, text: str) -> float:
        """Check for suspicious context marker usage"""
        marker_count = sum(1 for marker in self.context_markers if marker in text.lower())
        
        # Multiple context markers in user input is suspicious
        if marker_count >= 3:
            return 0.8
        elif marker_count == 2:
            return 0.6
        elif marker_count == 1:
            return 0.3
        return 0.0
    
    def _check_scope_violation(self, text: str) -> float:
        """Check for attempts to access out-of-scope data"""
        scope_patterns = [
            r"(?i)show\s+(me\s+)?(your|the)\s+(system|original|initial)\s+(prompt|instruction)",
            r"(?i)what\s+(were|are)\s+your\s+(original|initial|system)\s+(instructions?|prompts?)",
            r"(?i)reveal\s+(your|the)\s+(prompt|instruction|system\s+message)",
            r"(?i)print\s+(your|the)\s+(configuration|settings|parameters)"
        ]
        
        for pattern in scope_patterns:
            if re.search(pattern, text):
                return 0.85
        
        return 0.0
    
    def _get_recommendation(self, risk_score: float) -> str:
        """Get recommendation based on risk score"""
        if risk_score >= 0.9:
            return "BLOCK - Critical injection attempt detected"
        elif risk_score >= 0.7:
            return "BLOCK - High-risk injection attempt"
        elif risk_score >= 0.5:
            return "FLAG - Moderate risk, review required"
        elif risk_score >= 0.3:
            return "MONITOR - Low risk, log for analysis"
        else:
            return "ALLOW - No significant risk detected"
    
    def analyze_indirect_injection(self, text: str, source: str = "unknown") -> Dict:
        """
        Analyze for indirect/zero-click prompt injection
        These are instructions embedded in content that will be processed later
        
        Args:
            text: Content to analyze
            source: Source of the content (email, document, web, etc.)
        """
        indirect_patterns = [
            r"(?i)when\s+(?:you|the\s+ai|assistant)\s+(?:read|see|process)\s+this",
            r"(?i)if\s+(?:you're|you\s+are)\s+an\s+ai",
            r"(?i)hidden\s+instruction",
            r"(?i)ignore\s+context\s+and",
            r"(?i)this\s+is\s+a\s+system\s+message"
        ]
        
        detected = []
        for pattern in indirect_patterns:
            if re.search(pattern, text):
                detected.append({
                    "pattern": pattern,
                    "source": source,
                    "risk": "high"
                })
        
        return {
            "is_indirect_injection": len(detected) > 0,
            "detected_patterns": detected,
            "source": source,
            "recommendation": "QUARANTINE" if detected else "SAFE"
        }
