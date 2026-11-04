# ChatGPT files storage adapter

Uploads a vCon as a JSON file to OpenAI and attaches it to a vector store.

!!! warning "This adapter does not work as written"
    With the locked dependencies, `save` cannot finish. See [Check the known problems](#check-the-known-problems).

Module: `storage.chatgpt_files`. Needs the `openai` package, from the `conserver` dependency group.

## Configure the adapter

```yaml
storages:
  chatgpt:
    module: storage.chatgpt_files
    options:
      api_key: sk-example
      organization_key: org-example
      project_key: proj_example
      vector_store_id: vs_example
      purpose: assistants
```

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `organization_key` | string | `org-xxxxx` | OpenAI organization. Optional for the client |
| `project_key` | string | `proj_xxxxxxx` | OpenAI project. Optional for the client |
| `api_key` | string | `sk-proj-xxxxxx` | OpenAI API key |
| `vector_store_id` | string | `xxxxxx` | Vector store that receives the file. Required in practice |
| `purpose` | string | `assistants` | Purpose sent with the file upload. Required in practice |

The defaults are placeholders. The adapter builds its client with `get_openai_client` in `common/lib/openai_client.py`, so that function's other keys work here too: `LITELLM_PROXY_URL` with `LITELLM_MASTER_KEY`, `AZURE_OPENAI_ENDPOINT` with `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_API_VERSION`, `OPENAI_API_KEY` or `openai_api_key` in place of `api_key`, and `organization` or `project`.

## Save a vCon

1. Read the key `<uuid>` from Redis with `redis_mgr.get_key`.
2. Write the value to `<uuid>.vcon.json` in the process working directory.
3. Upload the file with `client.files.create`.
4. Delete the local file.
5. Add the uploaded file to the vector store.

## Read or delete a vCon

The adapter has no `get` and no `delete`. A file stays in OpenAI after `DELETE /vcon/{uuid}`.

## Handle a failed write

Any exception is re-raised, so the server moves the vCon to the [storage DLQ](index.md#handle-a-failed-write). The client runs with `max_retries=0`. A replay after step 3 uploads a second file. A failed upload leaves the local file in the working directory, because the delete in step 4 does not run.

## Check the known problems

- The adapter reads the Redis key `<uuid>`, and the server stores vCons under `vcon:<uuid>`. The read finds nothing, so the file holds `null`.
- Step 5 calls `client.beta.vector_stores`. `uv.lock` pins `openai` 2.24.0, where that attribute does not exist and the vector store API sits at `client.vector_stores`. The call raises `AttributeError` after the file has been uploaded.
- The only test, in `common/storage/chatgpt_files/test_init.py`, is marked skip.
