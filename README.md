# gistfs

Use GitHub Gists as a persistent key-value filesystem — ideal for AI agent memory.

## Install

```bash
pip install gistfs
```

With optional integrations:

```bash
pip install gistfs[llamaindex]   # LlamaIndex KVStore
pip install gistfs[langgraph]    # LangGraph BaseStore
pip install gistfs[all]          # everything
```

## Quick start

### Creating a new gist

No need to create a gist manually — bootstrap one from code:

```python
from gistfs import GistFS

gfs = GistFS.create(description="my agent memory")
print(gfs.gist_id)  # save this for later

# Or with GistMemory:
from gistfs import GistMemory
mem = GistMemory.create(description="my agent memory")
```

### As a filesystem (context manager)

```python
from gistfs import GistFS

with GistFS(gist_id="your_gist_id") as gfs:
    gfs.write("config.json", {"model": "gpt-4", "temperature": 0.7})
    config = gfs.read("config.json")
    print(gfs.list_files())
    gfs.delete("config.json")
```

### As AI agent memory

```python
from gistfs import GistMemory

with GistMemory(gist_id="your_gist_id") as mem:
    mem.put("conversation_1", {"messages": [{"role": "user", "content": "hi"}]})
    history = mem.get("conversation_1")
    all_data = mem.get_all()
    mem.delete("conversation_1")
```

### LlamaIndex integration

```python
from gistfs.integrations.llamaindex import GistKVStore

store = GistKVStore(gist_id="your_gist_id")
store.put("doc1", {"text": "hello world"}, collection="docstore")
doc = store.get("doc1", collection="docstore")
```

### LangGraph integration

```python
from gistfs.integrations.langgraph import GistStore

store = GistStore(gist_id="your_gist_id")
store.put(("user", "prefs"), "theme", {"value": "dark"})
item = store.get(("user", "prefs"), "theme")
```

## Authentication

Set the `GITHUB_TOKEN` environment variable with a GitHub personal access token that has `gist` scope. Read-only operations on public gists work without a token.

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Or pass it directly:

```python
gfs = GistFS(gist_id="abc123", token="ghp_...")
```
