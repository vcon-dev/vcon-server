from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis
import logging
import elasticsearch
import json
import os


logger = init_logger(__name__)
# Disable Elastic Search API requests logs
logging.getLogger("elastic_transport.transport").setLevel(logging.WARNING)

default_options = {
    "name": "elasticsearch",
    "cloud_id": "",
    "api_key": "",
    "index": "vcon_index",
    "ca_certs": None,
    "url": None,
    "username": None,
    "password": None,
    "index_prefix": "",
}


def do_vcon_parts_indexing(
    *,
    es,
    part,
    index_name,
    id,
    common_attributes,
):
    new_part = {**part, **common_attributes}
    try:
        es.index(
            index=index_name,
            id=id,
            document=new_part,
        )
    except Exception as e:
        logger.error(f"Elasticsearch storage plugin: failed to insert: {new_part}, error: {e} ", exc_info=True)


def save(
    vcon_uuid,
    opts=default_options,
):
    try:
        if opts.get("cloud_id", None) or opts.get("api_key", None):
            es = elasticsearch.Elasticsearch(
                cloud_id=opts["cloud_id"],
                api_key=opts["api_key"],
            )
        else:
            url = opts["url"]
            username = opts["username"]
            password = opts["password"]
            ca_certs = opts.get("ca_certs", None)
            if ca_certs and os.path.exists(ca_certs):
                es = elasticsearch.Elasticsearch(url, basic_auth=(username, password), ca_certs=ca_certs)
            else:
                es = elasticsearch.Elasticsearch(url, basic_auth=(username, password), verify_certs=False)
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        vcon_dict = vcon.to_dict()

        if not vcon_dict["dialog"]:
            return

        started_at = vcon_dict["dialog"][0]["start"]

        common_attributes = {
            "vcon_id": vcon_uuid,
            "started_at": started_at,
        }

        tenant_attachment = vcon.find_attachment_by_type("tenant")
        if tenant_attachment:
            if tenant_attachment["encoding"] == "json" and isinstance(tenant_attachment["body"], str):
                tenant = json.loads(tenant_attachment["body"])
            else:
                tenant = tenant_attachment["body"]
            common_attributes["tenant_id"] = tenant["id"]

        index_prefix = opts.get("index_prefix", "")
        index_prefix = index_prefix.strip()

        # Index the parties, separated by 'role' - id=f"{vcon_uuid}_{party_index}"
        for ind, party in enumerate(vcon_dict["parties"]):
            role = party.get("role")
            do_vcon_parts_indexing(
                es=es,
                part=party,
                index_name=f"{index_prefix}vcon_parties_{role}" if role else f"{index_prefix}vcon_parties",
                id=f"{vcon_uuid}_{ind}",
                common_attributes=common_attributes,
            )

        # Index the attachments, separated by 'type' - id=f"{vcon_uuid}_{attachment_index}"
        for ind, attachment in enumerate(vcon_dict["attachments"]):
            attachment_type = attachment.get(
                "type"
            ).lower()  # TODO this might be "purpose" in some of the attachments!!
            encoding = attachment.get("encoding", "none")
            if encoding == "json" and isinstance(attachment["body"], str):  # Only parse if it's a string
                attachment["body"] = json.loads(attachment["body"])
            do_vcon_parts_indexing(
                es=es,
                part=attachment,
                index_name=f"{index_prefix}vcon_attachments_{attachment_type}",
                id=f"{vcon_dict['uuid']}_{ind}",
                common_attributes=common_attributes,
            )

        # Index the analysis, separated by 'type' - id=f"{vcon_uuid}_{analysis_index}"
        for ind, analysis in enumerate(vcon_dict["analysis"]):
            analysis_type = analysis.get("type")
            if analysis["encoding"] == "json" and isinstance(analysis["body"], str):  # Only parse if it's a string
                analysis["body"] = json.loads(analysis["body"])
            do_vcon_parts_indexing(
                es=es,
                part=analysis,
                index_name=f"{index_prefix}vcon_analysis_{analysis_type}",
                id=f"{vcon_dict['uuid']}_{ind}",
                common_attributes=common_attributes,
            )

        # Index the dialog - id=f"{vcon_uuid}_{dialog_index}"
        # TODO: Consider separate indexes for different dialog 'types'
        for ind, dialog in enumerate(vcon_dict["dialog"]):
            do_vcon_parts_indexing(
                es=es,
                part=dialog,
                index_name=f"{index_prefix}vcon_dialog",
                id=f"{vcon_dict['uuid']}_{ind}",
                common_attributes=common_attributes,
            )
    except Exception as e:
        logger.error(f"Elasticsearch storage plugin: failed to insert vCon: {vcon_uuid}, error: {e} ", exc_info=True)
        raise e


def delete(
    vcon_uuid,
    opts=default_options,
):
    """
    Delete a vCon from Elasticsearch storage by UUID.
    
    This function removes all documents related to the vCon from all indices:
    - Parties (by role)
    - Attachments (by type) 
    - Analysis (by type)
    - Dialog
    
    Args:
        vcon_uuid: UUID of the vCon to delete
        opts: Dictionary containing Elasticsearch connection parameters
        
    Returns:
        bool: True if the vCon was successfully deleted, False if it was not found
        
    Raises:
        Exception: If there's an error deleting the vCon
    """
    logger.info("Starting the Elasticsearch storage delete for vCon: %s", vcon_uuid)
    try:
        # Establish Elasticsearch connection
        if opts.get("cloud_id", None) or opts.get("api_key", None):
            es = elasticsearch.Elasticsearch(
                cloud_id=opts["cloud_id"],
                api_key=opts["api_key"],
            )
        else:
            url = opts["url"]
            username = opts["username"]
            password = opts["password"]
            ca_certs = opts.get("ca_certs", None)
            if ca_certs and os.path.exists(ca_certs):
                es = elasticsearch.Elasticsearch(url, basic_auth=(username, password), ca_certs=ca_certs)
            else:
                es = elasticsearch.Elasticsearch(url, basic_auth=(username, password), verify_certs=False)
        
        index_prefix = opts.get("index_prefix", "")
        index_prefix = index_prefix.strip()
        
        total_deleted = 0
        
        # Get all vCon-related indices with a single pattern
        try:
            all_indices = es.indices.get_alias(index=f"{index_prefix}vcon*")
            all_indices = list(all_indices.keys())
            logger.info(f"Found vCon indices: {all_indices}")
        except Exception as e:
            logger.warning(f"Failed to get vCon indices: {e}")
            all_indices = []
        
        # Delete from all collected indices using bulk delete_by_query
        if all_indices:
            logger.info(f"Deleting from {len(all_indices)} indices with vcon_id: {vcon_uuid}")
            response = es.delete_by_query(
                index=all_indices,
                query={
                    "match": {
                        "vcon_id": vcon_uuid
                    }
                },
                refresh=True
            )
            total_deleted = response.get("deleted", 0)
            logger.info(f"Successfully deleted {total_deleted} documents from all indices")
        
        if total_deleted > 0:
            logger.info(f"Successfully deleted {total_deleted} total documents for vCon: {vcon_uuid}")
            return True
        else:
            logger.info(f"No documents found for vCon: {vcon_uuid}")
            return False
            
    except Exception as e:
        logger.error(f"Elasticsearch storage plugin: failed to delete vCon: {vcon_uuid}, error: {e}", exc_info=True)
        raise e
