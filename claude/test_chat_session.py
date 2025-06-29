"""
Tests for refactored ChatSession following TDD approach

These tests define the expected behavior for the simplified,
domain-based ChatSession design that imports from domain_models.
"""

from datetime import datetime, timedelta

import pytest

from claude.domain_models import PendingApproval, RunningWorkflow


# Fixtures
@pytest.fixture
def sample_session():
    """Fixture to create a fresh ChatSession for each test"""
    # Import here to avoid circular imports during test collection
    from claude.session_manager import ChatSession

    return ChatSession("test_session_123")


@pytest.fixture
def sample_workflow():
    """Fixture for a test workflow"""
    return RunningWorkflow("wf_1", "finance", "Tesla research", datetime.now())


@pytest.fixture
def sample_approval():
    """Fixture for a test approval"""
    return PendingApproval("ap_1", "finance", "Create Tesla research", {}, datetime.now())


# Test functions for ChatSession
def test_create_session():
    """Should create session with just basic data"""
    from claude.session_manager import ChatSession

    session = ChatSession("session_123")
    assert session.session_id == "session_123"
    assert session.workflows == {}
    assert session.pending_approvals == {}
    assert session.message_history == []
    assert isinstance(session.created_at, datetime)
    assert isinstance(session.last_activity, datetime)


def test_add_workflow_to_domain(sample_session, sample_workflow):
    """Should store workflow by domain key"""
    result = sample_session.add_workflow("finance", sample_workflow)

    assert result
    assert "finance" in sample_session.workflows
    assert sample_session.workflows["finance"] == sample_workflow
    assert sample_session.get_workflow("finance") == sample_workflow


def test_replace_workflow_in_same_domain(sample_session, capsys):
    """Should prevent replacing existing workflow in same domain and give warning"""
    workflow1 = RunningWorkflow("wf_1", "finance", "Tesla research", datetime.now())
    workflow2 = RunningWorkflow("wf_2", "finance", "NVDA research", datetime.now())

    # Add first workflow
    result1 = sample_session.add_workflow("finance", workflow1)
    assert result1

    # Try to add second workflow for same domain
    result2 = sample_session.add_workflow("finance", workflow2)
    assert not result2

    # The original workflow should still be there
    assert sample_session.workflows["finance"] == workflow1
    assert sample_session.get_workflow("finance") == workflow1
    assert len(sample_session.workflows) == 1

    # Check that a warning was printed
    captured = capsys.readouterr()
    assert "Warning: Cannot add workflow for domain 'finance'" in captured.out
    assert "wf_1" in captured.out


@pytest.mark.parametrize("domain", ["finance", "travel", "exercise", "nutrition"])
def test_workflow_domains(sample_session, domain):
    """Should handle workflows in different domains"""
    workflow = RunningWorkflow("wf_1", domain, f"Test {domain} task", datetime.now())
    sample_session.add_workflow(domain, workflow)
    assert sample_session.get_workflow(domain) == workflow


def test_multiple_concurrent_domains(sample_session):
    """Should handle multiple concurrent domains"""
    finance_wf = RunningWorkflow("wf_1", "finance", "Tesla research", datetime.now())
    travel_wf = RunningWorkflow("wf_2", "travel", "Paris trip", datetime.now())

    sample_session.add_workflow("finance", finance_wf)
    sample_session.add_workflow("travel", travel_wf)

    assert len(sample_session.workflows) == 2
    assert sample_session.get_workflow("finance") == finance_wf
    assert sample_session.get_workflow("travel") == travel_wf


def test_remove_workflow(sample_session, sample_workflow):
    """Should remove workflow from domain"""
    sample_session.add_workflow("finance", sample_workflow)
    assert sample_session.get_workflow("finance") == sample_workflow

    removed = sample_session.remove_workflow("finance")
    assert removed
    assert sample_session.get_workflow("finance") is None
    assert "finance" not in sample_session.workflows


def test_remove_nonexistent_workflow(sample_session):
    """Should handle removing workflow that doesn't exist"""
    removed = sample_session.remove_workflow("finance")
    assert not removed


def test_get_workflow_nonexistent_domain(sample_session):
    """Should return None for nonexistent domain"""
    workflow = sample_session.get_workflow("nonexistent")
    assert workflow is None


def test_add_pending_approval(sample_session, sample_approval):
    """Should handle domain-keyed pending approvals"""
    result = sample_session.add_pending_approval("finance", sample_approval)

    assert result
    assert sample_session.has_pending_approval("finance")
    assert not sample_session.has_pending_approval("travel")
    assert "finance" in sample_session.pending_approvals


