# scitt

Registers a signed statement of the vCon's hash on a SCRAPI-compatible SCITT transparency service, and stores the verified receipt.

Module: `links.scitt`

Imports `fastapi`, which the `conserver` dependency group does not include. The link fails to import in the `docker/Dockerfile.conserver` image, and each vCon then goes to the dead letter queue. It imports in the `docker/Dockerfile` image.

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `scrapi_url` | string | `http://scittles:8000` | Base URL of the transparency service |
| `signing_key_pem` | string | `None` | Base64-encoded P-256 PEM key. Used first when set |
| `signing_key_path` | string | `/etc/scitt/signing-key.pem` | Path to a P-256 PEM key |
| `issuer` | string | `conserver` | Issuer of the statement |
| `key_id` | string | `conserver-key-1` | Key ID in the statement |
| `vcon_operation` | string | `vcon_created` | Lifecycle event, such as `vcon_created` or `vcon_enhanced` |
| `store_receipt` | bool | `true` | Adds the receipts to the vCon |

## Follow the processing steps

1. Load the vCon and its SHA-256 hash, then load the signing key.
2. Collect the `tel` of each party. With none, use a single statement for the vCon.
3. For each entry, build a COSE Sign1 statement.

    | Case | Subject | Signed payload |
    |---|---|---|
    | Party with `tel` | `tel:<tel>` | `<hash>:<operation>:<tel>` |
    | No party has `tel` | `vcon://<uuid>` | `<hash>:<operation>` |

4. Register the statement at `<scrapi_url>/entries`, polling if the service replies 303.
5. Verify the receipt: recompute the Merkle root from its inclusion proof, fetch the service's public key from its JWKS, and check the signature.
6. If `store_receipt` is true, add the analysis and save the vCon.

To record two points in a chain, add this link twice with different `vcon_operation` values. The second hash covers the first receipt, since the receipt is part of the vCon.

## Read the return value

Returns the uuid. A missing vCon raises `HTTPException` with status 404. A failure to sign, register or verify raises. In each case the vCon goes to the dead letter queue.

## Inspect the vCon changes

One analysis entry when `store_receipt` is true. Otherwise none.

| Field | Value |
|---|---|
| `type` | `scitt_receipt` |
| `dialog` | `0` |
| `vendor` | `scittles` |
| `body` | One receipt object, or a list when there are several |
| `encoding` | `json` |

Each receipt has `entry_id`, `cose_receipt` in Base64, `vcon_operation`, `subject`, `vcon_hash` and `scrapi_url`. The `subject` can hold a party's phone number.

## Copy a configuration example

```yaml
links:
  scitt_created:
    module: links.scitt
    options:
      scrapi_url: http://scittles:8000
      signing_key_path: /etc/scitt/signing-key.pem
      issuer: conserver
      key_id: conserver-key-1
      vcon_operation: vcon_created
```

## Track the metrics

`conserver.link.scitt.statement_creation_failures` and `conserver.link.scitt.registration_failures`. See [Metrics](../metrics.md).
