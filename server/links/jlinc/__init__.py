from lib.logging_utils import init_logger
from lib.vcon_redis import VconRedis
import requests
import json

logger = init_logger(__name__)

# Set the auth token
auth_token = None
# Rember to set the expiration time of the auth token
auth_token_expiration = None

default_options = {
    "event_type": "vcon_created",
    "userDid": {
        "id": "did:jlinc:fedid-test.jlinc.io:A7bUH0oJlp2dFe0AYkMDSXE2jgRtocTl6YEGOLly_UI",
        "version": "2.0",
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://didspec.jlinc.io/v2/ctx.jsonld"
        ],
        "verificationMethod": [
            {
                "id": "#db40a8ea3d8756aa62063521c3f71f43",
                "type": "device",
                "controller": "did:jlinc:fedid-test.jlinc.io:A7bUH0oJlp2dFe0AYkMDSXE2jgRtocTl6YEGOLly_UI",
                "key": "2aij8ScGJfhrSjD6RiXEtWuIMz1Yx6NFxRjFVoHw4qM",
                "created": "2025-02-17T13:33:53Z",
                "deactivated": None
            }
        ],
        "capabilityDelegation": [],
        "service": [
            {
                "id": "did:jlinc:fedid-test.jlinc.io:5c7ZbnC5DRS5ACYpBI2IJXaJVUsnSP5L5792GzNGFzo",
                "type": "login",
                "serviceEndpoint": "http://fedid-test.jlinc.io:8888"
            }
        ],
        "created": "2025-02-17T13:33:53Z",
        "updated": "2025-02-17T13:33:53Z",
        "deactivated": False,
        "shortName": "user-nzilrt7o@fedid-test.jlinc.io",
        "recoveryHash": "e2bcf75f75f8f616c75622b8e2ede08b47ee781665514988"
    },
    "userSigningKey": "8h2VF5b79hkpOjqOISCrc3Suk12Gwo02HHfDrA3yqC3Gm3zNXydH6vGw8dmRc_SHu0iWtNmfrdyl7cjWVDJr8QP",
    "auditServerUrls": ["http://jlinc-archive-server:8081"],
    "apiServerUrl": "http://jlinc-api-server:9090",
    "agreementId": '23b3768b-5cec-4e01-bd95-e02a334f0943',
    "recipientId": "did:jlinc:agent:23b3768b-5cec-4e01-bd95-e02a334f0943",
    "authorization": {
        "did-id": "did:jlinc:did.jlinc.io:MzA3ZDNiMTVlNDE5NDk1YjU0MzVmYmUyM",
        "api-key": "NjY0NTBiN2M1MWQwOTU3ZGJkZTYzMjI1N"
    }
}

