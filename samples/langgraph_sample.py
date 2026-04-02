"""Sample: Using GistStore as persistent memory for a LangGraph chatbot.

The bot remembers user preferences across turns using a gist-backed store,
so memory survives restarts.

Requires:
    pip install gistfs[langgraph] langgraph langchain-openai

Environment variables (set in .env):
    GITHUB_TOKEN, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION
"""

import os

from dotenv import load_dotenv

load_dotenv()

from langchain_openai import AzureChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.store.base import BaseStore

from gistfs.integrations.langgraph import GistStore

# ── Azure OpenAI setup ──────────────────────────────────────────────

llm = AzureChatOpenAI(
    azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
)

# ── Gist-backed store ──────────────────────────────────────────────

store = GistStore.create(description="langgraph-sample memory")
gist_id = store._gfs.gist_id
print(f"Created gist: {gist_id}")


# ── Graph definition ───────────────────────────────────────────────

from typing import TypedDict


class State(TypedDict):
    user_id: str
    message: str
    response: str


def save_preference(state: State) -> State:
    """Extract and save a user preference from the message."""
    message = state["message"]

    # Ask the LLM to extract the preference
    result = llm.invoke(
        f"Extract the user preference from this message as a short label and value. "
        f"Reply with ONLY 'label: value' format. Message: {message}"
    )
    label, _, value = result.content.partition(":")

    if value.strip():
        store.put(
            ("user", state["user_id"], "prefs"),
            label.strip().lower(),
            {"value": value.strip()},
        )

    return state


def respond(state: State) -> State:
    """Generate a response using stored preferences as context."""
    # Retrieve all preferences for this user
    items = store.search(("user", state["user_id"], "prefs"))
    prefs = {item.key: item.value["value"] for item in items}

    context = f"User preferences: {prefs}" if prefs else "No known preferences."

    result = llm.invoke(
        f"{context}\n\n"
        f"User says: {state['message']}\n\n"
        f"Respond helpfully, referencing their preferences if relevant."
    )

    return {**state, "response": result.content}


# Build the graph
graph = StateGraph(State)
graph.add_node("save_preference", save_preference)
graph.add_node("respond", respond)
graph.set_entry_point("save_preference")
graph.add_edge("save_preference", "respond")
graph.add_edge("respond", END)

app = graph.compile()

# ── Run the conversation ───────────────────────────────────────────

user_id = "alice"

# Turn 1: set a preference
print("\n--- Turn 1 ---")
result = app.invoke({"user_id": user_id, "message": "I prefer dark mode", "response": ""})
print(f"User: {result['message']}")
print(f"Bot:  {result['response']}")

# Turn 2: set another preference
print("\n--- Turn 2 ---")
result = app.invoke({"user_id": user_id, "message": "My favorite language is Python", "response": ""})
print(f"User: {result['message']}")
print(f"Bot:  {result['response']}")

# Turn 3: ask something — bot should recall preferences
print("\n--- Turn 3 ---")
result = app.invoke({"user_id": user_id, "message": "What do you know about me?", "response": ""})
print(f"User: {result['message']}")
print(f"Bot:  {result['response']}")

# Show what's stored in the gist
print("\n--- Stored preferences ---")
for item in store.search(("user", user_id, "prefs")):
    print(f"  {item.key}: {item.value}")

# Prove persistence: reopen the same gist from scratch
print("\n--- Reopening gist to verify persistence ---")
store2 = GistStore(gist_id=gist_id)
for item in store2.search(("user", user_id, "prefs")):
    print(f"  {item.key}: {item.value}")

# Cleanup
store._gfs.delete_gist()
print("\nGist cleaned up.")
