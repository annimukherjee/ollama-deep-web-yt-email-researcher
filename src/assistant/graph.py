import json

from typing_extensions import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from langgraph.graph import START, END, StateGraph
from email.mime.text import MIMEText
from email.header import Header

from assistant.configuration import Configuration, SearchAPI
from assistant.utils import (
    deduplicate_and_format_sources,
    tavily_search,
    format_sources,
    perplexity_search,
    youtube_search,  # new import for YouTube search
)
from assistant.state import SummaryState, SummaryStateInput, SummaryStateOutput
from assistant.prompts import (
    query_writer_instructions,
    summarizer_instructions,
    reflection_instructions,
)


# Nodes
def generate_query(state: SummaryState, config: RunnableConfig):
    """Generate a query for web search"""

    # Format the prompt
    query_writer_instructions_formatted = query_writer_instructions.format(
        research_topic=state.research_topic
    )

    # Generate a query
    configurable = Configuration.from_runnable_config(config)
    llm_json_mode = ChatOllama(
        model=configurable.local_llm, temperature=0, format="json"
    )
    result = llm_json_mode.invoke(
        [
            SystemMessage(content=query_writer_instructions_formatted),
            HumanMessage(content=f"Generate a query for web search:"),
        ]
    )
    query = json.loads(result.content)

    return {"search_query": query["query"]}


def web_research(state: SummaryState, config: RunnableConfig):
    """Gather information from the web"""

    # Configure
    configurable = Configuration.from_runnable_config(config)

    # Handle both cases for search_api:
    # 1. When selected in Studio UI -> returns a string (e.g. "tavily")
    # 2. When using default -> returns an Enum (e.g. SearchAPI.TAVILY)
    if isinstance(configurable.search_api, str):
        search_api = configurable.search_api
    else:
        search_api = configurable.search_api.value

    # Search the web
    if search_api == "tavily":
        search_results = tavily_search(
            state.search_query, include_raw_content=True, max_results=1
        )
        search_str = deduplicate_and_format_sources(
            search_results, max_tokens_per_source=1000, include_raw_content=True
        )
    elif search_api == "perplexity":
        search_results = perplexity_search(
            state.search_query, state.research_loop_count
        )
        search_str = deduplicate_and_format_sources(
            search_results, max_tokens_per_source=1000, include_raw_content=False
        )
    else:
        raise ValueError(f"Unsupported search API: {configurable.search_api}")

    state.web_research_results.append(search_str)
    state.sources_gathered.append(format_sources(search_results))

    return {
        "web_research_results": state.web_research_results,
        "research_loop_count": state.research_loop_count + 1,
    }


def youtube_research(state: SummaryState, config: RunnableConfig):
    """Gather information from YouTube videos, including transcripts."""

    configurable = Configuration.from_runnable_config(config)
    if not configurable.youtube_api_key:
        raise ValueError("YouTube API key not configured in Configuration.")

    youtube_results = youtube_search(
        state.search_query, configurable.youtube_api_key, max_results=3
    )
    youtube_str = deduplicate_and_format_sources(
        youtube_results, max_tokens_per_source=500, include_raw_content=True
    )
    state.youtube_research_results.append(youtube_str)
    state.sources_gathered.append(format_sources(youtube_results))

    return {"youtube_research_results": state.youtube_research_results}


def summarize_sources(state: SummaryState, config: RunnableConfig):
    """Summarize the gathered sources, including both web and YouTube research"""

    # Existing summary
    existing_summary = state.running_summary

    # Most recent web research (if any)
    most_recent_web_research = state.web_research_results[-1] if state.web_research_results else ""
    # Combine YouTube research results if available
    youtube_results_str = "\n".join(state.youtube_research_results) if state.youtube_research_results else ""

    # Build the human message including both sources
    if existing_summary:
        human_message_content = (
            f"<User Input> \n {state.research_topic} \n <User Input>\n\n"
            f"<Existing Summary> \n {existing_summary} \n <Existing Summary>\n\n"
            f"<New Web Search Results> \n {most_recent_web_research} \n <New Web Search Results>\n\n"
            f"<YouTube Search Results> \n {youtube_results_str} \n <YouTube Search Results>"
        )
    else:
        human_message_content = (
            f"<User Input> \n {state.research_topic} \n <User Input>\n\n"
            f"<Web Search Results> \n {most_recent_web_research} \n <Web Search Results>\n\n"
            f"<YouTube Search Results> \n {youtube_results_str} \n <YouTube Search Results>"
        )

    # Run the LLM to generate an updated summary
    configurable = Configuration.from_runnable_config(config)
    llm = ChatOllama(model=configurable.local_llm, temperature=0)
    result = llm.invoke(
        [
            SystemMessage(content=summarizer_instructions),
            HumanMessage(content=human_message_content),
        ]
    )

    running_summary = result.content

    # Remove any <think> tags if present
    while "<think>" in running_summary and "</think>" in running_summary:
        start = running_summary.find("<think>")
        end = running_summary.find("</think>") + len("</think>")
        running_summary = running_summary[:start] + running_summary[end:]

    state.running_summary = running_summary
    return {"running_summary": running_summary}


