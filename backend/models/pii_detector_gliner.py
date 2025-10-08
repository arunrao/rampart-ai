"""
GLiNER-based PII Detection
High-accuracy, zero-shot PII detection using Generalist NER models
"""
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from functools import lru_cache
import re
import logging

logger = logging.getLogger(__name__)

# Try to import GLiNER
try:
    from gliner import GLiNER
    GLINER_AVAILABLE = True
except ImportError:
    GLINER_AVAILABLE = False
    logger.warning("GLiNER not available. Install with: pip install gliner")


@dataclass
class PIIEntity:
    """PII entity detected by GLiNER"""
    type: str  # email, phone, ssn, credit_card, etc.
    value: str
    start: int
    end: int
    confidence: float
    label: Optional[str] = None  # Original GLiNER label


class GLiNERPIIDetector:
    """
    Production-ready PII detector using GLiNER models
    
    Features:
    - Zero-shot entity detection (no retraining needed)
    - Context-aware (understands semantic meaning)
    - Custom entity types at runtime
    - Fallback to regex if model unavailable
    - Multiple model options (fast/balanced/accurate)
    """
    
    # Model options
    MODELS = {
        "edge": "knowledgator/gliner-pii-edge-v1.0",      # Fastest, ~5ms
        "balanced": "gravitee-io/gliner-pii-detection",    # Balanced, ~10ms (DEFAULT)
        "accurate": "gretelai/gretel-gliner-bi-large-v1.0" # Most accurate, ~15ms
    }
    
    # Default PII entity labels for GLiNER
    DEFAULT_LABELS = [
        "email address",
        "email",
        "phone number",
        "phone",
        "social security number",
        "ssn",
        "credit card number",
        "credit card",
        "ip address",
        "person name",
        "person",
        "full name",
        "address",
        "street address",
        "date of birth",
        "dob",
        "passport number",
        "driver license",
        "bank account",
        "routing number",
        "medical record number",
        "health insurance number",
    ]
    
    def __init__(
        self,
        model_type: str = "balanced",
        confidence_threshold: float = 0.7,
        use_onnx: bool = True,
        custom_labels: Optional[List[str]] = None
    ):
        """
        Initialize GLiNER PII Detector
        
        Args:
            model_type: "edge", "balanced", or "accurate"
            confidence_threshold: Minimum confidence score (0.0-1.0)
            use_onnx: Use ONNX for faster inference
            custom_labels: Additional entity labels to detect
        """
        self.model_type = model_type
        self.confidence_threshold = confidence_threshold
        self.use_onnx = use_onnx
        
        # Combine default and custom labels
        self.labels = self.DEFAULT_LABELS.copy()
        if custom_labels:
            self.labels.extend(custom_labels)
        
        # Model loaded lazily on first use
        self._model = None
        self._model_loaded = False
    
    @property
    def model(self):
        """Lazy load model on first use"""
        if not self._model_loaded:
            self._model = self._load_model()
            self._model_loaded = True
        return self._model
    
    def _load_model(self):
        """Load GLiNER model with error handling"""
        if not GLINER_AVAILABLE:
            logger.error("GLiNER library not installed")
            return None
        
        model_name = self.MODELS.get(self.model_type, self.MODELS["balanced"])
        
        try:
            logger.info(f"Loading GLiNER model: {model_name}")
            
            if self.use_onnx:
                # Try to load ONNX version for faster inference
                try:
                    model = GLiNER.from_pretrained(
                        model_name,
                        load_onnx_model=True,
                        load_tokenizer=True,
                        onnx_model_file="model.onnx"
                    )
                    logger.info(f"Loaded ONNX model: {model_name}")
                    return model
                except Exception as onnx_error:
                    logger.warning(f"ONNX load failed: {onnx_error}, trying PyTorch")
            
            # Fallback to PyTorch
            model = GLiNER.from_pretrained(model_name)
            logger.info(f"Loaded PyTorch model: {model_name}")
            return model
            
        except Exception as e:
            logger.error(f"Failed to load GLiNER model: {e}")
            return None
    
    def detect(
        self,
        text: str,
        labels: Optional[List[str]] = None,
        threshold: Optional[float] = None
    ) -> List[PIIEntity]:
        """
        Detect PII entities in text
        
        Args:
            text: Input text to analyze
            labels: Custom entity labels (uses defaults if None)
            threshold: Custom confidence threshold (uses default if None)
        
        Returns:
            List of detected PII entities
        """
        if not self.model:
            logger.warning("GLiNER model not available, falling back to regex")
            return self._regex_fallback(text)
        
        # Use provided labels or defaults
        entity_labels = labels or self.labels
        conf_threshold = threshold or self.confidence_threshold
        
        try:
            # Run GLiNER prediction
            predictions = self.model.predict_entities(
                text,
                entity_labels,
                threshold=conf_threshold
            )
            
            # Convert to PIIEntity format
            entities = []
            for pred in predictions:
                entity = PIIEntity(
                    type=self._map_label_to_type(pred["label"]),
                    value=pred["text"],
                    start=pred["start"],
                    end=pred["end"],
                    confidence=float(pred["score"]),
                    label=pred["label"]
                )
                entities.append(entity)
            
            logger.debug(f"GLiNER detected {len(entities)} PII entities")
            return entities
            
        except Exception as e:
            logger.error(f"GLiNER prediction failed: {e}, falling back to regex")
            return self._regex_fallback(text)
    
    def _map_label_to_type(self, label: str) -> str:
        """Map GLiNER label to standardized PII type"""
        label_lower = label.lower().replace(" ", "_")
        
        # Email
        if "email" in label_lower:
            return "email"
        
        # Phone
        if "phone" in label_lower or "mobile" in label_lower:
            return "phone"
        
        # SSN
        if "ssn" in label_lower or "social_security" in label_lower:
            return "ssn"
        
        # Credit Card
        if "credit" in label_lower or "card" in label_lower:
            return "credit_card"
        
        # IP Address
        if "ip" in label_lower:
            return "ip_address"
        
        # Name
        if "name" in label_lower or "person" in label_lower:
            return "name"
        
        # Address
        if "address" in label_lower and "email" not in label_lower and "ip" not in label_lower:
            return "address"
        
        # Date of birth
        if "dob" in label_lower or "birth" in label_lower:
            return "date_of_birth"
        
        # Passport
        if "passport" in label_lower:
            return "passport_number"
        
        # Driver License
        if "driver" in label_lower or "license" in label_lower:
            return "driver_license"
        
        # Bank Account
        if "bank" in label_lower or "account" in label_lower:
            return "bank_account"
        
        # Medical
        if "medical" in label_lower or "health" in label_lower:
            return "medical_record"
        
        # Default to generic
        return "name"
    
    def _regex_fallback(self, text: str) -> List[PIIEntity]:
        """
        Fallback to regex-based detection if GLiNER unavailable
        Basic patterns for common PII types
        """
        entities = []
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        for match in re.finditer(email_pattern, text):
            entities.append(PIIEntity(
                type="email",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.95,
                label="email_regex"
            ))
        
        # Phone pattern (US format)
        phone_pattern = r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b'
        for match in re.finditer(phone_pattern, text):
            entities.append(PIIEntity(
                type="phone",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.90,
                label="phone_regex"
            ))
        
        # SSN pattern
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        for match in re.finditer(ssn_pattern, text):
            entities.append(PIIEntity(
                type="ssn",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.98,
                label="ssn_regex"
            ))
        
        # Credit card pattern
        cc_pattern = r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
        for match in re.finditer(cc_pattern, text):
            entities.append(PIIEntity(
                type="credit_card",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.85,
                label="credit_card_regex"
            ))
        
        # IP Address pattern
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        for match in re.finditer(ip_pattern, text):
            entities.append(PIIEntity(
                type="ip_address",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.80,
                label="ip_regex"
            ))
        
        return entities
    
    def redact(
        self,
        text: str,
        entities: Optional[List[PIIEntity]] = None,
        redaction_text: str = "[REDACTED]",
        redact_types: Optional[List[str]] = None
    ) -> Tuple[str, List[PIIEntity]]:
        """
        Redact PII from text
        
        Args:
            text: Original text
            entities: Pre-detected entities (will detect if None)
            redaction_text: Replacement text
            redact_types: Only redact specific types (None = all)
        
        Returns:
            (redacted_text, entities_used)
        """
        # Detect if not provided
        if entities is None:
            entities = self.detect(text)
        
        # Filter by type if specified
        if redact_types:
            entities = [e for e in entities if e.type in redact_types]
        
        # Sort by start position (reverse) to maintain indices
        entities_sorted = sorted(entities, key=lambda e: e.start, reverse=True)
        
        # Redact each entity
        redacted = text
        for entity in entities_sorted:
            redacted = (
                redacted[:entity.start] +
                redaction_text +
                redacted[entity.end:]
            )
        
        return redacted, entities
    
    def batch_detect(
        self,
        texts: List[str],
        labels: Optional[List[str]] = None,
        threshold: Optional[float] = None
    ) -> List[List[PIIEntity]]:
        """
        Detect PII in multiple texts (more efficient than sequential)
        
        Args:
            texts: List of input texts
            labels: Custom entity labels
            threshold: Custom confidence threshold
        
        Returns:
            List of entity lists (one per input text)
        """
        # For now, process sequentially
        # TODO: Implement true batch processing for better performance
        return [self.detect(text, labels, threshold) for text in texts]


