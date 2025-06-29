"""
Refactored Session Management for Domain-Based Concurrent Workflows

This module provides simplified session management that supports:
- Domain-keyed concurrent workflows
- Conversation history with sliding window
- Minimal session state (just connection management)
- Clean separation of concerns
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List, Set
from functools import wraps

from claude.domain_models import RunningWorkflow, PendingApproval
from claude.message_types import Message, ConversationManager


def updates_activity(method):
    """Decorator to automatically update activity timestamp after method execution"""
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        self.update_activity()
        return result
    return wrapper


@dataclass
class ChatSession:
    """
    Simplified session - only connection management and domain workflows
    No workflow state pollution - just basic session data
    """
    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    # Domain-keyed workflows and approvals - one per domain
    workflows: Dict[str, RunningWorkflow] = field(default_factory=dict)
    pending_approvals: Dict[str, PendingApproval] = field(default_factory=dict)
    
    # Conversation history with structured messages
    message_history: List[Message] = field(default_factory=list)
    
    # Conversation manager for sliding window and format conversion
    conversation_manager: ConversationManager = field(default_factory=lambda: ConversationManager(max_messages=50))
    
    @updates_activity
    def add_workflow(self, domain: str, workflow: RunningWorkflow) -> bool:
        """Add workflow to domain - returns False if one already exists"""
        if domain in self.workflows:
            existing = self.workflows[domain]
            print(f"Warning: Cannot add workflow for domain '{domain}'. "
                  f"A workflow (ID: {existing.id}) is already active.")
            return False
        self.workflows[domain] = workflow
        return True
    
    @updates_activity
    def get_workflow(self, domain: str) -> Optional[RunningWorkflow]:
        """Get workflow for domain"""
        return self.workflows.get(domain)
    
    def remove_workflow(self, domain: str) -> bool:
        """Remove workflow from domain completely"""
        if domain in self.workflows:
            del self.workflows[domain]
            return True
        return False
    
    @updates_activity
    def add_pending_approval(self, domain: str, approval: PendingApproval) -> bool:
        """Add pending approval for domain - returns False if one already exists"""
        if domain in self.pending_approvals:
            existing = self.pending_approvals[domain]
            if existing.is_pending():
                print(f"Warning: Cannot add approval for domain '{domain}'. "
                      f"An approval (ID: {existing.id}) is already pending.")
                return False
        self.pending_approvals[domain] = approval
        return True
    
    def has_pending_approval(self, domain: str) -> bool:
        """Check if domain has pending approval"""
        approval = self.pending_approvals.get(domain)
        if approval and approval.is_pending():
            return True
        
        # Clean up expired approvals
        if approval and not approval.is_pending():
            del self.pending_approvals[domain]
        
        return False
    
    @updates_activity
    def remove_pending_approval(self, domain: str) -> Optional[PendingApproval]:
        """Remove and return pending approval"""
        approval = self.pending_approvals.pop(domain, None)
        return approval
    
    def get_all_domains(self) -> Set[str]:
        """Get all domains with workflows or pending approvals"""
        domains = set(self.workflows.keys())
        domains.update(self.pending_approvals.keys())
        return domains
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()
    
    @updates_activity
    def add_message(self, message: Message):
        """Add structured message to history and update activity"""
        self.message_history.append(message)
        # Apply sliding window to keep memory usage under control
        self.message_history = self.conversation_manager.apply_sliding_window(self.message_history)
    
    @updates_activity
    def add_user_message(self, content: str):
        """Add user message to history"""
        message = Message.from_user(content)
        self.add_message(message)
    
    @updates_activity
    def add_ai_message(self, content: str, source: str = "ai"):
        """Add AI/model message to history"""
        message = Message.from_ai(content, source)
        self.add_message(message)
    
    @updates_activity
    def add_system_message(self, content: str, source: str = "system"):
        """Add system message to history"""
        message = Message.from_system(content, source)
        self.add_message(message)
    
    def get_conversation_history(self, include_system: bool = True) -> List[Message]:
        """Get conversation history, optionally excluding system messages"""
        if include_system:
            return self.message_history.copy()
        return [msg for msg in self.message_history if msg.role != "system"]
    
    def get_conversation_for_gemini(self, include_system: bool = True) -> List:
        """Get conversation in Gemini format"""
        messages = self.get_conversation_history(include_system)
        return self.conversation_manager.to_gemini_format(messages)
    
    def get_conversation_for_langchain(self, include_system: bool = True) -> List:
        """Get conversation in LangChain format"""
        messages = self.get_conversation_history(include_system)
        return self.conversation_manager.to_langchain_format(messages)
    
    def get_latest_user_message(self) -> Optional[Message]:
        """Get the most recent user message"""
        return self.conversation_manager.get_latest_user_message(self.message_history)
    
    def get_conversation_context(self, include_system: bool = True) -> str:
        """Get conversation as formatted string for context"""
        messages = self.get_conversation_history(include_system)
        return self.conversation_manager.get_conversation_context(messages, include_system)
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired due to inactivity"""
        return datetime.now() > self.last_activity + timedelta(minutes=timeout_minutes)
    
    def cleanup_expired_approvals(self) -> int:
        """Clean up expired approvals and return count removed"""
        expired_domains = []
        for domain, approval in self.pending_approvals.items():
            if not approval.is_pending():
                expired_domains.append(domain)
        
        for domain in expired_domains:
            del self.pending_approvals[domain]
        
        return len(expired_domains)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for monitoring/debugging"""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "message_count": len(self.message_history),
            "workflow_domains": list(self.workflows.keys()),
            "pending_approval_domains": list(self.pending_approvals.keys()),
            "total_domains": len(self.get_all_domains())
        }


class SessionManager:
    """
    Simplified session manager for domain-based concurrent workflows
    Handles session lifecycle and cleanup, but not workflow orchestration
    """
    
    def __init__(self, session_timeout_minutes: int = 30, start_cleanup: bool = True):
        self.sessions: Dict[str, ChatSession] = {}
        self.session_timeout = session_timeout_minutes
        self._cleanup_task: Optional[asyncio.Task] = None
        if start_cleanup:
            self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start background cleanup task"""
        try:
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        except RuntimeError:
            # No event loop running (likely during tests)
            pass
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of expired sessions and approvals"""
        while True:
            try:
                await asyncio.sleep(60)  # Cleanup every minute
                self.cleanup_expired()
            except Exception as e:
                print(f"Error in session cleanup: {e}")
    
    def create_session(self, session_id: str) -> ChatSession:
        """Create new session or return existing"""
        if session_id not in self.sessions:
            self.sessions[session_id] = ChatSession(session_id=session_id)
            print(f"Created new session: {session_id}")
        else:
            # Update activity for existing session
            self.sessions[session_id].update_activity()
        
        return self.sessions[session_id]
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get existing session"""
        session = self.sessions.get(session_id)
        if session:
            session.update_activity()
        return session
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session and cleanup resources"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            
            # Cancel workflow tasks if running
            for workflow in session.workflows.values():
                if workflow.task and not workflow.task.done():
                    workflow.task.cancel()
            
            del self.sessions[session_id]
            print(f"Deleted session: {session_id}")
            return True
        return False
    
    def cleanup_expired(self) -> Dict[str, int]:
        """Clean up expired sessions and approvals"""
        stats = {"expired_sessions": 0, "expired_approvals": 0}
        
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            # Clean up expired approvals within each session
            expired_count = session.cleanup_expired_approvals()
            stats["expired_approvals"] += expired_count
            
            # Check for expired sessions
            if session.is_expired(self.session_timeout):
                expired_sessions.append(session_id)
        
        # Delete expired sessions
        for session_id in expired_sessions:
            self.delete_session(session_id)
            stats["expired_sessions"] += 1
        
        return stats
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get overall session statistics"""
        total_sessions = len(self.sessions)
        total_workflows = sum(len(s.workflows) for s in self.sessions.values())
        total_pending_approvals = sum(len(s.pending_approvals) for s in self.sessions.values())
        
        # Domain statistics
        all_domains = set()
        for session in self.sessions.values():
            all_domains.update(session.get_all_domains())
        
        return {
            "total_sessions": total_sessions,
            "total_active_workflows": total_workflows,
            "total_pending_approvals": total_pending_approvals,
            "unique_domains": list(all_domains),
            "domain_count": len(all_domains),
            "session_ids": list(self.sessions.keys())
        }
    
    def get_session_details(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed session information for debugging"""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        details = session.to_dict()
        
        # Add workflow details
        details["workflows"] = {
            domain: workflow.to_dict() 
            for domain, workflow in session.workflows.items()
        }
        
        # Add approval details
        details["approvals"] = {
            domain: approval.to_dict() 
            for domain, approval in session.pending_approvals.items()
        }
        
        return details
    
    async def shutdown(self):
        """Clean shutdown - cancel all tasks"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        
        # Cancel all workflow tasks
        for session in self.sessions.values():
            for workflow in session.workflows.values():
                if workflow.task and not workflow.task.done():
                    workflow.task.cancel()
        
        print("SessionManager shutdown complete")


# Global session manager instance - don't start cleanup during import
session_manager = SessionManager(start_cleanup=False)


# Convenience functions for backward compatibility
def create_session(session_id: str) -> ChatSession:
    return session_manager.create_session(session_id)


def get_session(session_id: str) -> Optional[ChatSession]:
    return session_manager.get_session(session_id)


# Export for external use
__all__ = [
    'ChatSession', 'SessionManager',
    'session_manager', 'create_session', 'get_session'
]