from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis
from playhouse.postgres_ext import PostgresqlExtDatabase, BinaryJSONField
from peewee import (
    Model,
    DateTimeField,
    TextField,
    UUIDField,
)
from datetime import datetime

logger = init_logger(__name__)
default_options = {"name": "postgres"}


def create_vcons_class(opts):
    # Initialize the database connection
    db = PostgresqlExtDatabase(
        opts["database"],
        user=opts["user"],
        password=opts["password"],
        host=opts["host"],
        port=opts["port"],
    )
    
    # Define the Meta class with the database
    class Meta:
        database = db

    # Use the type function to dynamically create the Vcons class
    Vcons = type(
        'Vcons',  # The class name
        (Model,),  # The base class (Model in this case)
        {
            'id': UUIDField(primary_key=True),
            'vcon': TextField(),
            'uuid': UUIDField(),
            'created_at': DateTimeField(),
            'updated_at': DateTimeField(null=True),
            'subject': TextField(null=True),
            'vcon_json': BinaryJSONField(null=True),
            'created_by_local_type': TextField(),
            'created_by_domain': TextField(),
            'created_by_local_type_version': TextField(),
            'Meta': Meta,  # Include the Meta class
        }
    )

    db.create_tables([Vcons], safe=True)

    return Vcons, db


def save(
    vcon_uuid,
    opts=default_options,
):
    logger.info("Starting the Postgres storage for vCon: %s", vcon_uuid)
    try:
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        Vcons, db = create_vcons_class(opts)
        vcon_data = {
            "id": vcon.uuid,
            "uuid": vcon.uuid,
            "vcon": vcon.vcon,
            "created_at": vcon.created_at,
            "updated_at": datetime.now(),
            "subject": vcon.subject,
            "vcon_json": vcon.to_dict(),
            "created_by_local_type": vcon.to_dict().get('created_by', {}).get("local_type"),
            "created_by_local_type_version": vcon.to_dict().get('created_by', {}).get("local_type_version"),
            "created_by_domain": vcon.to_dict().get('created_by', {}).get("domain"),
        }
        Vcons.insert(**vcon_data).on_conflict(
            conflict_target=(Vcons.id), update=vcon_data
        ).execute()

        logger.info("Finished the Postgres storage for vCon: %s", vcon_uuid)
    except Exception as e:
        logger.error(
            f"postgres storage plugin: failed to insert vCon: {vcon_uuid}, error: {e} "
        )
    finally:
        db.close()  # TODO - connection pooling?


def get(
    vcon_uuid,
    opts=default_options,
):
    try:
        Vcons, db = create_vcons_class(opts)

        vcon = Vcons.get(Vcons.id == vcon_uuid)
        return vcon.vcon_json

    except Vcons.DoesNotExist:
        pass  # just return None
    except Exception as e:
        logger.error(
            f"Postgres storage plugin: failed to get vCon: {vcon_uuid}, error: {e} "
        )
    finally:
        db.close()