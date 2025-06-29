"""
Context Aggregator for multi-domain workflow context loading.

This module provides functionality to aggregate context from multiple
domain workflows for LLM consumption, converting context dictionaries
to formatted strings for better LLM readability.
"""

import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from claude.session_manager import ChatSession


class ContextAggregator:
    """Aggregates context from multiple domain workflows for LLM queries."""

    def __init__(self, max_context_size: int = 10000):
        """
        Initialize the context aggregator.

        Args:
            max_context_size: Maximum size of context in characters
        """
        self.max_context_size = max_context_size
        self.domain_extractors: Dict[str, Callable] = {}

    def register_domain_extractor(self, domain: str, extractor: Callable) -> None:
        """
        Register a custom context extractor for a specific domain.

        Args:
            domain: Domain name
            extractor: Function that takes a workflow and returns custom context dict
        """
        self.domain_extractors[domain] = extractor

    def aggregate_context(
        self,
        session: Optional[ChatSession],
        filter_domains: Optional[List[str]] = None,
        summarize: bool = False,
        include_messages: bool = False,
        max_messages: int = 5,
    ) -> Dict[str, Any]:
        """
        Aggregate context from session workflows.

        Args:
            session: Chat session to aggregate from
            filter_domains: Optional list of domains to include
            summarize: Whether to summarize large contexts
            include_messages: Whether to include recent messages
            max_messages: Maximum number of recent messages to include

        Returns:
            Aggregated context dictionary with string-formatted contexts
        """
        if session is None or not isinstance(session, ChatSession):
            return {
                "error": "Invalid session",
                "formatted_context": "No valid session",
            }

        context = {
            "session_id": session.session_id,
            "formatted_context": "",
        }

        # Build formatted context string
        context_lines = []

        for domain, workflow in session.workflows.items():
            if filter_domains and domain not in filter_domains:
                continue

            # Add domain header
            context_lines.append(f"Domain: {domain}")

            # Build workflow context with string formatting
            workflow_context = self._build_workflow_context(workflow, summarize)
            context_lines.append(f"  Workflow: {workflow.description}")
            context_lines.append(f"  Status: {workflow_context['status']}")
            if workflow_context.get("progress", 0) > 0:
                context_lines.append(f"  Progress: {workflow_context['progress']:.1%}")
            context_lines.append(f"  Context: {workflow_context['context']}")

            if workflow_context.get("custom_context"):
                context_lines.append(f"  Custom Context: {workflow_context['custom_context']}")

            context_lines.append("")  # Empty line between domains

        # Add pending approvals
        for domain, approval in session.pending_approvals.items():
            if filter_domains and domain not in filter_domains:
                continue

            # Add approval to the domain section if it exists, or create new section
            domain_found = False
            for i, line in enumerate(context_lines):
                if line == f"Domain: {domain}":
                    domain_found = True
                    # Find where to insert approval (after domain workflows)
                    insert_idx = i + 1
                    while insert_idx < len(context_lines) and context_lines[insert_idx].startswith("  "):
                        insert_idx += 1
                    context_lines.insert(insert_idx, f"  Pending Approval: {approval.description}")
                    context_lines.insert(
                        insert_idx + 1, f"  Approval Details: {self._format_approval_details(approval.triage_result)}"
                    )
                    break

            if not domain_found:
                context_lines.append(f"Domain: {domain}")
                context_lines.append(f"  Pending Approval: {approval.description}")
                context_lines.append(f"  Approval Details: {self._format_approval_details(approval.triage_result)}")
                context_lines.append("")  # Empty line

        # Workflows are now handled in the main loop above since both active and completed
        # workflows are stored in the same 'workflows' dict, differentiated by status

        # Set formatted context
        context["formatted_context"] = "\n".join(context_lines).strip()
        if not context["formatted_context"]:
            context["formatted_context"] = "No active workflows"

        # Include recent messages if requested
        if include_messages and hasattr(session, "message_history"):
            context["recent_messages"] = session.message_history[-max_messages:]

        # Check context size and truncate if needed
        if len(context["formatted_context"]) > self.max_context_size:
            context = self._truncate_context(context, len(context["formatted_context"]))

        return context

    def _build_workflow_context(self, workflow: Any, summarize: bool) -> Dict[str, Any]:
        """Build context dictionary for a single workflow with string-formatted context."""
        # Extract basic workflow info
        workflow_id = workflow.id
        domain = workflow.domain
        description = workflow.description
        created_at = workflow.created_at.isoformat()

        # Get workflow context dict
        context_dict = workflow.context

        # Convert context dictionary to formatted string
        context_string = self._format_context_dict(context_dict, domain, summarize)

        # Add workflow status from the workflow object itself
        status = "unknown"
        if hasattr(workflow, "status"):
            status = workflow.status.value if hasattr(workflow.status, "value") else str(workflow.status)

        workflow_context = {
            "workflow_id": workflow_id,
            "domain": domain,
            "description": description,
            "status": status,
            "created_at": created_at,
            "context": context_string,
            "progress": getattr(workflow, "progress", 0.0),
        }

        # Add custom context if extractor registered
        if domain in self.domain_extractors:
            custom_context = self.domain_extractors[domain](workflow)
            workflow_context["custom_context"] = self._format_context_dict(custom_context, domain, summarize)

        # Add freshness info
        if hasattr(workflow, "last_update"):
            age_seconds = (datetime.now() - workflow.last_update).total_seconds()
            workflow_context["last_updated_seconds_ago"] = int(age_seconds)

        return workflow_context

    def _format_context_dict(self, context_dict: Dict[str, Any], domain: str, summarize: bool) -> str:
        """Convert context dictionary to formatted string for LLM consumption."""
        if not context_dict:
            return "No context available"

        # Check if we have a domain-specific formatter
        formatter_method = f"_format_{domain}_context"
        if hasattr(self, formatter_method):
            return getattr(self, formatter_method)(context_dict, summarize)

        # Default formatting
        return self._format_default_context(context_dict, summarize)

    def _format_default_context(self, context_dict: Dict[str, Any], summarize: bool) -> str:
        """Default context formatting - simple key-value pairs."""
        if summarize and len(json.dumps(context_dict)) > 1000:
            # Extract key information for summary
            summary_keys = ["intent", "status", "progress", "current_step", "summary", "error"]
            filtered_dict = {k: v for k, v in context_dict.items() if k in summary_keys}

            # Check for summary in state subdict too
            if "state" in context_dict and isinstance(context_dict["state"], dict):
                state = context_dict["state"]
                if "summary" in state:
                    return f"Summary: {state['summary']}"

            if "summary" in context_dict:
                return f"Summary: {context_dict['summary']}"
            context_dict = filtered_dict

        lines = []
        for key, value in context_dict.items():
            if isinstance(value, dict):
                # Nested dict - format as sub-section
                lines.append(f"{key.title()}:")
                for sub_key, sub_value in value.items():
                    lines.append(f"  {sub_key}: {sub_value}")
            elif isinstance(value, list):
                # List - format as bullet points
                lines.append(f"{key.title()}: {', '.join(map(str, value))}")
            else:
                lines.append(f"{key.title()}: {value}")

        return "\n".join(lines)

    def _format_finance_context(self, context_dict: Dict[str, Any], summarize: bool) -> str:
        """Finance-specific context formatting."""
        lines = []

        # Priority fields for finance workflows
        if "intent" in context_dict:
            lines.append(f"Intent: {context_dict['intent']}")

        if "entities" in context_dict:
            entities = context_dict["entities"]
            if "symbol" in entities:
                lines.append(f"Symbol: {entities['symbol']}")
            if "amount" in entities:
                amount = entities["amount"]
                if isinstance(amount, (int, float)):
                    lines.append(f"Amount: ${amount:,.2f}")
                else:
                    lines.append(f"Amount: {amount}")

        if "state" in context_dict:
            state = context_dict["state"]
            if "status" in state:
                status = state["status"]
                progress = state.get("progress", "")
                if progress:
                    lines.append(f"Status: {status} ({progress}% complete)")
                else:
                    lines.append(f"Status: {status}")

            if "risk_level" in state:
                lines.append(f"Risk Level: {state['risk_level']}")

        # Add other fields
        remaining_fields = {k: v for k, v in context_dict.items() if k not in ["intent", "entities", "state"]}
        for key, value in remaining_fields.items():
            lines.append(f"{key.title()}: {value}")

        return "\n".join(lines)

    def _format_hr_context(self, context_dict: Dict[str, Any], summarize: bool) -> str:
        """HR-specific context formatting."""
        lines = []

        if "intent" in context_dict:
            lines.append(f"Intent: {context_dict['intent']}")

        if "entities" in context_dict:
            entities = context_dict["entities"]
            if "employee_id" in entities:
                lines.append(f"Employee ID: {entities['employee_id']}")

        if "state" in context_dict:
            state = context_dict["state"]
            if "status" in state:
                lines.append(f"Status: {state['status']}")

            if "documents_required" in state:
                docs = state["documents_required"]
                lines.append(f"Documents Required: {', '.join(docs) if isinstance(docs, list) else docs}")

            if "documents_received" in state:
                docs = state["documents_received"]
                lines.append(f"Documents Received: {', '.join(docs) if isinstance(docs, list) else docs}")

            if "next_step" in state:
                lines.append(f"Next Step: {state['next_step']}")

        return "\n".join(lines)

    def _format_approval_details(self, details: Dict[str, Any]) -> str:
        """Format approval details as a readable string."""
        if not details:
            return "No details available"

        lines = []
        for key, value in details.items():
            lines.append(f"{key.title()}: {value}")

        return "; ".join(lines)

    def _truncate_context(self, context: Dict[str, Any], current_size: int) -> Dict[str, Any]:
        """Truncate context to fit size limit."""
        context["truncated"] = True
        context["truncation_info"] = {
            "original_size": current_size,
            "max_size": self.max_context_size,
        }

        # Truncate the formatted context string
        max_content_size = self.max_context_size - 200  # Leave room for metadata
        truncated_content = context["formatted_context"][:max_content_size]
        context["formatted_context"] = truncated_content + "\n\n... [context truncated due to size limit]"

        return context
