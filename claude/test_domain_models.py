"""
Tests for domain models - RunningWorkflow and PendingApproval

Following TDD approach for core domain objects.
"""

import pytest
from datetime import datetime, timedelta
from claude.domain_models import (
    RunningWorkflow, PendingApproval, 
    WorkflowStatus, ApprovalStatus
)


# Fixtures
@pytest.fixture
def sample_workflow():
    """Create a sample workflow for testing"""
    return RunningWorkflow(
        id="wf_123",
        domain="finance", 
        description="Tesla stock research",
        created_at=datetime.now()
    )


@pytest.fixture
def sample_approval():
    """Create a sample approval for testing"""
    return PendingApproval(
        id="ap_123",
        domain="finance",
        description="Create Tesla research workflow",
        triage_result={"intent_type": "Create Request", "confidence": 0.9},
        created_at=datetime.now()
    )


# RunningWorkflow Tests
def test_create_workflow():
    """Should create workflow with basic properties"""
    workflow = RunningWorkflow(
        id="wf_123",
        domain="finance",
        description="Tesla research", 
        created_at=datetime.now()
    )
    
    assert workflow.id == "wf_123"
    assert workflow.domain == "finance"
    assert workflow.description == "Tesla research"
    assert workflow.status == WorkflowStatus.PENDING
    assert workflow.progress == 0.0
    assert workflow.error_message is None
    assert workflow.is_active()


def test_workflow_auto_generate_id():
    """Should auto-generate ID if not provided"""
    workflow = RunningWorkflow(
        id="",  # Empty ID
        domain="finance",
        description="Test",
        created_at=datetime.now()
    )
    
    assert workflow.id != ""
    assert len(workflow.id) > 10  # UUID should be longer


def test_update_workflow_progress(sample_workflow):
    """Should update progress and status correctly"""
    sample_workflow.update_progress(0.5, WorkflowStatus.RUNNING)
    
    assert sample_workflow.progress == 0.5
    assert sample_workflow.status == WorkflowStatus.RUNNING
    assert sample_workflow.last_update > sample_workflow.created_at


def test_workflow_progress_clamping(sample_workflow):
    """Should clamp progress between 0.0 and 1.0"""
    # Test upper bound
    sample_workflow.update_progress(1.5)
    assert sample_workflow.progress == 1.0
    
    # Test lower bound  
    sample_workflow.update_progress(-0.5)
    assert sample_workflow.progress == 0.0


def test_mark_workflow_completed(sample_workflow):
    """Should mark workflow as completed with full progress"""
    sample_workflow.mark_completed()
    
    assert sample_workflow.status == WorkflowStatus.COMPLETED
    assert sample_workflow.progress == 1.0
    assert not sample_workflow.is_active()


def test_mark_workflow_failed(sample_workflow):
    """Should mark workflow as failed with error message"""
    error_msg = "API timeout error"
    sample_workflow.mark_failed(error_msg)
    
    assert sample_workflow.status == WorkflowStatus.FAILED
    assert sample_workflow.error_message == error_msg
    assert not sample_workflow.is_active()


@pytest.mark.parametrize("status,expected_active", [
    (WorkflowStatus.PENDING, True),
    (WorkflowStatus.RUNNING, True), 
    (WorkflowStatus.PAUSED, True),
    (WorkflowStatus.COMPLETED, False),
    (WorkflowStatus.FAILED, False),
    (WorkflowStatus.CANCELLED, False),
])
def test_workflow_is_active(sample_workflow, status, expected_active):
    """Should correctly identify active workflows"""
    sample_workflow.status = status
    assert sample_workflow.is_active() == expected_active


def test_workflow_to_dict(sample_workflow):
    """Should convert workflow to dictionary"""
    workflow_dict = sample_workflow.to_dict()
    
    assert workflow_dict["id"] == sample_workflow.id
    assert workflow_dict["domain"] == sample_workflow.domain
    assert workflow_dict["description"] == sample_workflow.description
    assert workflow_dict["status"] == sample_workflow.status.value
    assert workflow_dict["progress"] == sample_workflow.progress
    assert isinstance(workflow_dict["created_at"], str)  # ISO format
    assert isinstance(workflow_dict["last_update"], str)  # ISO format


