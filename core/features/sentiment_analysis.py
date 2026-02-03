"""
Sentiment Analysis
Personalized responses based on user sentiment.
"""

from typing import Dict, Any, Optional, List
from enum import Enum


class Sentiment(Enum):
    """Sentiment types."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    CONFUSED = "confused"


class SentimentAnalyzer:
    """Analyzes sentiment from user messages."""
    
    def __init__(self):
        # Keyword-based sentiment detection (can be enhanced with ML model)
        self.positive_keywords = [
            "great", "excellent", "amazing", "love", "perfect", "wonderful",
            "fantastic", "awesome", "good", "yes", "sure", "interested",
            "excited", "happy", "pleased", "satisfied"
        ]
        
        self.negative_keywords = [
            "bad", "terrible", "awful", "hate", "worst", "disappointed",
            "frustrated", "angry", "upset", "no", "not", "don't", "won't",
            "can't", "unhappy", "dissatisfied"
        ]
        
        self.frustrated_keywords = [
            "frustrated", "annoyed", "irritated", "fed up", "tired of",
            "sick of", "enough", "stop", "quit"
        ]
        
        self.excited_keywords = [
            "excited", "thrilled", "can't wait", "looking forward",
            "eager", "enthusiastic", "pumped", "ready"
        ]
        
        self.confused_keywords = [
            "confused", "don't understand", "unclear", "not sure",
            "what do you mean", "explain", "help me understand"
        ]
    
    def analyze(self, message: str, conversation_history: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        Analyze sentiment from message and conversation history.
        
        Args:
            message: User message text
            conversation_history: Optional conversation history
        
        Returns:
            Dictionary with sentiment analysis results
        """
        if not message:
            return {
                "sentiment": Sentiment.NEUTRAL.value,
                "confidence": 0.5,
                "score": 0.0
            }
        
        message_lower = message.lower()
        
        # Count keyword matches
        positive_score = sum(1 for kw in self.positive_keywords if kw in message_lower)
        negative_score = sum(1 for kw in self.negative_keywords if kw in message_lower)
        frustrated_score = sum(1 for kw in self.frustrated_keywords if kw in message_lower)
        excited_score = sum(1 for kw in self.excited_keywords if kw in message_lower)
        confused_score = sum(1 for kw in self.confused_keywords if kw in message_lower)
        
        # Determine sentiment
        sentiment = Sentiment.NEUTRAL
        confidence = 0.5
        score = 0.0
        
        if frustrated_score > 0:
            sentiment = Sentiment.FRUSTRATED
            confidence = min(0.9, 0.5 + frustrated_score * 0.1)
            score = -0.8
        elif excited_score > 0:
            sentiment = Sentiment.EXCITED
            confidence = min(0.9, 0.5 + excited_score * 0.1)
            score = 0.8
        elif confused_score > 0:
            sentiment = Sentiment.CONFUSED
            confidence = min(0.9, 0.5 + confused_score * 0.1)
            score = 0.0
        elif positive_score > negative_score:
            sentiment = Sentiment.POSITIVE
            confidence = min(0.9, 0.5 + (positive_score - negative_score) * 0.1)
            score = 0.5 + (positive_score - negative_score) * 0.1
        elif negative_score > positive_score:
            sentiment = Sentiment.NEGATIVE
            confidence = min(0.9, 0.5 + (negative_score - positive_score) * 0.1)
            score = -0.5 - (negative_score - positive_score) * 0.1
        else:
            sentiment = Sentiment.NEUTRAL
            confidence = 0.5
            score = 0.0
        
        # Consider conversation history for context
        if conversation_history:
            recent_sentiment = self._analyze_history_sentiment(conversation_history)
            if recent_sentiment:
                # Weight current message 70%, history 30%
                if recent_sentiment["sentiment"] == sentiment.value:
                    confidence = min(0.95, confidence + 0.1)
                else:
                    # If history differs, reduce confidence slightly
                    confidence = max(0.3, confidence - 0.1)
        
        return {
            "sentiment": sentiment.value,
            "confidence": min(1.0, max(0.0, confidence)),
            "score": max(-1.0, min(1.0, score)),
            "positive_score": positive_score,
            "negative_score": negative_score
        }
    
    def _analyze_history_sentiment(self, conversation_history: List[Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze sentiment from recent conversation history.
        
        Args:
            conversation_history: List of conversation messages
        
        Returns:
            Sentiment analysis result or None
        """
        if not conversation_history:
            return None
        
        # Analyze last 3 user messages
        recent_messages = []
        for msg in reversed(conversation_history[-6:]):  # Last 6 messages (3 user + 3 assistant)
            text = ""
            if hasattr(msg, 'role') and hasattr(msg, 'parts'):
                # SDK object
                if msg.role == "user" and msg.parts:
                    text = getattr(msg.parts[0], 'text', '')
            elif isinstance(msg, dict):
                # Dictionary format
                if msg.get("role") == "user":
                    parts = msg.get("parts", [])
                    if parts and isinstance(parts[0], dict):
                        text = parts[0].get("text", "")
            
            if text:
                recent_messages.append(text)
                if len(recent_messages) >= 3:
                    break
        
        if not recent_messages:
            return None
        
        # Analyze combined recent messages
        combined_text = " ".join(recent_messages)
        return self.analyze(combined_text)
    
    def get_sentiment_aware_response_guidance(self, sentiment_result: Dict[str, Any]) -> str:
        """
        Get guidance for generating sentiment-aware responses.
        
        Args:
            sentiment_result: Result from analyze() method
        
        Returns:
            Guidance string for response generation
        """
        sentiment = sentiment_result.get("sentiment", "neutral")
        score = sentiment_result.get("score", 0.0)
        
        guidance_map = {
            Sentiment.POSITIVE.value: "User is positive and engaged. Be enthusiastic and helpful. Offer next steps or additional value.",
            Sentiment.NEGATIVE.value: "User is negative. Be empathetic, acknowledge concerns, and focus on problem-solving. Avoid being pushy.",
            Sentiment.FRUSTRATED.value: "User is frustrated. Be patient, understanding, and focus on resolving their issue quickly. Apologize if appropriate.",
            Sentiment.EXCITED.value: "User is excited. Match their energy and provide clear next steps. Capitalize on their enthusiasm.",
            Sentiment.CONFUSED.value: "User is confused. Provide clear, simple explanations. Break down complex information. Ask clarifying questions.",
            Sentiment.NEUTRAL.value: "User sentiment is neutral. Maintain professional, helpful tone. Provide information and guide conversation."
        }
        
        return guidance_map.get(sentiment, guidance_map[Sentiment.NEUTRAL.value])


# Global instance
sentiment_analyzer = SentimentAnalyzer()
