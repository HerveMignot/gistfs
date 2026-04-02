"""Sample: Using GistKVStore as a persistent docstore for a LlamaIndex RAG pipeline.

Requires:
    pip install gistfs[llamaindex] llama-index-llms-azure-openai llama-index-embeddings-azure-openai

Environment variables (set in .env):
    GITHUB_TOKEN, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION
"""

import os

from dotenv import load_dotenv

load_dotenv()

from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.llms.azure_openai import AzureOpenAI

from gistfs.integrations.llamaindex import GistKVStore

# ── Azure OpenAI setup ──────────────────────────────────────────────

llm = AzureOpenAI(
    deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
)

embed_model = AzureOpenAIEmbedding(
    deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
)

Settings.llm = llm
Settings.embed_model = embed_model

# ── Gist-backed KV store ────────────────────────────────────────────

# Create a new gist to hold our document store (or reuse an existing gist_id)
kv_store = GistKVStore.create(description="llamaindex-sample docstore")
print(f"Created gist: {kv_store._mem.gfs.gist_id}")

# Store some documents via the KVStore
kv_store.put("doc1", {"text": "Paris is the capital of France.", "id": "doc1"})
kv_store.put("doc2", {"text": "Berlin is the capital of Germany.", "id": "doc2"})
kv_store.put("doc3", {"text": "Tokyo is the capital of Japan.", "id": "doc3"})

# Verify persistence
print("Stored keys:", list(kv_store.get_all().keys()))
print("doc1:", kv_store.get("doc1"))

# Build an index from the stored documents
nodes = [
    TextNode(text=kv_store.get(k)["text"], id_=k)
    for k in kv_store.get_all()
]

index = VectorStoreIndex(nodes)
query_engine = index.as_query_engine()

# Query
response = query_engine.query("What is the capital of Japan?")
print(f"\nQuery: What is the capital of Japan?")
print(f"Response: {response}")

# Cleanup
kv_store._mem.gfs.delete_gist()
print("\nGist cleaned up.")
