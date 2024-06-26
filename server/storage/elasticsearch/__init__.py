from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis
import logging
from elasticsearch import Elasticsearch
import json


logger = init_logger(__name__)
# Disable Elastic Search API requests logs
logging.getLogger("elastic_transport.transport").setLevel(logging.WARNING)

default_options = {
    "name": "elasticsearch",
    "cloud_id": "",
    "api_key": "",
    "index": "vcon_index",
}


def do_vcon_parts_indexing(*, es, part, index_name, id, common_attributes,):
    new_part = {**part, **common_attributes}
    try:
        es.index(
            index=index_name,
            id=id,
            document=new_part,
        )
    except Exception as e:
        logger.error(
            f"Elasticsearch storage plugin: failed to insert: {new_part}, error: {e} ", exc_info=True
        )


def save(
    vcon_uuid,
    opts=default_options,
):
    try:
        es = Elasticsearch(
            cloud_id=opts["cloud_id"],
            api_key=opts["api_key"],
        )
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        vcon_dict = vcon.to_dict()

        started_at = vcon_dict["dialog"][0]["start"]
        
        common_attributes = {
            "vcon_id": vcon_uuid,
            "started_at": started_at,
        }

        tenant_attachment = vcon.find_attachment_by_type("tenant")
        if tenant_attachment:
            tenant = json.loads(tenant_attachment["body"])
            common_attributes["tenant_id"] = tenant["id"]

        # Index the parties, separated by 'role' - id=f"{vcon_uuid}_{party_index}"
        for ind, party in enumerate(vcon_dict["parties"]):
            role = party.get("meta", {}).get("role")
            do_vcon_parts_indexing(
                es=es,
                part=party, 
                index_name=f"vcon_parties_{role}" if role else "vcon_parties", 
                id=f"{vcon_uuid}_{ind}", 
                common_attributes=common_attributes
            )

        # Index the attachments, separated by 'type' - id=f"{vcon_uuid}_{attachment_index}"
        for ind, attachment in enumerate(vcon_dict["attachments"]):
            type = attachment.get("type")  # TODO this might be "purpose" in some of the attachments!!
            if attachment["encoding"] == "json":  # TODO may be we need handle different encodings
                attachment["body"] = json.loads(attachment["body"])
            do_vcon_parts_indexing(
                es=es,
                part=attachment, 
                index_name=f"vcon_attachments_{type}", 
                id=f"{vcon_dict['uuid']}_{ind}", 
                common_attributes=common_attributes
            )

        # Index the analysis, separated by 'type' - id=f"{vcon_uuid}_{analysis_index}"
        for ind, analysis in enumerate(vcon_dict["analysis"]):
            type = analysis.get("type")
            if analysis["encoding"] == "json":  # TODO may be we need handle different encodings
                if isinstance(analysis["body"], str):
                    analysis["body"] = json.loads(analysis["body"])
            do_vcon_parts_indexing(
                es=es,
                part=analysis, 
                index_name=f"vcon_analysis_{type}", 
                id=f"{vcon_dict['uuid']}_{ind}", 
                common_attributes=common_attributes
            )

        # Index the dialog - id=f"{vcon_uuid}_{dialog_index}"
        # TODO: Consider separate indexes for different dialog 'types'
        for ind, dialog in enumerate(vcon_dict["dialog"]):
            do_vcon_parts_indexing(
                es=es,
                part=dialog, 
                index_name="vcon_dialog", 
                id=f"{vcon_dict['uuid']}_{ind}", 
                common_attributes=common_attributes
            )
    except Exception as e:
        logger.error(
            f"Elasticsearch storage plugin: failed to insert vCon: {vcon_uuid}, error: {e} ", exc_info=True
        )