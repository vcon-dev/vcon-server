import os, sys, json, uuid6
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from spaceandtime import SpaceAndTime, SXTTable   # pip3 install spaceandtime 

# for testing in-place: add parent directories to path to support local imports
# remove this next line once fully integerated (or not, whatever):
for i in range(0,4): sys.path.append(str(Path(__file__).parents[i])) 
from lib.logging_utils import init_logger  
from server.lib.vcon_redis import VconRedis


# Probably merge these Envars into one of the existing config files
load_dotenv()
SXT_API_KEY = os.getenv("SXT_API_KEY")  # Check out: https://docs.spaceandtime.io/docs/api-key
SXT_VCON_TABLENAME = os.getenv("SXT_VCON_TABLENAME")  # Provided by SXT
SXT_VCON_TABLE_WRITE_BISCUIT = os.getenv("SXT_VCON_TABLE_WRITE_BISCUI") # Provided by SXT


# Initialize the logger and default VCON options:
logger = init_logger(__name__)
default_options = {"name": "spaceandtime"}

# Define the SXT object once. Can also move this into the save/get functions
sxt = SpaceAndTime(api_key=SXT_API_KEY, authenticate=True, logger=logger )


 
def save(
    vcon_uuid,
    opts=default_options
):
    logger.info("Starting the spaceandtime storage for vCon: %s", vcon_uuid)
    try:
        vcon_redis = VconRedis()

        # GET VCON, EITHER REAL FROM REDIS OR FOR TESTING
        if vcon_uuid == 'test': # generate a test record:
            vcon = {"uuid": uuid6.uuid6(), 
                    "vcon": "test", 
                    "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                    "subject": "test", 
                    "vcon_json": json.dumps(opts) }
        else: 
            vcon = vcon_redis.get_vcon(vcon_uuid)

        # ENSURE CONNECTION TO SPACE AND TIME IS STILL VALID:
        if sxt.user.access_expired: 
            success, response = sxt.authenticate()
            if not success: raise Exception(response)

        tbl = SXTTable(name=SXT_VCON_TABLENAME, SpaceAndTime_parent=sxt) # inherit user/logging/etc. from sxt object
        tbl.biscuits.append(SXT_VCON_TABLE_WRITE_BISCUIT)

        # MAKE SURE VCON IS WELL FORMED:
        for col in vcon.keys():
            if col.upper() not in tbl.columns.keys():
                raise Exception(f"VCON object doesn't have a corresponding column in table:{SXT_VCON_TABLENAME}, column:{str(col).upper()}")
            
        # INSERT ROW INTO SPACE AND TIME
        success, response = tbl.insert.list_of_dicts(list_of_dicts=[dict(vcon)]) # this can insert many rows, if more efficient

        # LOG RESULTS:
        if success: logger.info("Finished the spaceandtime storage for vCon: %s", vcon_uuid)
        else: raise Exception(response)

        return vcon['uuid']
            
    except Exception as e:
        logger.error(f"spaceandtime storage plugin: failed to insert vCon: {vcon_uuid}, error: {e} ")



def get(
    vcon_uuid,
    opts=default_options,
):
    logger.info("Starting the spaceandtime storage get for vCon: %s", vcon_uuid)
    try:

        # CONNECT TO SPACE AND TIME
        if sxt.user.access_expired: 
            success, response = sxt.authenticate()
            if not success: raise Exception(response)

        tbl = SXTTable(name=SXT_VCON_TABLENAME, SpaceAndTime_parent=sxt)
        tbl.biscuits.append(SXT_VCON_TABLE_WRITE_BISCUIT)

        success, response = tbl.select(sql_text=f"select * from {tbl.table_name} where uuid='{vcon_uuid}' ")
        if not success: raise Exception(response)

        # looks like the postgres plugin returns only the 'vcon_json' column, so we will too:
        return None if response == [] else json.loads(response[0]['VCON_JSON'])
    
    except Exception as e:
        logger.error(
            f"Postgres storage plugin: failed to get vCon: {vcon_uuid}, error: {e} "
        )



if __name__ == "__main__":  # lightweight unit testing

    # genearate a new test vcon
    uuid = save('test')

    # retrieve the VCON we just created
    data = get(uuid)
    print(data)

    # retrieve a non-existant VCON (aka NONE)
    data = get('nope')
    print(data)