def reflect_on_summary(state: SummaryState, config: RunnableConfig):
    """Reflect on the summary and generate a follow-up query"""

    configurable = Configuration.from_runnable_config(config)
    llm_json_mode = ChatOllama(
        model=configurable.local_llm, temperature=0, format="json"
    )
    result = llm_json_mode.invoke(
        [
            SystemMessage(
                content=reflection_instructions.format(
                    research_topic=state.research_topic
                )
            ),
            HumanMessage(
                content=f"Identify a knowledge gap and generate a follow-up web search query based on our existing knowledge: {state.running_summary}"
            ),
        ]
    )
    follow_up_query = json.loads(result.content)

    query = follow_up_query.get("follow_up_query")
    if not query:
        return {"search_query": f"Tell me more about {state.research_topic}"}

    return {"search_query": follow_up_query["follow_up_query"]}


def finalize_summary(state: SummaryState):
    """Finalize the summary"""

    # Format all accumulated sources into a single bulleted list
    all_sources = "\n".join(source for source in state.sources_gathered)
    state.running_summary = (
        f"## Summary\n\n{state.running_summary}\n\n### Sources:\n{all_sources}"
    )
    return {"running_summary": state.running_summary}


def send_email(state: SummaryState, config: RunnableConfig):
    """Send the final summary via email."""
    configurable = Configuration.from_runnable_config(config)
    if not configurable.email_recipient:
        raise ValueError("Email recipient not configured in Configuration.")

    subject = f"Research Summary: {state.research_topic}"
    body = state.running_summary
    from_email = configurable.smtp_username if configurable.smtp_username else "no-reply@example.com"
    to_email = configurable.email_recipient

    # Create a MIMEText object to handle UTF-8 encoding
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = from_email
    msg["To"] = to_email

    import smtplib
    smtp_server = configurable.smtp_server or "smtp.gmail.com"
    smtp_port = configurable.smtp_port or 587

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        if configurable.smtp_username and configurable.smtp_password:
            server.login(configurable.smtp_username, configurable.smtp_password)
        server.sendmail(from_email, [to_email], msg.as_string())

    return {"email_sent": True}


def route_research(
    state: SummaryState, config: RunnableConfig
) -> Literal["finalize_summary", "web_research"]:
    """Route the research based on the follow-up query"""

    configurable = Configuration.from_runnable_config(config)
    if state.research_loop_count <= configurable.max_web_research_loops:
        return "web_research"
    else:
        return "finalize_summary"






# Add nodes and edges
builder = StateGraph(
    SummaryState,
    input=SummaryStateInput,
    output=SummaryStateOutput,
    config_schema=Configuration,
)

builder.add_node("generate_query", generate_query)
builder.add_node("web_research", web_research)
builder.add_node("youtube_research", youtube_research)  # new node for YouTube research
builder.add_node("summarize_sources", summarize_sources)
builder.add_node("reflect_on_summary", reflect_on_summary)
builder.add_node("finalize_summary", finalize_summary)
builder.add_node("send_email", send_email)  # new node for emailing the summary

# Add edges
builder.add_edge(START, "generate_query")
builder.add_edge("generate_query", "web_research")
builder.add_edge("web_research", "youtube_research")  # route to YouTube research after web research
builder.add_edge("youtube_research", "summarize_sources")
builder.add_edge("summarize_sources", "reflect_on_summary")
builder.add_conditional_edges("reflect_on_summary", route_research)
builder.add_edge("finalize_summary", "send_email")
builder.add_edge("send_email", END)

graph = builder.compile()