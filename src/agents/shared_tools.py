"""
Shared tools available to all specialist coaches.
These are actual function definitions that can be imported and used.
"""

import os
from typing import Any, Dict, Optional

from duckduckgo_search import DDGS
from google import genai
from google.genai import types

from src.agents.utils import (
    non_terminal_function,
    terminal_function,
)


@terminal_function
def hand_off_to_triage_agent() -> Dict[str, str]:
    """Return conversation to main assistant when topic is outside expertise.

    Returns:
        Dict indicating handoff to triage agent
    """
    return {"action": "hand_off_to_triage_agent"}


@terminal_function
def create_artifacts(domain: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create task for complex multi-step processes.

    Args:
        domain: The domain for the artifact (e.g., "exercise_plan", "meal_plan")
        data: The data/context needed to create the artifact

    Returns:
        Dict with task creation details
    """
    return {"action": "create_artifacts", "domain": domain, "data": data}


@non_terminal_function
def search_internet(query_prompt: str) -> str:
    """Search web using gemini AI model.

    Args:
        query: The search query prompt to the gemini model

    Returns:
        text with citations in format [1](link1)[2](link2)
    """
    # Define the grounding tool
    grounding_tool = types.Tool(google_search=types.GoogleSearch())

    # Configure generation settings
    config = types.GenerateContentConfig(tools=[grounding_tool])
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Make the request
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite-preview-06-17",
        contents=query_prompt,
        config=config,
    )

    def add_citations(response):
        text = response.text
        supports = response.candidates[0].grounding_metadata.grounding_supports
        chunks = response.candidates[0].grounding_metadata.grounding_chunks

        # Sort supports by end_index in descending order to avoid shifting issues when inserting.
        sorted_supports = sorted(supports, key=lambda s: s.segment.end_index, reverse=True)

        for support in sorted_supports:
            end_index = support.segment.end_index
            if support.grounding_chunk_indices:
                # Create citation string like [1](link1)[2](link2)
                citation_links = []
                for i in support.grounding_chunk_indices:
                    if i < len(chunks):
                        uri = chunks[i].web.uri
                        citation_links.append(f"[{i + 1}]({uri})")

                citation_string = ", ".join(citation_links)
                text = text[:end_index] + citation_string + text[end_index:]

        return text

    return add_citations(response)


@non_terminal_function
def search_internet_duckduckgo(
    query: str, timeframe: Optional[str] = None, region: Optional[str] = None, max_results: int = 10
) -> str:
    """Search web using duckduckgo-search Python package.

    Args:
        query: The search query string
        timeframe: Optional timeframe filter - 'd' (day), 'w' (week), 'm' (month), 'y' (year)
        region: Optional region code (e.g., 'us-en', 'uk-en', 'de-de')
        max_results: Maximum number of results to return (default: 10)

    Returns:
        Formatted search results with titles, snippets, and URLs
    """
    try:
        with DDGS() as ddgs:
            # Set up search parameters
            search_params = {"keywords": query, "max_results": max_results}

            if region:
                search_params["region"] = region

            if timeframe:
                # Map single letter to full timeframe name
                timeframe_map = {"d": "day", "w": "week", "m": "month", "y": "year"}
                search_params["timelimit"] = timeframe_map.get(timeframe, timeframe)

            # Perform search
            results = list(ddgs.text(**search_params))

            # Format results
            formatted_results = []
            for i, result in enumerate(results, 1):
                title = result.get("title", "No title")
                body = result.get("body", "No description")
                href = result.get("href", "No URL")
                formatted_results.append(f"[{i}] {title}\n{body}\n{href}\n")

            if not formatted_results:
                return "No search results found."

            return "\n".join(formatted_results)

    except Exception as e:
        return f"Error performing search: {str(e)}"


@non_terminal_function
def search_internet_google_custom(
    query: str, num_results: int = 10, date_restrict: Optional[str] = None, site_search: Optional[str] = None
) -> str:
    """Search web using Google Custom Search API.

    Args:
        query: The search query string
        num_results: Number of results to return (max 10 per request)
        date_restrict: Optional date restriction (e.g., 'd1' for past day, 'w1' for past week, 'm1' for past month)
        site_search: Optional site to search within (e.g., 'stackoverflow.com')

    Returns:
        Formatted search results with titles, snippets, and URLs
    """
    api_key = os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY")
    search_engine_id = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")

    if not api_key or not search_engine_id:
        return "Error: Missing Google Custom Search credentials. Set GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_CUSTOM_SEARCH_ENGINE_ID in .env"

    url = "https://www.googleapis.com/customsearch/v1"

    params = {
        "key": api_key,
        "cx": search_engine_id,
        "q": query,
        "num": min(num_results, 10),  # Google Custom Search API max is 10 per request
    }

    if date_restrict:
        params["dateRestrict"] = date_restrict

    if site_search:
        params["siteSearch"] = site_search

    try:
        import requests

        response = requests.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        # Check for errors in response
        if "error" in data:
            return f"Google API Error: {data['error'].get('message', 'Unknown error')}"

        # Format results
        formatted_results = []
        items = data.get("items", [])
        for i, item in enumerate(items, 1):
            title = item.get("title", "No title")
            snippet = item.get("snippet", "No description")
            link = item.get("link", "No URL")
            formatted_results.append(f"[{i}] {title}\n{snippet}\n{link}\n")

        if not formatted_results:
            return "No search results found."

        # Add search metadata if available
        search_info = data.get("searchInformation", {})
        total_results = search_info.get("formattedTotalResults", "Unknown")
        search_time = search_info.get("formattedSearchTime", "Unknown")

        metadata = f"Found {total_results} results in {search_time} seconds\n\n"

        return metadata + "\n".join(formatted_results)

    except requests.RequestException as e:
        return f"Error performing search: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
