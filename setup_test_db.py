#!/usr/bin/env python3
import os
os.environ['CONSERVER_CONFIG_FILE'] = '/app/test_config.yml'

from server.storage.postgres import get_db_connection, Vcons

opts = {
    "database": "vcon_test_db",
    "user": "postgres", 
    "password": "postgres",
    "host": "postgres",
    "port": 5432,
}

print("Connecting to PostgreSQL...")
db = get_db_connection(opts)
Vcons._meta.database = db

print("Creating vcons table...")
db.create_tables([Vcons], safe=True)
print("Table created successfully!")
db.close()
