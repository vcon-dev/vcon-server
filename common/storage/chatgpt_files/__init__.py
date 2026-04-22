from lib.logging_utils import init_logger
from lib.openai_client import get_openai_client
import json
import os
import redis_mgr

logger = init_logger(__name__)


default_options = {
    "organization_key": "org-xxxxx",
    "project_key": "proj_xxxxxxx",
    "api_key": "sk-proj-xxxxxx",
    "vector_store_id": "xxxxxx",
    "purpose": "assistants",
}


def save(vcon_uuid: str, options: dict = default_options) -> None:
    """Save a vCon to ChatGPT files.

    Args:
        vcon_uuid (str): The UUID of the vCon to be saved.
        options (dict, optional): Dictionary containing organization and project keys, API key,
        vector store ID, and purpose. Defaults to default_options.
    """
    try:
        vcon = redis_mgr.get_key(vcon_uuid)
        file_name = f"{vcon_uuid}.vcon.json"
        with open(file_name, "w") as file:
            json.dump(vcon, file)
        client = get_openai_client(options)
        with open(file_name, "rb") as upload_file:
            file = client.files.create(file=upload_file, purpose=options["purpose"])
        os.remove(file_name)
        client.beta.vector_stores.files.create(vector_store_id=options["vector_store_id"], file_id=file.id)
    except Exception as error:
        raise error