# Global singleton instance (lazy loaded)
_detector_instance: Optional[GLiNERPIIDetector] = None


def get_gliner_detector(
    model_type: str = "balanced",
    confidence_threshold: float = 0.7,
    use_onnx: bool = True
) -> GLiNERPIIDetector:
    """
    Get or create global GLiNER detector instance
    
    Args:
        model_type: "edge", "balanced", or "accurate"
        confidence_threshold: Minimum confidence score
        use_onnx: Use ONNX for faster inference
    
    Returns:
        GLiNERPIIDetector instance
    """
    global _detector_instance
    
    if _detector_instance is None:
        _detector_instance = GLiNERPIIDetector(
            model_type=model_type,
            confidence_threshold=confidence_threshold,
            use_onnx=use_onnx
        )
    
    return _detector_instance


# Convenience functions
def detect_pii_gliner(
    text: str,
    model_type: str = "balanced",
    custom_labels: Optional[List[str]] = None,
    threshold: float = 0.7
) -> List[PIIEntity]:
    """
    Detect PII using GLiNER (convenience function)
    
    Args:
        text: Input text
        model_type: Model variant to use
        custom_labels: Additional entity types to detect
        threshold: Confidence threshold
    
    Returns:
        List of detected PII entities
    """
    detector = get_gliner_detector(model_type=model_type, confidence_threshold=threshold)
    
    # Add custom labels if provided
    labels = detector.labels.copy()
    if custom_labels:
        labels.extend(custom_labels)
    
    return detector.detect(text, labels=labels)


def redact_pii_gliner(
    text: str,
    model_type: str = "balanced",
    redaction_text: str = "[REDACTED]",
    redact_types: Optional[List[str]] = None,
    threshold: float = 0.7
) -> Tuple[str, List[PIIEntity]]:
    """
    Detect and redact PII (convenience function)
    
    Args:
        text: Input text
        model_type: Model variant to use
        redaction_text: Replacement text
        redact_types: Only redact specific types
        threshold: Confidence threshold
    
    Returns:
        (redacted_text, detected_entities)
    """
    detector = get_gliner_detector(model_type=model_type, confidence_threshold=threshold)
    return detector.redact(text, redaction_text=redaction_text, redact_types=redact_types)
