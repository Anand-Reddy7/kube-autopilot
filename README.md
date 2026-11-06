# kube-autopilot

Call `gpt-5.6-luna` through LangChain to inspect Kubernetes resources using
read-only SDK tools: `list_nodes`, `list_pods`, `list_deployments`, `list_services`,
and `get_pod_logs_and_events`.

LangGraph manages execution in `graph.py`:
`START -> llm -> tools -> llm -> ... -> END`.
The shared `MessagesState` retains the instruction, model responses, and tool
results during each run. The graph ends when the model returns an answer
without tool calls, with a limit of 21 graph steps to bound repeated calls.
There is no saved state between runs.

Pods, deployments, services, and pod logs/events use namespace `default` when
no namespace is specified. Node listing is cluster-wide.

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
```

Edit the local `.env` file next to `main.py` and add your key:

```dotenv
OPENAI_API_KEY=your-openai-api-key
KUBECONFIG=~/.kube/k8s-admin.conf
```

The application loads this file on every run, including when launched from a
different directory. Values in `.env` override existing environment variables.
The `.env` file is excluded from Git by `.gitignore`.

Run the application:

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
