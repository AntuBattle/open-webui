# CMSAI local deployment

Linux Docker Compose setup for this OpenWebUI checkout and the CERN remote Qwen service. LiteLLM is not part of this initial trial.

## Start

Requirements: running Docker Engine, Docker Compose, and access to the CERN remote LLM endpoint. Run the commands below from `deploy/cmsai` within this repository.

The build script follows OpenWebUI’s Docker CI procedure: it generates an ignored build-only Dockerfile with `NODE_OPTIONS=--max-old-space-size=12288`. The source checkout stays unchanged. Regenerate it with the script whenever rebuilding.

The local `.env` contains a generated `WEBUI_SECRET_KEY` and is ignored by Git. On another machine, create it once using:

```sh
(umask 077; python3 -c 'import secrets; print("WEBUI_SECRET_KEY=" + secrets.token_urlsafe(48))' > .env)
```

Add `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `REMOTE_LLM_API_KEY`, and `CERN_ML_SESSION_COOKIE` to `.env` before starting. For this trial the OIDC client is Archi’s `cms-a2rchi`; its credentials were copied from the existing local Archi configuration. The endpoint and default model are declared in Compose; no frontend provider configuration is required.

Do not run that command over an existing `.env`: changing the key can invalidate sessions and make saved OAuth credentials unreadable. Back it up separately from Git.

```sh
docker compose config --quiet
bash scripts/build.sh
docker compose up -d
docker compose ps
```

Open http://127.0.0.1:3000. The OpenWebUI login page shows a CERN sign-in button; automatic SSO redirect is disabled. Password login, local signup, LDAP and OpenWebUI API keys are disabled. Other OpenWebUI SSO providers are not configured. CERN itself controls the methods shown on its sign-in page. Existing browser sessions are not automatically revoked by these settings.

CERN sign-in links an existing account with the same email, preserving its role and chats. New CERN identities use OpenWebUI’s default pending role; on an empty database, the first account becomes administrator. The configured default model is `hf-qwen38-27b`. Existing chats may retain their previous model selection.

Host networking is retained for this local trial; the Ollama integration is disabled. The application itself binds only to `127.0.0.1:3000`. This is a Linux-local setup, not a Kubernetes networking template.

## Configuration and data

Edit `compose.yaml` for durable global settings. `ENABLE_PERSISTENT_CONFIG=False` means UI edits to global configuration are temporary and revert at application restart. Personal account settings, accounts, passwords, assigned roles, conversations and workspace records remain in the database.

The named volume `cmsai_open-webui-data` retains `/app/backend/data`, including the default SQLite database. `docker compose down` retains the volume; `docker compose down -v` deletes it. Preserve both the data volume and `.env` across redeployments.

After changing environment settings, run `docker compose up -d` to recreate the service. A plain `docker compose restart` does not load changed Compose environment values.

```sh
docker compose logs --tail=100 open-webui
docker compose restart open-webui
docker compose down
```

## Local CERN callback

`scripts/oauth-callback.py` runs as the `oauth-callback` Compose service, using the existing image and Python standard library. It binds only to `127.0.0.1:7869` and redirects `/redirect` to `http://127.0.0.1:3000/oauth/oidc/login/callback`, preserving the query string. Other paths return 404. It neither exchanges tokens nor logs callback queries.

`OPENID_REDIRECT_URI=http://127.0.0.1:7869/redirect` makes OpenWebUI use the same registered address for authorization and token exchange. CERN accepts this callback for Archi’s client. OpenWebUI retains responsibility for state validation and token exchange. Open **http://127.0.0.1:3000** manually; automatic hostname redirection is intentionally not implemented. Use **127.0.0.1 throughout**, not localhost: cookies cross ports on the same hostname but do not cross these two hostnames. Archi cannot use port 7869 while this helper is running.

This is a local workaround. A future CMSAI OIDC registration can point directly to the deployed OpenWebUI callback, removing the helper.

## Temporary authentication workarounds

These local workarounds belong to this configuration repository; they are not changes to OpenWebUI source and are not the future ArgoCD authentication design.

- OpenWebUI login reuses Archi’s CERN client and the small callback service on port 7869. A dedicated CMSAI registration will let us remove that service.
- Remote model requests use a manually copied CERN ML session cookie plus the LiteLLM virtual key. `CERN_ML_SESSION_COOKIE` and `REMOTE_LLM_API_KEY` are stored only in the ignored `.env`. All users of this backend share the configured ML session identity and virtual key for model requests; this is not per-user model authentication.

The Qwen API base is `https://ml.cern.ch/serving/genai/kops-llm-serving-ml-prod-qwen-v38-27b/openai/v1`; its model ID is `hf-qwen38-27b`. Compose uses `auth_type: bearer` for the virtual key and a custom `Cookie` header for `authservice_session`. The OpenWebUI login token is not forwarded to the model. TLS verification stays enabled.

Set `CERN_ML_SESSION_COOKIE` to the complete cookie pair `authservice_session=<cookie value>` (no `Cookie:` prefix). Quote it in `.env` using single quotes.

Logging into ML in your own browser does **not** automatically update the backend cookie. When it expires, sign into ML, renew `CERN_ML_SESSION_COOKIE` privately in `.env`, then recreate the app with both Compose files:

```sh
docker compose -f compose.yaml -f compose.unified.yaml up -d open-webui
```

