import os
import paramiko
import json
from typing import Optional

from lib.logging_utils import init_logger
from datetime import datetime
from server.lib.vcon_redis import VconRedis

logger = init_logger(__name__)


default_options = {
    "name": "sftp",
    "url": "sftp://localhost",
    "port": 22,
    "username": "username",
    "password": "password",
    "path": ".",
    "add_timestamp_to_filename": True,
    "filename": "vcon",
    "extension": "json",
}


def save(
    vcon_uuid,
    opts=default_options,
):
    logger.info("Saving vCon to sftp storage")
    transport = paramiko.Transport((opts["url"], opts["port"]))
    transport.connect(username=opts["username"], password=opts["password"])

    class SFTPClient(paramiko.SFTPClient):
        def __init__(self, *args, **kwargs):
            super(SFTPClient, self).__init__(*args, **kwargs)

        def putfo(self, fo, remotepath, callback=None, confirm=True):
            return self.putfo(fo, remotepath, callback, confirm)

    sftp = SFTPClient.from_transport(transport)
    # Upload the vCon to the SFTP site
    try:
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        filename = opts["filename"]
        if opts["add_timestamp_to_filename"]:
            filename += f"_{datetime.now().isoformat()}"
        filename += f".{opts['extension']}"
        sftp.putfo(vcon.dumps(), os.path.join(opts["path"], filename))
        logger.info(f"sftp storage plugin: uploaded vCon: {vcon_uuid} to {opts['url']}")
    except Exception as e:
        logger.error(
            f"sftp storage plugin: failed to upload vCon: {vcon_uuid}, error: {e} "
        )
        raise e
    finally:
        sftp.close()
        transport.close()

def get(vcon_uuid: str, opts=default_options) -> Optional[dict]:
    """Get a vCon from SFTP storage by UUID."""
    try:
        transport = paramiko.Transport((opts["url"], opts["port"]))
        transport.connect(username=opts["username"], password=opts["password"])
        sftp = paramiko.SFTPClient.from_transport(transport)

        try:
            # List files in the directory
            files = sftp.listdir(opts["path"])
            
            # Filter files matching our pattern
            base_name = opts["filename"]
            ext = opts["extension"]
            matching_files = [f for f in files if f.startswith(base_name) and f.endswith(f".{ext}")]
            
            if not matching_files:
                return None
                
            # Get the most recent file
            latest_file = max(matching_files)
            
            # Create a temporary file to store the content
            import tempfile
            with tempfile.NamedTemporaryFile() as temp_file:
                sftp.get(os.path.join(opts["path"], latest_file), temp_file.name)
                with open(temp_file.name, 'r') as f:
                    return json.loads(f.read())
                    
        finally:
            sftp.close()
            transport.close()
            
    except Exception as e:
        logger.error(f"sftp storage plugin: failed to get vCon: {vcon_uuid}, error: {e}")
        return None

