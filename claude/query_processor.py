"""
Query Processor for multi-domain context queries.

This module provides functionality to route query intents to multi-domain
context, integrate with LLM for response generation with domain awareness.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from claude.context_aggregator import ContextAggregator

if TYPE_CHECKING:
    from claude.session_manager import ChatSession


class QueryProcessor:
    """Processes queries with multi-domain context and LLM integration."""

    def __init__(
        self, 
        llm: Optional[Any] = None, 
        context_aggregator: Optional[ContextAggregator] = None,
        max_context_size: int = 8000
    ):
        """
        Initialize the query processor.

        Args:
            llm: Language model for query processing (defaults to GPT-4)
            context_aggregator: Context aggregator instance
            max_context_size: Maximum context size for LLM
        """
        if llm is not None:
            self.llm = llm
        else:
            try:
                self.llm = ChatOpenAI(model="gpt-4", temperature=0.3)
            except Exception:
                # For testing without API key
                self.llm = None
        self.context_aggregator = context_aggregator or ContextAggregator(max_context_size=max_context_size)
        self.max_context_size = max_context_size

    async def process_query(
        self,
        session: "ChatSession",
        intent_domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a query with multi-domain context using full conversation history.

        Args:
            session: Chat session containing workflows and conversation history
            intent_domain: The domain classification from TriageAgent (e.g., "finance", "hr")

        Returns:
            Query result dictionary with response and metadata
        """
        try:
            # Get the latest user message from conversation
            latest_user_msg = session.get_latest_user_message()
            if not latest_user_msg:
                return {
                    "status": "error",
                    "response": "No user message found in conversation history.",
                    "error_type": "no_user_message",
                    "domains_referenced": [],
                    "confidence": 0.0,
                    "timestamp": datetime.now().isoformat()
                }
            
            query = latest_user_msg.content
            
            # Aggregate context from session
            # Convert intent_domain to list for context aggregator
            filter_domains = [intent_domain] if intent_domain else None
            
            context = self.context_aggregator.aggregate_context(
                session=session,
                filter_domains=filter_domains,
                summarize=True,  # Always summarize for queries
                include_messages=True,  # Always include conversation context now
                max_messages=10  # Increased since we're using conversation history
            )

            # Extract domains referenced
            domains_referenced = self._extract_domain_names(context["formatted_context"])

            # Build LLM prompt with context and conversation history
            conversation_history = session.get_conversation_for_langchain(include_system=False)
            system_message = self._build_system_prompt(context, conversation_history)
            
            # Use conversation history instead of single message
            messages = [system_message] + conversation_history

            # Generate response using LLM
            llm_response = await self.llm.ainvoke(messages)
            response_content = llm_response.content

            # Calculate confidence score
            confidence = self._calculate_confidence(context, query, response_content)

            # Store AI response in session
            session.add_ai_message(response_content, source="query_processor")

            result = {
                "status": "completed",
                "response": response_content,
                "domains_referenced": domains_referenced,
                "confidence": confidence,
                "timestamp": datetime.now().isoformat(),
                "context_summary": self._summarize_context(context)
            }

            return result

        except Exception as e:
            return {
                "status": "error",
                "response": f"I encountered an error while processing your query: {str(e)}",
                "error_type": "llm_error",
                "domains_referenced": [],
                "confidence": 0.0,
                "timestamp": datetime.now().isoformat()
            }

    def _build_system_prompt(self, context: Dict[str, Any], conversation_history: List) -> SystemMessage:
        """Build system prompt with aggregated context and conversation awareness for LLM."""
        
        formatted_context = context.get("formatted_context", "")
        
        # Count conversation messages for context
        conversation_length = len(conversation_history)
        
        if not formatted_context or formatted_context == "No active workflows":
            # No workflows - simple response
            prompt = f"""You are a helpful assistant for a multi-domain workflow management system.
The user currently has no active workflows in their session.

Conversation Context: This conversation has {conversation_length} previous messages. Use the conversation history to understand context and references.

Instructions:
- Provide helpful, concise responses to their queries
- Reference previous parts of the conversation when relevant
- If they ask about "it", "that", or "the previous one", use conversation context to understand what they mean
- Maintain a professional but friendly tone"""
        else:
            prompt = f"""You are a helpful assistant for a multi-domain workflow management system.

Current Session Context:
{formatted_context}

Conversation Context: This conversation has {conversation_length} previous messages. Use the conversation history to understand context and references.

Instructions:
- Use the provided context to answer the user's query accurately
- Reference previous parts of the conversation when relevant (e.g., "the finance workflow we discussed")
- Be concise and relevant to their specific question
- Reference specific workflow details when relevant
- If asking about status, provide current progress and next steps
- If no relevant context exists, acknowledge this clearly
- If they use pronouns like "it", "that", or "the previous one", use conversation context to understand what they mean
- Maintain a professional but friendly tone"""

        return SystemMessage(content=prompt)

    def _extract_domain_names(self, formatted_context: str) -> List[str]:
        """Extract domain names from formatted context string."""
        import re
        domain_matches = re.findall(r'^Domain: (\w+)', formatted_context, re.MULTILINE)
        return domain_matches

    def _indent_text(self, text: str, spaces: int) -> str:
        """Indent text by specified number of spaces."""
        indent = " " * spaces
        return "\n".join(indent + line for line in text.split("\n"))


    def _calculate_confidence(self, context: Dict[str, Any], query: str, response: str) -> float:
        """Calculate confidence score for the query response."""
        confidence = 0.5  # Base confidence
        
        formatted_context = context.get("formatted_context", "")
        
        # Increase confidence if we have relevant context
        if formatted_context and formatted_context != "No active workflows":
            confidence += 0.2
        
        # Increase confidence if query matches workflow domains
        query_lower = query.lower()
        domain_names = self._extract_domain_names(formatted_context)
        for domain in domain_names:
            if domain.lower() in query_lower:
                confidence += 0.1
                break
        
        # Increase confidence if response is substantial
        if len(response.split()) > 10:
            confidence += 0.1
        
        # Decrease confidence if context was truncated
        if context.get("truncated"):
            confidence -= 0.1
        
        # Increase confidence if we have multiple domains (more context)
        if len(domain_names) > 1:
            confidence += 0.1
        
        return min(1.0, max(0.0, confidence))

    def _summarize_context(self, context: Dict[str, Any]) -> str:
        """Create a brief summary of the context used."""
        formatted_context = context.get("formatted_context", "")
        
        if not formatted_context or formatted_context == "No active workflows":
            return "No active workflows"
        
        domain_names = self._extract_domain_names(formatted_context)
        
        # Count workflows by counting workflow lines
        import re
        workflow_matches = re.findall(r'  Workflow:', formatted_context)
        completed_matches = re.findall(r'  Completed Workflow:', formatted_context)
        workflow_count = len(workflow_matches) + len(completed_matches)
        
        summary = f"{workflow_count} workflow(s) across {len(domain_names)} domain(s): {', '.join(domain_names)}"
        
        if context.get("truncated"):
            summary += " (context truncated)"
        
        return summary


    def calculate_domain_relevance(self, query: str, domain: str, session: "ChatSession") -> float:
        """Calculate relevance score of a domain for the given query."""
        relevance = 0.0
        query_lower = query.lower()
        
        # Direct domain mention
        if domain.lower() in query_lower:
            relevance += 0.5
        
        # Check if domain has workflows
        if domain in session.workflows:
            relevance += 0.2
            workflow = session.workflows[domain]
            
            # Check if query mentions workflow-specific terms
            context = getattr(workflow, "context", {})
            
            # Check entities
            entities = context.get("entities", {})
            for key, value in entities.items():
                if str(value).lower() in query_lower:
                    relevance += 0.2
                    break
            
            # Check description
            if hasattr(workflow, "description") and workflow.description.lower() in query_lower:
                relevance += 0.1
        
        # Domain-specific keywords
        domain_keywords = {
            "finance": ["portfolio", "stock", "investment", "money", "transfer", "analysis"],
            "hr": ["employee", "onboard", "documents", "orientation", "hiring"],
            "it": ["access", "provision", "system", "server", "deployment"],
            "analytics": ["data", "analysis", "report", "dashboard", "metrics"]
        }
        
        if domain in domain_keywords:
            for keyword in domain_keywords[domain]:
                if keyword in query_lower:
                    relevance += 0.1
                    break
        
        return min(1.0, relevance)