Do not print resolved Compose configuration or connection headers: they contain credentials. No automatic cookie capture or renewal service is installed. Keep the virtual key and cookie out of Git. The model ID is explicitly configured, so its presence in the selector alone is not proof of API access.

## Unified MCP

The public CERN root and issuing CA certificates in `certificates/` are mounted read-only. At startup, `update-ca-certificates` merges them with the image’s standard trust store before OpenWebUI starts. `AIOHTTP_CLIENT_SSL_CERT_FILE`, `SSL_CERT_FILE`, and `REQUESTS_CA_BUNDLE` select that combined bundle across the HTTP clients used for discovery, OAuth redirects/token exchange, and MCP. TLS verification stays enabled. These public certificates were copied from this machine’s installed CERN trust anchors; replace them when CERN rotates the CA.

The authenticated endpoint `https://cmspnr-api.cern.ch/mcp/sse` accepts HTTP POST initialization with a JSON response despite its `/sse` name. It advertises OAuth discovery and dynamic client registration. OpenWebUI registers its own OAuth client; Codex tokens are not copied into this deployment.

After the base service is running, register once and enable the connection:

```sh
python3 scripts/register-unified.py
docker compose -f compose.yaml -f compose.unified.yaml up -d
```

Registration uses the running checkout's own OAuth implementation. The encrypted client metadata is saved in the ignored `.env`, alongside the stable encryption key. The server definition lives in `compose.unified.yaml`. Keep using both Compose files for subsequent `up` commands, or the Unified connection will be removed from the service environment. Running the registration script again refuses to create a duplicate client.

Sign in to OpenWebUI, enable Unified through the chat's Integrations menu, and complete the CERN authorization in the same browser. Do not set OAuth tools as default model tools: user authorization must happen before a completion request. Registration alone does not prove user authorization or tool execution works.

With `ENABLE_PERSISTENT_CONFIG=False`, changes to the registered client through the UI are temporary. If Unified invalidates its client registration, durable re-registration must also update `.env`; an in-memory repair alone will not survive restart.

## Active integration: remote cluster ToolHive

`compose.toolhive.yaml` points OpenWebUI to **Cluster Tools (ToolHive)** at
`https://cms-compops-mcp-testbed.cern.ch/mcp`, using OAuth 2.1 and integration ID
`cluster-tools`. This replaces the local Geneva/Unified gateway connection.
The cluster configuration aggregates DBS, Jira, OpenSearch, Git and Rucio;
CERN application `mcp-gateway-test` roles determine the tools each user receives.
The `default-role` alone permits no tools. Unified and Geneva are not included.

Keep all three Compose files so the last override selects the remote gateway:

```sh
python scripts/register-toolhive.py
docker compose -f compose.yaml -f compose.unified.yaml -f compose.toolhive.yaml config --quiet
docker compose -f compose.yaml -f compose.unified.yaml -f compose.toolhive.yaml up -d --no-deps open-webui
```

Registration uses the running OpenWebUI's existing encryption key and writes new
remote OAuth client metadata to `TOOLHIVE_OAUTH_CLIENT_INFO` in private `.env`.
The callback is `http://127.0.0.1:3000/oauth/clients/mcp:cluster-tools/callback`.
The registration script requires OpenWebUI to be running. Repeat registration
and recreate OpenWebUI if the remote gateway loses its client registrations.
Do not reuse encrypted client metadata from the previous local gateway.

Open http://127.0.0.1:3000 in your signed-in browser. In the chat Integrations →
Tools menu, authorize **Cluster Tools (ToolHive)**. The direct authorization
entry is `http://127.0.0.1:3000/oauth/clients/mcp:cluster-tools/authorize`.
Complete the gateway's CERN authorization, then select the integration in your
chat. Your existing CERN browser session may avoid another password prompt.
OpenWebUI login and tool authorization remain separate sessions.

OpenWebUI data, CERN sign-in and the shared Qwen model configuration are retained.
The existing manually renewed CERN ML cookie can still expire independently.
Global admin configuration remains temporary (`ENABLE_PERSISTENT_CONFIG=False`).

The local mock-weather and ToolHive service definitions, and their YAML configs,
remain available for the earlier trial, but OpenWebUI no longer depends on or
connects to them. `toolhive/verify.py` checks that earlier local trial; it does
not verify the remote cluster gateway. `compose.unified.yaml` retains the
alternative direct Unified connection when used without the ToolHive override.

## Future ArgoCD deployment

This repository will own deployment settings. User data stays in persistent storage and secrets are supplied separately. Kubernetes manifests, secret management, database deployment and MCP authentication provisioning remain future decisions. The existing `.github/workflows/docker.yaml` builds this checkout and publishes images to `ghcr.io/antubattle/open-webui`. Deploy an exact image digest after its build succeeds. The local `cmsai/open-webui:local` tag is only for Compose.

## Repository and image boundaries

The public deployment configuration lives in `deploy/cmsai`. Keep real credentials
in its ignored `.env` locally, or supply them through Kubernetes Secrets in the
cluster. Never commit the `.env`, encrypted OAuth registration metadata, logs,
screenshots or user databases. The entire deployment directory is excluded from
the Docker build context; Compose settings configure the running container and
are not embedded in the published application image. CERN certificates are public
trust anchors and remain mounted by the local Compose setup.

Moving these files preserves the Compose project name `cmsai` and its named data
volume. Existing containers are not recreated by the move. Run future build,
registration and Compose commands from this directory.
