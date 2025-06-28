"""
Domain Models for Multi-Agent Workflow System

Core data structures for workflows, approvals, and workflow state management.
These are shared between session management, orchestration, and testing.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional


class WorkflowStatus(Enum):
    """Workflow execution status"""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(Enum):
    """Approval request states"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class RunningWorkflow:
    """
    Represents an active workflow in a specific domain
    Contains the workflow state and execution context
    """

    id: str
    domain: str
    description: str
    created_at: datetime

    # Private field to store the actual status
    _status: WorkflowStatus = field(default=WorkflowStatus.PENDING, init=False)

    # Workflow execution context
    triage_result: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    progress: float = 0.0  # 0.0 to 1.0

    # Execution details
    last_update: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None

    # Optional task reference for async execution
    task: Optional[Any] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        # Set initial status without triggering update
        self._status = WorkflowStatus.PENDING

    @property
    def status(self) -> WorkflowStatus:
        """Get the current workflow status"""
        return self._status

    @status.setter
    def status(self, value: WorkflowStatus):
        """Set workflow status and automatically update timestamp"""
        self._status = value
        self._update_timestamp()

    def _update_timestamp(self):
        """Private method to update the last_update timestamp"""
        self.last_update = datetime.now()

    def update_progress(self, progress: float, status: Optional[WorkflowStatus] = None):
        """Update workflow progress and status"""
        self.progress = max(0.0, min(1.0, progress))  # Clamp to 0-1
        if status:
            self.status = status  # This will auto-update timestamp via setter
        else:
            self._update_timestamp()  # Update timestamp for progress change

    def mark_completed(self):
        """Mark workflow as completed"""
        self.status = WorkflowStatus.COMPLETED  # Auto-updates timestamp
        self.progress = 1.0

    def mark_failed(self, error_message: str):
        """Mark workflow as failed with error message"""
        self.status = WorkflowStatus.FAILED  # Auto-updates timestamp
        self.error_message = error_message

    def is_active(self) -> bool:
        """Check if workflow is actively running"""
        return self.status in [WorkflowStatus.PENDING, WorkflowStatus.RUNNING, WorkflowStatus.PAUSED]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "domain": self.domain,
            "description": self.description,
            "status": self.status.value,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "last_update": self.last_update.isoformat(),
            "error_message": self.error_message,
            "context": self.context,
        }


@dataclass
class PendingApproval:
    """
    Represents a pending approval request for workflow creation/modification
    """

    id: str
    domain: str
    description: str
    triage_result: Dict[str, Any]
    created_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=10))

    # Original request context
    original_message: str = ""
    action_type: str = ""  # "create", "update", "delete"
    confidence_score: float = 0.0

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def is_expired(self) -> bool:
        """Check if approval request has expired"""
        return datetime.now() > self.expires_at

    def approve(self):
        """Mark approval as approved"""
        self.status = ApprovalStatus.APPROVED

    def reject(self):
        """Mark approval as rejected"""
        self.status = ApprovalStatus.REJECTED

    def expire(self):
        """Mark approval as expired"""
        self.status = ApprovalStatus.EXPIRED

    def is_pending(self) -> bool:
        """Check if approval is still pending and not expired"""
        return self.status == ApprovalStatus.PENDING and not self.is_expired()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "domain": self.domain,
            "description": self.description,
            "action_type": self.action_type,
            "original_message": self.original_message,
            "confidence_score": self.confidence_score,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }


# Export main classes
__all__ = ["WorkflowStatus", "ApprovalStatus", "RunningWorkflow", "PendingApproval"]
