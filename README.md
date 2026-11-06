# kube-autopilot

Call `gpt-5.6-luna` through LangChain to inspect Kubernetes resources using
read-only SDK tools: `list_nodes`, `list_namespaces`, `list_pods`, `list_deployments`, `list_services`,
and `get_pod_logs_and_events`.

All Kubernetes tools run in the independent `mcp_server` process. The chat app
and CLI discover and call them over MCP Streamable HTTP:

`Chat page -> FastAPI -> LangGraph -> HTTP MCP server -> Kubernetes SDK -> Cluster`

The MCP server does not need an OpenAI API key or PostgreSQL. Only the MCP
server machine needs the kubeconfig and access to the cluster. The chat app
needs its LLM credentials, database connection, MCP URL, and MCP token.

LangGraph manages execution in `graph.py`:
`START -> llm -> tools -> llm -> ... -> END`.
The shared `MessagesState` retains the instruction, model responses, and tool
results during each run. The graph ends when the model returns an answer
without tool calls, with a limit of 21 graph steps to bound repeated calls.
The web application saves graph state in PostgreSQL using `PostgresSaver`.
The original command-line application continues to use a fresh state per run.

Pods, deployments, services, and pod logs/events use namespace `default` when
no namespace is specified. Node and namespace listing are cluster-wide.

The tool uses the Kubernetes Python SDK (`CoreV1Api.list_node`) with your local kubeconfig's current
context. It uses `~/.kube/k8s-admin.conf` by default, or `KUBECONFIG` if set.
`~` resolves to the home directory of the user running Python. Run the application in the same
environment where your cluster connection works. Your Kubernetes identity must
have permission to list nodes. The tool returns node names, readiness,
scheduling status, kubelet versions, and addresses.

Run in PowerShell with Python 3.11 or later:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-mcp.txt
```

Edit the local `.env` file next to `main.py` and add your key:

```dotenv
OPENAI_API_KEY=your-openai-api-key
KUBECONFIG=~/.kube/k8s-admin.conf
POSTGRES_PASSWORD=your-local-database-password
DATABASE_URL=postgresql://kube_autopilot:your-local-database-password@127.0.0.1:5433/kube_autopilot?sslmode=disable
MCP_SERVER_URL=http://127.0.0.1:8002/mcp
MCP_AUTH_TOKEN=your-shared-mcp-token
```

The application loads this file on every run, including when launched from a
different directory. Values in `.env` override existing environment variables.
The `.env` file is excluded from Git by `.gitignore`.

The database settings have been generated in your local `.env`. For a new
checkout, set both database variables with the same password (URL-encode special
characters in the password inside `DATABASE_URL`). Do not commit `.env`.

Start PostgreSQL using Docker Desktop in Linux container mode:

```powershell
docker compose up -d --wait
```

Compose uses PostgreSQL 18, publishes it only on `127.0.0.1:5433`, and stores
data in the `postgres_data` named volume. `docker compose stop` or
`docker compose down` retains history. Do not use `docker compose down -v`
unless you intend to delete the database volume. Keep this volume when
recreating containers. PostgreSQL must be available before the app starts.

Start the independent MCP server in its own terminal before the chat app:

```powershell
.\.venv\Scripts\python.exe -m mcp_server
```

The endpoint is `http://127.0.0.1:8002/mcp`. A browser GET is not a chat page;
this is an MCP protocol endpoint. The client discovers tools at startup, so
restart the chat app after changing the server's tool definitions.

Server settings are in the separate Git-ignored `.env.mcp` file:

```dotenv
KUBECONFIG=~/.kube/k8s-admin.conf
MCP_HOST=127.0.0.1
MCP_PORT=8002
MCP_AUTH_TOKEN=your-shared-mcp-token
```

Matching random tokens have already been generated in your local `.env` and
`.env.mcp`. Keep these files private. Kubeconfig changes belong in `.env.mcp`.
The server reads `.env.mcp`; it does not load the chat app's `.env`.

Start the local chat page in a second terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --host 127.0.0.1
```

Open http://127.0.0.1:8000 and submit your question. FastAPI serves the page at
`GET /`. Use **New chat** to start a conversation and the **Saved chats** list
to reopen previous conversations. Messages survive page refreshes and app
restarts. The page remembers the selected chat in local storage; PostgreSQL
stores the actual messages and graph state. Follow-up questions in the same
conversation use previous messages. A new conversation starts separate state.
Messages previously displayed by the old page cannot be recovered retroactively.

API endpoints:

- `POST /conversations`: create a chat and return its ID.
- `GET /conversations`: list saved chats.
- `GET /conversations/{id}`: load its messages and interrupted-request status.
- `POST /chat`: send `{"conversation_id": "<id>", "message": "List all namespaces"}`;
  returns `{"conversation_id": "<id>", "answer": "..."}`.
- `POST /conversations/{id}/resume`: continue an interrupted graph run.

The page offers **Resume last request** when a graph run was interrupted.
Only one request per conversation runs at a time, including across browser tabs.
Edit `SYSTEM_MESSAGE` in `app.py` to adjust the chat assistant's instructions.
Credentials remain on the backend. This is a local, single-user application;
saved conversations are shared by anyone who can access its API.

To run MCP on another machine, copy `mcp_server/` and `requirements-mcp.txt`
there, install those dependencies, and supply the server machine's kubeconfig.
Set `MCP_HOST=0.0.0.0`, keep `MCP_AUTH_TOKEN` configured, and set
`MCP_ALLOWED_HOSTS` to the exact hostname/IP clients use (include `:*` for any
port), for example `mcp.internal.example:*,192.168.1.50:*`. Then set the chat
app's `MCP_SERVER_URL` to that machine's `/mcp` URL with the same token.
Use an HTTPS reverse proxy or a private encrypted network for cross-machine
connections. The server's network listener is independent of FastAPI.

An optional server-only Docker image is provided:

```powershell
docker build -f Dockerfile.mcp -t kube-autopilot-mcp .
```

Run it with the server environment and mount its kubeconfig directory:

```powershell
docker run --rm --name kube-autopilot-mcp -p 127.0.0.1:8002:8002 --env-file .env.mcp -e MCP_HOST=0.0.0.0 -e KUBECONFIG=/root/.kube/k8s-admin.conf --mount "type=bind,source=$env:USERPROFILE\.kube,target=/root/.kube,readonly" kube-autopilot-mcp
```

Run either the Python MCP process or the Docker MCP container on port 8002,
not both. The container must be able to reach the Kubernetes API; kubeconfig
certificate paths and credential helper commands must work inside Linux.
The Python process can use your existing Windows credential helpers directly.

You can also run the original command-line application:

```powershell
.\.venv\Scripts\python.exe main.py
```

Edit the `SystemMessage` content in `main.py` to choose what the application
does. It runs that instruction directly without prompting for input. For example:

```python
SystemMessage(
    content="List pods, deployments and services in namespace production"
)
```

Logs default to the last 100 lines per regular container. You can request a
specific container, line count, or previous container logs. Events are filtered
by the current pod's UID. Errors fetching a container's logs do not prevent
retrieving the pod's events. Your Kubernetes identity needs permission to read
the requested resources, pod logs, and events.

The model requests the tool, Python makes a read-only Kubernetes API request, and the
model presents the returned nodes. No cluster resources are changed.
