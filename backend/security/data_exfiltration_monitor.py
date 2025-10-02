"""
Data Exfiltration Detection and Monitoring
Detects attempts to leak sensitive data through LLM outputs
"""
import re
from typing import Dict, List, Set
from dataclasses import dataclass
from enum import Enum


class ExfiltrationMethod(Enum):
    """Methods of data exfiltration"""
    URL_EMBEDDING = "url_embedding"
    EMAIL_COMMAND = "email_command"
    API_CALL = "api_call"
    ENCODING = "encoding"
    STEGANOGRAPHY = "steganography"
    SIDE_CHANNEL = "side_channel"


@dataclass
class SensitiveDataPattern:
    """Pattern for sensitive data"""
    name: str
    pattern: str
    severity: float
    category: str


class DataExfiltrationMonitor:
    """
    Monitors LLM outputs for data exfiltration attempts
    Based on Microsoft AI Red Team research
    """
    
    def __init__(self):
        self.sensitive_patterns = self._load_sensitive_patterns()
        self.exfiltration_indicators = self._load_exfiltration_indicators()
        self.trusted_domains = {"example.com", "trusted.org"}
    
    def _load_sensitive_patterns(self) -> List[SensitiveDataPattern]:
        """Load patterns for sensitive data"""
        return [
            SensitiveDataPattern(
                name="api_key",
                pattern=r"(?i)(api[_-]?key|apikey|api[_-]?secret)[\s:=]+['\"]?([a-zA-Z0-9_\-]{20,})['\"]?",
                severity=0.95,
                category="credentials"
            ),
            SensitiveDataPattern(
                name="password",
                pattern=r"(?i)(password|passwd|pwd)[\s:=]+['\"]?([^\s'\"]{8,})['\"]?",
                severity=0.9,
                category="credentials"
            ),
            SensitiveDataPattern(
                name="jwt_token",
                pattern=r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
                severity=0.95,
                category="credentials"
            ),
            SensitiveDataPattern(
                name="aws_key",
                pattern=r"AKIA[0-9A-Z]{16}",
                severity=1.0,
                category="credentials"
            ),
            SensitiveDataPattern(
                name="private_key",
                pattern=r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
                severity=1.0,
                category="credentials"
            ),
            SensitiveDataPattern(
                name="database_connection",
                pattern=r"(?i)(mongodb|mysql|postgresql|redis)://[^\s]+",
                severity=0.9,
                category="infrastructure"
            ),
            SensitiveDataPattern(
                name="internal_ip",
                pattern=r"\b(?:10\.|172\.(?:1[6-9]|2[0-9]|3[01])\.|192\.168\.)\d{1,3}\.\d{1,3}\b",
                severity=0.7,
                category="infrastructure"
            )
        ]
    
    def _load_exfiltration_indicators(self) -> List[Dict]:
        """Load indicators of exfiltration attempts"""
        return [
            {
                "name": "url_with_data",
                "pattern": r"https?://[^\s]+\?[^\s]*(?:data|token|key|secret|password)=[^\s&]+",
                "severity": 0.9,
                "method": ExfiltrationMethod.URL_EMBEDDING
            },
            {
                "name": "email_instruction",
                "pattern": r"(?i)(send|email|forward|mail)\s+(?:this|it|the\s+\w+)\s+to\s+[\w\.-]+@[\w\.-]+",
                "severity": 0.95,
                "method": ExfiltrationMethod.EMAIL_COMMAND
            },
            {
                "name": "webhook_call",
                "pattern": r"(?i)(webhook|callback|notify)\s+(?:url|endpoint)[\s:]+https?://",
                "severity": 0.85,
                "method": ExfiltrationMethod.API_CALL
            },
            {
                "name": "base64_encoded_url",
                "pattern": r"(?i)base64.*https?://",
                "severity": 0.8,
                "method": ExfiltrationMethod.ENCODING
            },
            {
                "name": "curl_command",
                "pattern": r"curl\s+(?:-X\s+POST\s+)?https?://[^\s]+",
                "severity": 0.9,
                "method": ExfiltrationMethod.API_CALL
            },
            {
                "name": "fetch_post",
                "pattern": r"fetch\(['\"]https?://[^'\"]+['\"],\s*\{[^}]*method:\s*['\"]POST['\"]",
                "severity": 0.9,
                "method": ExfiltrationMethod.API_CALL
            }
        ]
    
    def scan_output(self, output: str, context: Dict = None) -> Dict:
        """
        Scan LLM output for data exfiltration attempts
        
        Args:
            output: The LLM output to scan
            context: Additional context (user_id, session_id, etc.)
        
        Returns:
            Detection results
        """
        results = {
            "has_exfiltration_risk": False,
            "risk_score": 0.0,
            "sensitive_data_found": [],
            "exfiltration_indicators": [],
            "urls_found": [],
            "recommendation": "ALLOW"
        }
        
        # Check for sensitive data
        for pattern in self.sensitive_patterns:
            matches = re.finditer(pattern.pattern, output)
            for match in matches:
                results["sensitive_data_found"].append({
                    "type": pattern.name,
                    "category": pattern.category,
                    "severity": pattern.severity,
                    "matched_text": match.group()[:50] + "..." if len(match.group()) > 50 else match.group(),
                    "position": match.span()
                })
        
        # Check for exfiltration indicators
        for indicator in self.exfiltration_indicators:
            matches = re.finditer(indicator["pattern"], output)
            for match in matches:
                results["exfiltration_indicators"].append({
                    "name": indicator["name"],
                    "method": indicator["method"].value,
                    "severity": indicator["severity"],
                    "matched_text": match.group()[:100],
                    "position": match.span()
                })
        
        # Extract and analyze URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, output)
        for url in urls:
            url_analysis = self._analyze_url(url)
            results["urls_found"].append(url_analysis)
        
        # Calculate risk score
        risk_score = 0.0
        
        if results["sensitive_data_found"]:
            max_sensitive_severity = max(item["severity"] for item in results["sensitive_data_found"])
            risk_score = max(risk_score, max_sensitive_severity)
        
        if results["exfiltration_indicators"]:
            max_exfil_severity = max(item["severity"] for item in results["exfiltration_indicators"])
            risk_score = max(risk_score, max_exfil_severity)
        
        # Increase risk if both sensitive data AND exfiltration method present
        if results["sensitive_data_found"] and results["exfiltration_indicators"]:
            risk_score = min(risk_score * 1.3, 1.0)
        
        # Check for untrusted URLs with parameters
        untrusted_urls_with_params = [
            url for url in results["urls_found"]
            if not url["is_trusted"] and url["has_parameters"]
        ]
        if untrusted_urls_with_params:
            risk_score = max(risk_score, 0.75)
        
        results["risk_score"] = risk_score
        results["has_exfiltration_risk"] = risk_score >= 0.6
        
        # Recommendation
        if risk_score >= 0.9:
            results["recommendation"] = "BLOCK"
        elif risk_score >= 0.7:
            results["recommendation"] = "REDACT"
        elif risk_score >= 0.5:
            results["recommendation"] = "FLAG"
        else:
            results["recommendation"] = "ALLOW"
        
        return results
    
    def _analyze_url(self, url: str) -> Dict:
        """Analyze a URL for exfiltration risk"""
        from urllib.parse import urlparse, parse_qs
        
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        is_trusted = any(domain in parsed.netloc for domain in self.trusted_domains)
        has_parameters = len(params) > 0
        
        # Check for suspicious parameter names
        suspicious_params = {"data", "token", "key", "secret", "password", "auth", "credential"}
        has_suspicious_params = any(
            param.lower() in suspicious_params 
            for param in params.keys()
        )
        
        return {
            "url": url,
            "domain": parsed.netloc,
            "is_trusted": is_trusted,
            "has_parameters": has_parameters,
            "has_suspicious_params": has_suspicious_params,
            "risk_level": "high" if (not is_trusted and has_suspicious_params) else "low"
        }
    
    def redact_sensitive_data(self, text: str) -> str:
        """Redact sensitive data from text"""
        redacted = text
        
        for pattern in self.sensitive_patterns:
            redacted = re.sub(
                pattern.pattern,
                f"[{pattern.name.upper()}_REDACTED]",
                redacted
            )
        
        return redacted
    
    def add_trusted_domain(self, domain: str):
        """Add a domain to the trusted list"""
        self.trusted_domains.add(domain)
    
    def remove_trusted_domain(self, domain: str):
        """Remove a domain from the trusted list"""
        self.trusted_domains.discard(domain)