def test_add_duplicate_pending_approval(sample_session, sample_approval):
    """Should reject adding a second pending approval for same domain"""
    # Add first approval
    result1 = sample_session.add_pending_approval("finance", sample_approval)
    assert result1

    # Try to add second approval for same domain
    second_approval = PendingApproval("ap_2", "finance", "Second approval", {}, datetime.now())
    result2 = sample_session.add_pending_approval("finance", second_approval)

    assert not result2
    assert sample_session.has_pending_approval("finance")
    # First approval should still be there
    assert sample_session.pending_approvals["finance"].id == "ap_1"


def test_remove_pending_approval(sample_session, sample_approval):
    """Should remove and return pending approval"""
    sample_session.add_pending_approval("finance", sample_approval)
    assert sample_session.has_pending_approval("finance")

    removed_approval = sample_session.remove_pending_approval("finance")
    assert removed_approval == sample_approval
    assert not sample_session.has_pending_approval("finance")


def test_remove_nonexistent_approval(sample_session):
    """Should return None when removing nonexistent approval"""
    removed = sample_session.remove_pending_approval("finance")
    assert removed is None


@pytest.mark.parametrize(
    "approval_domain,workflow_domain,expected_domains",
    [
        ("finance", "travel", {"finance", "travel"}),
        ("exercise", "exercise", {"exercise"}),
        ("finance", "finance", {"finance"}),
    ],
)
def test_get_all_domains(sample_session, approval_domain, workflow_domain, expected_domains):
    """Should return all domains with workflows or approvals"""
    # Add workflow
    workflow = RunningWorkflow("wf_1", workflow_domain, f"{workflow_domain} task", datetime.now())
    sample_session.add_workflow(workflow_domain, workflow)

    # Add approval
    approval = PendingApproval("ap_1", approval_domain, f"{approval_domain} approval", {}, datetime.now())
    sample_session.add_pending_approval(approval_domain, approval)

    domains = sample_session.get_all_domains()
    assert domains == expected_domains


def test_update_activity(sample_session):
    """Should update last activity timestamp"""
    original_time = sample_session.last_activity

    # Small delay to ensure timestamp difference
    import time

    time.sleep(0.01)

    sample_session.update_activity()
    assert sample_session.last_activity > original_time


def test_has_pending_approval_false(sample_session):
    """Should return False when no pending approval exists"""
    assert not sample_session.has_pending_approval("finance")
    assert not sample_session.has_pending_approval("travel")


def test_empty_session_domains(sample_session):
    """Should return empty set when no workflows or approvals exist"""
    domains = sample_session.get_all_domains()
    assert domains == set()


def test_add_message(sample_session):
    """Should add message to history and update activity"""
    original_time = sample_session.last_activity

    import time

    time.sleep(0.01)

    sample_session.add_message("Hello world")

    assert len(sample_session.message_history) == 1
    assert sample_session.message_history[0] == "Hello world"
    assert sample_session.last_activity > original_time


def test_session_expiry(sample_session):
    """Should detect expired sessions"""
    # Session should not be expired initially
    assert not sample_session.is_expired(timeout_minutes=30)

    # Manually set old last_activity
    sample_session.last_activity = datetime.now() - timedelta(minutes=31)

    assert sample_session.is_expired(timeout_minutes=30)


def test_cleanup_expired_approvals():
    """Should clean up expired approvals"""
    from claude.session_manager import ChatSession

    session = ChatSession("test_session")

    # Add valid approval
    valid_approval = PendingApproval(
        "ap_1", "finance", "Valid approval", {}, datetime.now(), expires_at=datetime.now() + timedelta(minutes=5)
    )
    session.add_pending_approval("finance", valid_approval)

    # Add expired approval
    expired_approval = PendingApproval(
        "ap_2",
        "travel",
        "Expired approval",
        {},
        datetime.now() - timedelta(minutes=15),
        expires_at=datetime.now() - timedelta(minutes=5),
    )
    session.add_pending_approval("travel", expired_approval)

    # Should have both approvals initially
    assert len(session.pending_approvals) == 2

    # Cleanup should remove expired approval
    removed_count = session.cleanup_expired_approvals()
    assert removed_count == 1
    assert len(session.pending_approvals) == 1
    assert "finance" in session.pending_approvals
    assert "travel" not in session.pending_approvals


