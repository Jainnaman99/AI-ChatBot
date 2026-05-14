from typing import Dict, List
from datetime import datetime, timedelta
import uuid

class ConversationManager:
    """
    Manages conversation history for multiple sessions.
    Stores conversations in memory with automatic cleanup of old sessions.
    """

    def __init__(self, max_history_per_session: int = 10, session_timeout_minutes: int = 60):
        self.conversations: Dict[str, List[Dict]] = {}
        self.session_timestamps: Dict[str, datetime] = {}
        self.max_history_per_session = max_history_per_session
        self.session_timeout = timedelta(minutes=session_timeout_minutes)

    def generate_session_id(self) -> str:
        """Generate a new unique session ID"""
        return str(uuid.uuid4())

    def add_message(self, session_id: str, role: str, content: str):
        """
        Add a message to the conversation history

        Args:
            session_id: Unique session identifier
            role: Either 'user' or 'assistant'
            content: Message content
        """
        # Initialize session if it doesn't exist
        if session_id not in self.conversations:
            self.conversations[session_id] = []

        # Add the message
        self.conversations[session_id].append({
            "role": role,
            "content": content
        })

        # Update timestamp
        self.session_timestamps[session_id] = datetime.now()

        # Keep only the last N messages to prevent memory overflow
        if len(self.conversations[session_id]) > self.max_history_per_session * 2:
            self.conversations[session_id] = self.conversations[session_id][-(self.max_history_per_session * 2):]

    def get_history(self, session_id: str) -> List[Dict]:
        """
        Retrieve conversation history for a session

        Args:
            session_id: Unique session identifier

        Returns:
            List of message dictionaries with 'role' and 'content'
        """
        self._cleanup_expired_sessions()

        return self.conversations.get(session_id, [])

    def clear_session(self, session_id: str):
        """Clear conversation history for a specific session"""
        if session_id in self.conversations:
            del self.conversations[session_id]
        if session_id in self.session_timestamps:
            del self.session_timestamps[session_id]

    def clear_all_sessions(self):
        """Clear all conversation histories"""
        self.conversations.clear()
        self.session_timestamps.clear()

    def _cleanup_expired_sessions(self):
        """Remove sessions that have been inactive for too long"""
        current_time = datetime.now()
        expired_sessions = [
            session_id for session_id, timestamp in self.session_timestamps.items()
            if current_time - timestamp > self.session_timeout
        ]

        for session_id in expired_sessions:
            self.clear_session(session_id)

    def get_active_session_count(self) -> int:
        """Get the number of active sessions"""
        self._cleanup_expired_sessions()
        return len(self.conversations)


# Global instance
conversation_manager = ConversationManager()
