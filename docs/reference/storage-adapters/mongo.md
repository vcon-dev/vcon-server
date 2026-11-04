# MongoDB storage adapter

Stores each vCon as one document in a MongoDB collection, keyed by UUID.

Module: `storage.mongo`. Needs `pymongo`, from the `storage` dependency group.

## Configure the adapter

```yaml
storages:
  mongo:
    module: storage.mongo
    options:
      url: mongodb://root:example@mongo:27017/
      database: conserver
      collection: vcons
```

Any URL that `pymongo.MongoClient` accepts works, including `mongodb+srv://` and replica set URLs.

## Set the options

The adapter reads `url`, `database` and `collection` directly, so all three are required in an `options` block.

| Option | Type | Default | Description |
|---|---|---|---|
| `name` | string | `mongo` | Not read by the adapter |
| `url` | string | `mongodb://localhost:27017/` | Connection URL. A missing key raises `ValueError` |
| `database` | string | `conserver` | Database name |
| `collection` | string | `vcons` | Collection name |

The adapter logs the whole options dictionary at INFO on each `save`, and the URL at DEBUG. A password in `url` reaches the logs.

## Save a vCon

`save` reads the vCon through `VconRedis`, then runs `update_one` with `$set` and `upsert=True` on `_id`, which holds the UUID.

The stored document is the vCon with these changes:

- `_id` is added.
- Top-level `created_at` becomes a BSON date.
- `start` on each dialog becomes a BSON date.

Attachment and analysis bodies stay as they are. The adapter does not apply `EGRESS_FORMAT_VERSION`.

`$set` writes the keys in the new document and leaves others alone, so a top-level key removed from the vCon stays in MongoDB.

## Read a vCon

`get` calls `fetch`, turns dates back into ISO strings, and returns the vCon dictionary. The result still contains `_id`. It returns `None` when the document is missing or on any error.

The module also has `fetch` and `exists`, which raise on errors. `Storage` does not call them directly.

## Delete a vCon

The adapter has no `delete`. A document stays in MongoDB after `DELETE /vcon/{uuid}`.

## Handle a failed write

Any exception raises, so the server moves the vCon to the [storage DLQ](index.md#handle-a-failed-write). That covers a vCon missing from Redis, a missing `created_at`, a dialog with no `start`, and a date that will not parse. The adapter sets no retry of its own.

A repeated `save` is safe, because it upserts on `_id`.

## Query the collection

```javascript
// Find by UUID
db.vcons.findOne({ _id: "018f4a2e-7b1c-8000-9000-000000000001" })

// Search by party
db.vcons.find({ "parties.tel": "+15555550100" })

// Recent vCons
db.vcons.find().sort({ created_at: -1 }).limit(10)
```
