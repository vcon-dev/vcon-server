from lib.vcon_redis import VconRedis
import vcon
import json


def test_store_vcon():
    # Create an instance of VconRedis
    vcon_redis = VconRedis()

    # Load tests/dataset/1ba06c0c-97ea-439f-8691-717ef86e4f3e.vcon.json to use
    # as the vCon object
    with open("tests/dataset/1ba06c0c-97ea-439f-8691-717ef86e4f3e.vcon.json") as f:
        vcon_json = json.load(f)
    vcon_obj = vcon.Vcon(vcon_json)

    # Call the store_vcon method
    vcon_redis.store_vcon(vcon_obj)


def test_get_vcon():
    # Create an instance of VconRedis
    vcon_redis = VconRedis()

    # Load tests/dataset/1ba06c0c-97ea-439f-8691-717ef86e4f3e.vcon.json to use
    # as the vCon object
    with open("tests/dataset/1ba06c0c-97ea-439f-8691-717ef86e4f3e.vcon.json") as f:
        vcon_json = json.load(f)
    vcon_obj = vcon.Vcon(vcon_json)

    # Call the store_vcon method
    vcon_redis.store_vcon(vcon_obj)

    # Call the get_vcon method
    loaded_vcon = vcon_redis.get_vcon(vcon_obj.uuid)

    # Assert that the contents of the loaded vCon object is the same as the
    # original vCon object
    # Convert the vCon object to a dictionary to compare
    assert vcon_obj.to_dict() == loaded_vcon.to_dict()


def test_store_vcon_dict():
    # Create an instance of VconRedis
    vcon_redis = VconRedis()

    # Load tests/dataset/1ba06c0c-97ea-439f-8691-717ef86e4f3e.vcon.json to use
    # as the vCon dictionary
    with open("tests/dataset/1ba06c0c-97ea-439f-8691-717ef86e4f3e.vcon.json") as f:
        vcon_dict = json.load(f)

    # Call the store_vcon_dict method
    vcon_redis.store_vcon_dict(vcon_dict)


def test_get_vcon_dict():
    # Create an instance of VconRedis
    vcon_redis = VconRedis()

    # Load tests/dataset/1ba06c0c-97ea-439f-8691-717ef86e4f3e.vcon.json to use
    # as the vCon dictionary
    with open("tests/dataset/1ba06c0c-97ea-439f-8691-717ef86e4f3e.vcon.json") as f:
        vcon_dict = json.load(f)

    # Call the store_vcon_dict method
    vcon_redis.store_vcon_dict(vcon_dict)

    # Call the get_vcon_dict method
    loaded_vcon_dict = vcon_redis.get_vcon_dict(vcon_dict["uuid"])

    # Assert that the contents of the loaded vCon dictionary is the same as the
    # original vCon dictionary
    assert vcon_dict == loaded_vcon_dict