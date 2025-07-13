import os

from langgraph.graph import START, StateGraph
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_openai import ChatOpenAI
from langchain import hub

from web_searcher.agents.edge import select_tool, update_scratchpad
from web_searcher.agents.nodes import parse, format_descriptions, annotate
from web_searcher.agents.tools import click, type_text, scroll, wait, go_back, to_search_engine
from web_searcher.models.schemas import AgentState


def create_agent_graph():
    # Load prompt from hub
    prompt = hub.pull("wfh/web-voyager")
    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL"), max_tokens=os.getenv("OPENAI_MAX_TOKENS"))

    agent = annotate | RunnablePassthrough.assign(
        prediction=format_descriptions | prompt | llm | StrOutputParser() | parse
    )

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("agent", agent)
    graph_builder.add_edge(START, "agent")
    graph_builder.add_node("update_scratchpad", update_scratchpad)
    graph_builder.add_edge("update_scratchpad", "agent")

    tools = {
        "Click": click,
        "Type": type_text,
        "Scroll": scroll,
        "Wait": wait,
        "GoBack": go_back,
        "Google": to_search_engine,
    }

    for node_name, tool in tools.items():
        graph_builder.add_node(
            node_name,
            RunnableLambda(tool) | (lambda observation: {"observation": observation}),
        )
        graph_builder.add_edge(node_name, "update_scratchpad")

    graph_builder.add_conditional_edges("agent", select_tool)
    return graph_builder.compile()
