# mongo

Stores vCons in MongoDB.

## Configuration

```yaml
storages:
  mongo:
    module: storage.mongo
    options:
      url: mongodb://root:example@mongo:27017/
      database: conserver
      collection: vcons
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `url` | string | Required | MongoDB connection URL |
| `database` | string | `conserver` | Database name |
| `collection` | string | `vcons` | Collection name |

## Example

### Local MongoDB

```yaml
storages:
  mongo:
    module: storage.mongo
    options:
      url: mongodb://localhost:27017/
      database: vcon_server
      collection: vcons
```

### MongoDB Atlas

```yaml
storages:
  mongo_atlas:
    module: storage.mongo
    options:
      url: mongodb+srv://user:password@cluster.mongodb.net/
      database: production
      collection: vcons
```

### With Replica Set

```yaml
storages:
  mongo:
    module: storage.mongo
    options:
      url: mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0
      database: vcon_server
      collection: vcons
```

## Document Structure

```json
{
  "_id": "abc-123-def",
  "vcon": "0.0.1",
  "uuid": "abc-123-def",
  "created_at": "2024-01-15T10:30:00Z",
  "parties": [...],
  "dialog": [...],
  "analysis": [...],
  "_metadata": {
    "stored_at": "2024-01-15T10:31:00Z",
    "version": "1.0"
  }
}
```

## Queries

```javascript
// Find by UUID
db.vcons.findOne({ uuid: "abc-123-def" })

// Search by party
db.vcons.find({ "parties.tel": "+15551234567" })

// Recent vCons
db.vcons.find().sort({ created_at: -1 }).limit(10)

// Text search (requires index)
db.vcons.createIndex({ "analysis.body": "text" })
db.vcons.find({ $text: { $search: "billing issue" } })
```