# PendingApproval Tests  
def test_create_approval():
    """Should create approval with basic properties"""
    approval = PendingApproval(
        id="ap_123",
        domain="finance",
        description="Create workflow",
        triage_result={"confidence": 0.8},
        created_at=datetime.now()
    )
    
    assert approval.id == "ap_123"
    assert approval.domain == "finance"
    assert approval.status == ApprovalStatus.PENDING
    assert approval.is_pending()
    assert not approval.is_expired()


def test_approval_auto_generate_id():
    """Should auto-generate ID if not provided"""
    approval = PendingApproval(
        id="",  # Empty ID
        domain="finance",
        description="Test",
        triage_result={},
        created_at=datetime.now()
    )
    
    assert approval.id != ""
    assert len(approval.id) > 10  # UUID should be longer


def test_approval_default_expiry():
    """Should set default expiry time"""
    approval = PendingApproval(
        id="ap_123",
        domain="finance", 
        description="Test",
        triage_result={},
        created_at=datetime.now()
    )
    
    # Should expire in ~10 minutes
    expected_expiry = datetime.now() + timedelta(minutes=10)
    time_diff = abs((approval.expires_at - expected_expiry).total_seconds())
    assert time_diff < 60  # Within 1 minute tolerance


def test_approval_approve(sample_approval):
    """Should mark approval as approved"""
    sample_approval.approve()
    assert sample_approval.status == ApprovalStatus.APPROVED
    assert not sample_approval.is_pending()


def test_approval_reject(sample_approval):
    """Should mark approval as rejected"""
    sample_approval.reject()
    assert sample_approval.status == ApprovalStatus.REJECTED
    assert not sample_approval.is_pending()


def test_approval_expire(sample_approval):
    """Should mark approval as expired"""
    sample_approval.expire()
    assert sample_approval.status == ApprovalStatus.EXPIRED
    assert not sample_approval.is_pending()


def test_approval_is_expired():
    """Should detect expired approvals"""
    # Create approval that expires in the past
    past_time = datetime.now() - timedelta(minutes=1)
    approval = PendingApproval(
        id="ap_123",
        domain="finance",
        description="Test",
        triage_result={},
        created_at=past_time,
        expires_at=past_time
    )
    
    assert approval.is_expired()
    assert not approval.is_pending()


def test_approval_to_dict(sample_approval):
    """Should convert approval to dictionary"""
    approval_dict = sample_approval.to_dict()
    
    assert approval_dict["id"] == sample_approval.id
    assert approval_dict["domain"] == sample_approval.domain
    assert approval_dict["description"] == sample_approval.description
    assert approval_dict["status"] == sample_approval.status.value
    assert isinstance(approval_dict["created_at"], str)  # ISO format
    assert isinstance(approval_dict["expires_at"], str)  # ISO format


@pytest.mark.parametrize("status,expired,expected_pending", [
    (ApprovalStatus.PENDING, False, True),
    (ApprovalStatus.PENDING, True, False),  # Expired
    (ApprovalStatus.APPROVED, False, False),
    (ApprovalStatus.REJECTED, False, False),
    (ApprovalStatus.EXPIRED, False, False),
])
def test_approval_is_pending(status, expired, expected_pending):
    """Should correctly identify pending approvals"""
    if expired:
        expires_at = datetime.now() - timedelta(minutes=1)  # Past
    else:
        expires_at = datetime.now() + timedelta(minutes=10)  # Future
    
    approval = PendingApproval(
        id="ap_123",
        domain="finance",
        description="Test",
        triage_result={},
        created_at=datetime.now(),
        expires_at=expires_at
    )
    approval.status = status
    
    assert approval.is_pending() == expected_pending