from lib.logging_utils import init_logger
import json
import os
import redis_mgr
from openai import OpenAI

logger = init_logger(__name__)


default_options = {
    "organization_key": "org-xxxxx",
    "project_key": "proj_xxxxxxx",
    "api_key": "",
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
        client = OpenAI(
            organization=options["organization_key"],
            project=options["project_key"],
            api_key=options["api_key"],
        )
        file = client.files.create(file=open(file_name, "rb"), purpose=options["purpose"])
        os.remove(file_name)
        client.beta.vector_stores.files.create(vector_store_id=options["vector_store_id"], file_id=file.id)
    except Exception as error:
        raise error