def test_has_pending_approval_cleans_expired(sample_session):
    """Should clean up expired approvals when checking"""
    # Add expired approval
    expired_approval = PendingApproval(
        "ap_1",
        "finance",
        "Expired approval",
        {},
        datetime.now() - timedelta(minutes=15),
        expires_at=datetime.now() - timedelta(minutes=5),
    )
    sample_session.add_pending_approval("finance", expired_approval)

    # Should have approval initially
    assert "finance" in sample_session.pending_approvals

    # Checking should clean up expired approval
    has_pending = sample_session.has_pending_approval("finance")
    assert not has_pending
    assert "finance" not in sample_session.pending_approvals


def test_session_to_dict(sample_session):
    """Should convert session to dictionary"""
    # Add some data
    workflow = RunningWorkflow("wf_1", "finance", "Tesla research", datetime.now())
    approval = PendingApproval("ap_1", "travel", "Plan trip", {}, datetime.now())

    sample_session.add_workflow("finance", workflow)
    sample_session.add_pending_approval("travel", approval)
    sample_session.add_message("Hello")

    session_dict = sample_session.to_dict()

    assert session_dict["session_id"] == sample_session.session_id
    assert isinstance(session_dict["created_at"], str)  # ISO format
    assert isinstance(session_dict["last_activity"], str)  # ISO format
    assert session_dict["message_count"] == 1
    assert session_dict["workflow_domains"] == ["finance"]
    assert session_dict["pending_approval_domains"] == ["travel"]
    assert session_dict["total_domains"] == 2


# Tests for SessionManager
def test_create_session_manager():
    """Should create session manager with default settings"""
    from claude.session_manager import SessionManager

    manager = SessionManager()
    assert manager.session_timeout == 30
    assert manager.sessions == {}


def test_session_manager_create_session():
    """Should create and return sessions"""
    from claude.session_manager import SessionManager

    manager = SessionManager()
    session = manager.create_session("test_123")

    assert session.session_id == "test_123"
    assert "test_123" in manager.sessions
    assert manager.get_session("test_123") == session


def test_session_manager_get_nonexistent_session():
    """Should return None for nonexistent session"""
    from claude.session_manager import SessionManager

    manager = SessionManager()
    session = manager.get_session("nonexistent")
    assert session is None


def test_session_manager_delete_session():
    """Should delete sessions and return success status"""
    from claude.session_manager import SessionManager

    manager = SessionManager()
    session = manager.create_session("test_123")

    # Should delete successfully
    deleted = manager.delete_session("test_123")
    assert deleted
    assert "test_123" not in manager.sessions

    # Should return False for nonexistent session
    deleted_again = manager.delete_session("test_123")
    assert not deleted_again


def test_session_manager_stats():
    """Should provide session statistics"""
    from claude.session_manager import SessionManager

    manager = SessionManager()

    # Empty stats
    stats = manager.get_session_stats()
    assert stats["total_sessions"] == 0
    assert stats["total_active_workflows"] == 0
    assert stats["total_pending_approvals"] == 0
    assert stats["unique_domains"] == []

    # Add sessions with workflows and approvals
    session1 = manager.create_session("session_1")
    session2 = manager.create_session("session_2")

    workflow1 = RunningWorkflow("wf_1", "finance", "Research", datetime.now())
    workflow2 = RunningWorkflow("wf_2", "travel", "Plan trip", datetime.now())
    approval1 = PendingApproval("ap_1", "exercise", "Create plan", {}, datetime.now())

    session1.add_workflow("finance", workflow1)
    session1.add_pending_approval("exercise", approval1)
    session2.add_workflow("travel", workflow2)

    stats = manager.get_session_stats()
    assert stats["total_sessions"] == 2
    assert stats["total_active_workflows"] == 2
    assert stats["total_pending_approvals"] == 1
    assert set(stats["unique_domains"]) == {"finance", "travel", "exercise"}
    assert stats["domain_count"] == 3


def test_session_manager_session_details():
    """Should provide detailed session information"""
    from claude.session_manager import SessionManager

    manager = SessionManager()

    # Nonexistent session
    details = manager.get_session_details("nonexistent")
    assert details is None

    # Session with data
    session = manager.create_session("test_123")
    workflow = RunningWorkflow("wf_1", "finance", "Research", datetime.now())
    approval = PendingApproval("ap_1", "travel", "Plan trip", {}, datetime.now())

    session.add_workflow("finance", workflow)
    session.add_pending_approval("travel", approval)

    details = manager.get_session_details("test_123")
    assert details is not None
    assert details["session_id"] == "test_123"
    assert "workflows" in details
    assert "approvals" in details
    assert "finance" in details["workflows"]
    assert "travel" in details["approvals"]
