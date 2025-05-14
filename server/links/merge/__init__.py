import logging
from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
import os
from redis.commands.search.field import TagField, TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis_mgr import redis
from redis.commands.search.query import Query
from server.redis_mgr import show_keys

logger = init_logger(__name__)

default_options = {
    "sampling_rate": 1,
    "replace_attachments": False,  # If True, replace attachments with matching type
    "replace_analysis": False,     # If True, replace analysis with matching type
}

def parties_match(parties1, parties2):
    """Return True if two parties lists are equivalent (order-insensitive, shallow compare)."""
    if len(parties1) != len(parties2):
        return False
    # Convert to sorted list of tuples for comparison
    def party_key(p):
        return tuple(sorted(p.items()))
    return sorted([party_key(p) for p in parties1]) == sorted([party_key(p) for p in parties2])

def ensure_vcon_index():
    """
    Ensure the RediSearch index for vCon JSON documents exists.
    This should be called once before any search.
    """
    from redis_mgr import redis
    from redis.commands.search.field import TagField
    from redis.commands.search.indexDefinition import IndexDefinition, IndexType

    try:
        # Try to get info; if it fails, the index doesn't exist
        redis.ft("vcon_idx").info()
    except Exception:
        schema = (
            TagField("$.parties[*].tel", as_name="party_tel"),
            TagField("$.parties[*].mailto", as_name="party_mailto"),
            TagField("$.parties[*].name", as_name="party_name"),
        )
        definition = IndexDefinition(prefix=["vcon:"], index_type=IndexType.JSON)
        try:
            redis.ft("vcon_idx").create_index(schema, definition=definition)
        except Exception as e:
            logger.warning(f"Could not create vCon RediSearch index: {e}")

def run(
    vcon_uuid,
    link_name,
    opts=default_options,
):
    # Ensure the RediSearch index exists before searching
    ensure_vcon_index()
    module_name = __name__.split(".")[-1]
    logger.info(f"Starting {module_name}: {link_name} plugin for: {vcon_uuid}")
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    vcon_redis = VconRedis()
    inbound_vcon = vcon_redis.get_vcon(vcon_uuid)
    if not inbound_vcon:
        logger.error(f"No vCon found for uuid: {vcon_uuid}")
        return vcon_uuid

    # Use RediSearch to find a matching vCon
    for match_uuid in find_matching_vcon_by_parties(redis, inbound_vcon):
        candidate = vcon_redis.get_vcon(match_uuid)
        if candidate and parties_match(inbound_vcon.parties, candidate.parties):
            found_vcon = candidate
            break
    else:
        found_vcon = None

    if found_vcon:
        logger.info(f"Found vCon with matching parties: {found_vcon.uuid}")
        # Merge dialogs
        for dialog in inbound_vcon.dialog:
            found_vcon.add_dialog(dialog)
        # Merge or replace attachments
        if opts.get("replace_attachments"):
            inbound_types = {a["type"] for a in inbound_vcon.attachments}
            found_vcon.vcon_dict["attachments"] = [a for a in found_vcon.attachments if a["type"] not in inbound_types]
            for attachment in inbound_vcon.attachments:
                found_vcon.add_attachment(**attachment)
        else:
            for attachment in inbound_vcon.attachments:
                found_vcon.add_attachment(**attachment)
        # Merge or replace analysis
        if opts.get("replace_analysis"):
            inbound_types = {a["type"] for a in inbound_vcon.analysis}
            found_vcon.vcon_dict["analysis"] = [a for a in found_vcon.analysis if a["type"] not in inbound_types]
            for analysis in inbound_vcon.analysis:
                found_vcon.add_analysis(**analysis)
        else:
            for analysis in inbound_vcon.analysis:
                found_vcon.add_analysis(**analysis)
        vcon_redis.store_vcon(found_vcon)
        logger.info(f"Merged vCon {vcon_uuid} into {found_vcon.uuid}")
        return found_vcon.uuid
    else:
        logger.info(f"No matching vCon found for parties in {vcon_uuid}")
        return vcon_uuid 

def create_vcon_index():
    # Index the parties as a tag field for set-based search
    schema = (
        TagField("$.parties[*].tel", as_name="party_tel"),
        TagField("$.parties[*].mailto", as_name="party_mailto"),
        TagField("$.parties[*].name", as_name="party_name"),
    )
    definition = IndexDefinition(prefix=["vcon:"], index_type=IndexType.JSON)
    try:
        redis.ft("vcon_idx").create_index(schema, definition=definition)
    except Exception as e:
        # Index may already exist
        print(f"Index creation error (may be ok): {e}")

def find_matching_vcon_by_parties(redis, inbound_vcon):
    # Build a query for all party fields
    party_queries = []
    for party in inbound_vcon.parties:
        subqueries = []
        if "tel" in party:
            subqueries.append(f"@party_tel:{{{party['tel']}}}")
        if "mailto" in party:
            subqueries.append(f"@party_mailto:{{{party['mailto']}}}")
        if "name" in party:
            subqueries.append(f"@party_name:{{{party['name']}}}")
        if subqueries:
            party_queries.append("(" + " ".join(subqueries) + ")")
    # Require all parties to match (AND)
    query_str = " ".join(party_queries)
    query = Query(query_str)
    results = redis.ft("vcon_idx").search(query)
    # Exclude the inbound vcon itself
    for doc in results.docs:
        if doc.id != f"vcon:{inbound_vcon.uuid}":
            yield doc.id.split(":", 1)[1] 