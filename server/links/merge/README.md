# Merge Link

This link takes an inbound vCon, searches for another vCon with the same parties, and if found, merges the dialogs, attachments, and analysis from the inbound vCon into the found one. If no match is found, it returns the original vCon's UUID.

## Features

- Efficiently searches for vCons with matching parties using RedisJSON and RediSearch (if available)
- Merges dialogs, attachments, and analysis into the found vCon
- Supports options to replace (or append) attachments and analysis by type
- Returns the UUID of the merged-into vCon, or the original if no match
- Includes logging and error handling
- Ensures the RediSearch index is created only once, automatically on first use

## How It Works

1. **Index Creation**:  
   On first use, the link ensures a RediSearch index exists on the `vcon:*` keys, indexing the `parties` fields (tel, mailto, name). This enables fast searching by party attributes. The index is only created if it does not already exist.

2. **Searching for a Match**:  
   The link uses RediSearch to efficiently find candidate vCons with matching parties. It builds a query based on the inbound vCon's parties and searches the index for vCons with the same set of party attributes.

3. **Merging**:  
   If a match is found:
   - **Dialogs**: All dialogs from the inbound vCon are added to the found vCon.
   - **Attachments**: By default, attachments are appended. If `replace_attachments` is set, attachments of the same type are replaced.
   - **Analysis**: By default, analysis entries are appended. If `replace_analysis` is set, analysis of the same type is replaced.
   - The merged vCon is saved back to Redis, and its UUID is returned.

   If no match is found, the original vCon's UUID is returned.

## Configuration Options

The link can be configured with the following options:

```python
default_options = {
    "sampling_rate": 1,
    "replace_attachments": False,  # If True, replace attachments with matching type
    "replace_analysis": False,     # If True, replace analysis with matching type
}
```

### Options Description

- `sampling_rate`: Rate at which to sample vCons for merging (default: 1, i.e., always run)
- `replace_attachments`: If True, replace attachments of the same type instead of appending
- `replace_analysis`: If True, replace analysis of the same type instead of appending

## Output

- If a vCon with matching parties is found, merges the inbound vCon's dialogs, attachments, and analysis into it, and returns the found vCon's UUID
- If no match is found, returns the original vCon's UUID

## Requirements

- vCons must have a `parties` field (list of dicts)
- Redis must be accessible and contain vCons with keys matching `vcon:*`
- **RediSearch and RedisJSON modules must be enabled** in your Redis instance for efficient search (otherwise, fallback to scanning all vCons)
- The RediSearch index is created automatically if missing

## Example

```python
from server.links.merge import run

result_uuid = run(
    vcon_uuid="1234-5678-90ab-cdef",
    link_name="merge",
    opts={
        "replace_attachments": True,
        "replace_analysis": False,
    }
)
print("Resulting vCon UUID:", result_uuid)
```

## Notes

- The merge link is designed to be idempotent and safe to call multiple times.
- The RediSearch index creation is handled automatically and only runs if the index does not exist.
- If RediSearch is not available, the link will fall back to scanning all vCons, which may be slower for large datasets. 