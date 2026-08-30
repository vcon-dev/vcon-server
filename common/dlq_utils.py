# Dead Letter Queue utils

def get_ingress_list_dlq_name(ingress_list: str) -> str:
    return f"DLQ:{ingress_list}"


def get_storage_dlq_name(storage_name: str) -> str:
    """DLQ for vCons whose write to a storage backend failed.

    Kept separate from the ingress DLQ because replaying one of these means
    re-attempting only the storage write. Replaying through the ingress list
    would re-run the whole chain, including transcription that already
    succeeded.
    """
    return f"DLQ:storage:{storage_name}"
