import re

from langgraph.graph import END
from langchain_core.messages import SystemMessage
from web_searcher.models.schemas import AgentState


def select_tool(state: AgentState):
    action = state["prediction"]["action"]
    if action == "ANSWER":
        return END
    if action == "retry":
        return "agent"
    return action


def update_scratchpad(state: AgentState):
    old = state.get("scratchpad")
    if old:
        txt = old[0].content
        last_line = txt.rsplit("\n", 1)[-1]
        step = int(re.match(r"\d+", last_line).group()) + 1
    else:
        txt = "Previous action observations:\n"
        step = 1

    txt += f"\n{step}. {state['observation']}"
    return {**state, "scratchpad": [SystemMessage(content=txt)]}
