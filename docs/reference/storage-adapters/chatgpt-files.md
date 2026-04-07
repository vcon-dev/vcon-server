# chatgpt-files

Uploads vCons to the OpenAI Files API and optionally adds them to an OpenAI vector store, making them available for use with Assistants and ChatGPT Retrieval.

## Prerequisites

- An OpenAI account with API access
- A vector store created in the OpenAI platform (if using vector store integration)
- The `openai` Python package

```
pip install openai
```

## Configuration

```yaml
storages:
  chatgpt_files:
    module: storage.chatgpt_files
    options:
      organization_key: ${OPENAI_ORG_ID}
      project_key: ${OPENAI_PROJECT_ID}
      api_key: ${OPENAI_API_KEY}
      vector_store_id: ${OPENAI_VECTOR_STORE_ID}
      purpose: assistants
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `organization_key` | string | Required | OpenAI organization ID (e.g. `org-xxxxx`) |
| `project_key` | string | Required | OpenAI project ID (e.g. `proj_xxxxxxx`) |
| `api_key` | string | Required | OpenAI API key (e.g. `sk-proj-xxxxxx`) |
| `vector_store_id` | string | Required | ID of the OpenAI vector store to attach uploaded files to |
| `purpose` | string | `assistants` | Purpose for the uploaded file. Must be a value accepted by the OpenAI Files API (e.g. `assistants`) |

## Example

```yaml
storages:
  chatgpt_files:
    module: storage.chatgpt_files
    options:
      organization_key: ${OPENAI_ORG_ID}
      project_key: ${OPENAI_PROJECT_ID}
      api_key: ${OPENAI_API_KEY}
      vector_store_id: ${OPENAI_VECTOR_STORE_ID}
      purpose: assistants

chains:
  main:
    links:
      - transcribe
      - summarize
    storages:
      - chatgpt_files
    ingress_lists:
      - default
    enabled: 1
```

## File Naming

Each vCon is written to a temporary local file named `{uuid}.vcon.json`, uploaded to the OpenAI Files API, and then the local file is deleted. The uploaded file is attached to the configured vector store.

```
{vcon_uuid}.vcon.json  →  uploaded to OpenAI Files API  →  added to vector store
```

## Notes

- A temporary local file is created during the upload and removed immediately after a successful transfer.
- After uploading, the file is registered with the vector store identified by `vector_store_id`, enabling semantic search via OpenAI Assistants.
- File size limits and rate limits are governed by your OpenAI account tier.
- Store the `api_key` and other credentials in environment variables — never commit them to source control.
