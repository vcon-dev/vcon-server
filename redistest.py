import redis

def test_redis_connection(host, port):
    print(f"\nTesting Redis connection to {host}:{port}")
    r = redis.Redis(host=host, port=port)
    
    # Test basic Redis functionality
    try:
        r.ping()
        print("Basic Redis connectivity: SUCCESS")
    except Exception as e:
        print(f"Basic Redis connectivity FAILED: {e}")
        return
    
    # Test RedisJSON module
    try:
        result = r.json().set('test', '$', {'test': 'value'})
        print(f"JSON.SET test result: {result}")
        value = r.json().get('test')
        print(f"JSON.GET test result: {value}")
        print("RedisJSON is working properly!")
    except Exception as e:
        print(f"RedisJSON test FAILED: {e}")

# Test the new Redis Stack instance
print("Testing new Redis Stack instance...")
test_redis_connection('localhost', 6380)