def run(vcon_uuid, link_name, opts=default_options):
    """JLINC link that processes vCons through the JLINC API and sends them to the audit server.
    
    Args:
        vcon_uuid: UUID of the vCon to process
        link_name: Name of this link instance
        opts: Link options containing:
            userDid: The user's DID
            userSigningKey: The user's signing key
            apiServerUrl: JLINC API server URLs
            auditServerUrls: List of JLINC audit server URLs to try
            agreementId: The agreement ID to use for the vCon
            recipientDidId: The DID of the agent to use for the vCon

    Returns:
        True if the vCon was processed successfully
        False otherwise
    """
    logger.info(f"Running {link_name} link on vCon {vcon_uuid}")
    
    # Get vCon data from Redis
    vcon_redis = VconRedis()
    vcon_obj = vcon_redis.get_vcon(vcon_uuid)
    if not vcon_obj:
        logger.error(f"Could not get vCon {vcon_uuid} from Redis")
        return False

    vcon_dict = vcon_obj.to_dict()
    
    # Get the auth token from the JLINC API
    global auth_token, auth_token_expiration
    
    if auth_token is None:
        # Get the auth token from the JLINC API
        auth_url = f"{opts['apiServerUrl']}/api/v1/auth"
        response = requests.post(auth_url, headers={
            "did-id" : opts["authorization"]["did-id"],
            "api-key" : opts["authorization"]["api-key"]
        })
        if response.status_code == 200:
            auth_token = response.json()["token"]
        else:
            logger.warning(f"Failed to get auth token from JLINC API at {auth_url}. Status: {response}")
            raise Exception(f"Failed to get auth token from JLINC API at {auth_url}. Status: {response.status_code}")
    
    try:
        api_url = opts['apiServerUrl']
        audit_urls = opts['auditServerUrls']
        logger.info(f"Processing vCon {vcon_uuid} through JLINC API at {api_url}")
            
        request_data = {
            "type": "data",
            "senderId": opts["userDid"]["id"],
            "recipientId": opts["recipientId"],
            "agreementId": opts["agreementId"],
            "data":  {
                "event_type": opts["event_type"],
                "vcon_uuid": vcon_uuid,
                "vcon_hash": vcon_obj.hash,
                "created_at": vcon_obj.created_at
            }
        }
        
        response = requests.post(
            f"{api_url}/api/v1/event/create",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=request_data
        )
        
        if response.status_code == 200:
            processed_vcon = response.json()
            logger.info(f"Successfully processed vCon {vcon_uuid} through JLINC API at {api_url}")
            logger.info(f"Processed vCon: {processed_vcon}")
        else:
            logger.warning(f"Failed to process vCon {vcon_uuid} through JLINC API at {api_url}. Status: {response.status_code}")
            raise Exception(f"Failed to process vCon {vcon_uuid} through JLINC API at {api_url}. Status: {response.status_code}") 

        # Make the signing request, like the create event request
        request_data = {
            "event": processed_vcon,
            "didDoc": opts["userDid"],
            "signingKey": opts["userSigningKey"],
            "signingPublicKey": opts["userDid"]["verificationMethod"][0]["key"]
        }
        response = requests.post(
            f"{api_url}/api/v1/event/sign",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=request_data
        )

        if response.status_code == 200:
            logger.info(f"Successfully signed vCon {vcon_uuid} through JLINC API at {api_url}")
            signedEvent = response.json()
        else:
            logger.warning(f"Failed to sign vCon {vcon_uuid} through JLINC API at {api_url}. Status: {response.status_code}")
            raise Exception(f"Failed to sign vCon {vcon_uuid} through JLINC API at {api_url}. Status: {response.status_code}")

    
        # Send processed vCon to JLINC audit server
        try:            
            response = requests.post(
                f"{api_url}/api/v1/audit/create",
                headers={"Authorization": f"Bearer {auth_token}"},
                json=signedEvent
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully sent vCon {vcon_uuid} to JLINC api server at {api_url}")
                event_audit_record = response.json()
            else:
                logger.warning(f"Failed to send vCon {vcon_uuid} to JLINC api server at {api_url}. Status: {response.status_code}")

            request_data = {
                "audit": event_audit_record,
                "didDoc": opts["userDid"],
                "signingKey": opts["userSigningKey"],
                "signingPublicKey": opts["userDid"]["verificationMethod"][0]["key"]
            }
            
            # Make the signing request, like the create event request
            response = requests.post(
                f"{api_url}/api/v1/audit/sign",
                headers={"Authorization": f"Bearer {auth_token}"},
                json=request_data
            )

            if response.status_code == 200:
                logger.info(f"Successfully signed vCon {vcon_uuid} to JLINC api server at {api_url}")
                signed_audit_record = response.json()
            else:
                logger.warning(f"Failed to sign vCon {vcon_uuid} to JLINC api server at {api_url}. Status: {response.status_code}")
            
            for audit_url in audit_urls:
                try:
                    response = requests.post(
                        f"{audit_url}/api/v1/audit/put",
                        json=signed_audit_record
                    )
                    if response.status_code == 200:
                        logger.info(f"Successfully sent vCon {vcon_uuid} to JLINC audit server at {audit_url}")
                        event_audit_record = response.json()
                    else:
                        logger.warning(f"Failed to send vCon {vcon_uuid} to JLINC audit server at {audit_url}. Status: {response.status_code}")
                        continue
                except Exception as e:
                    logger.warning(f"Error connecting to JLINC audit server at {audit_url}: {e}")

        except Exception as e:
            logger.warning(f"Error connecting to JLINC api server at {api_url}: {e}")
        
        # Send the event audit record to the audit server
    except Exception as e:
        logger.warning(f"Error connecting to JLINC API at {api_url}: {e}")

    # Successfully processed and audited
    logger.info(f"Successfully completed JLINC processing for vCon {vcon_uuid}")
    return True 