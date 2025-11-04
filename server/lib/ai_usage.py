from lib.logging_utils import init_logger
import requests
from datetime import datetime, timezone
from typing import Optional


logger = init_logger(__name__)


def send_ai_usage_data_for_tracking(
    vcon_uuid: str,
    input_units: int, 
    output_units: int, 
    unit_type: str,
    type: str,
    send_ai_usage_data_to_url: str,
    ai_usage_api_token: str,
    model: str,
    sub_type: Optional[str] = None,
):
    """Send AI usage data to portal endpoint for tracking"""
    data = {
        "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "record_id": vcon_uuid,
        "type": type,
        "sub_type": sub_type,
        "unit_type": unit_type,
        "input_units": input_units,
        "output_units": output_units,
        "ai_model": model,
    }
    if send_ai_usage_data_to_url:
        response = requests.post(
            send_ai_usage_data_to_url,
            json=data, 
            headers={"Authorization": f"Bearer {ai_usage_api_token}"}
        )
        if response.ok:
            logger.info(f"AI usage data sent to portal endpoint for tracking: {data}")
        else:
            logger.error(f"Failed to send AI usage data to portal endpoint for tracking: {response.status_code} {response.text}")
    else:
        logger.info(
            "AI usage data not sent to portal endpoint as "
            "send_ai_usage_data_to_url is not provided for tracking"
        )