import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphRecursionError

from graph import build_graph
from tools import (
    get_pod_logs_and_events, list_deployments, list_nodes, list_pods, list_services,
)


def main():
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Add OPENAI_API_KEY to the .env file before running this script.")

    llm = ChatOpenAI(model="gpt-5.6-luna", use_responses_api=True)
    tools = [list_nodes, list_pods, list_deployments, list_services, get_pod_logs_and_events]
    messages = [
        SystemMessage(
            content="list out all the pods in the default namespace"
        ),
    ]
    graph = build_graph(llm, tools)
    try:
        result = graph.invoke({"messages": messages}, config={"recursion_limit": 21})
    except GraphRecursionError:
        raise SystemExit("Stopped at the graph step limit. Try a more specific instruction.")
    print(result["messages"][-1].text)


if __name__ == "__main__":
    main()
