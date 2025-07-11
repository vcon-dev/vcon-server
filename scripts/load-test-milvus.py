#!/usr/bin/env python3
"""
Load testing script for Milvus with vCon data
Usage: python scripts/load-test-milvus.py --vcons 1000 --concurrent 10
"""

import asyncio
import argparse
import time
import random
import statistics
from concurrent.futures import ThreadPoolExecutor
import uuid
from datetime import datetime, UTC

try:
    from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
except ImportError:
    print("❌ pymilvus not installed. Run: pip install pymilvus")
    exit(1)

class MilvusLoadTester:
    def __init__(self, host="localhost", port="19530"):
        self.host = host
        self.port = port
        self.collection_name = f"load_test_{int(time.time())}"
        self.results = {
            'insert_times': [],
            'search_times': [],
            'errors': []
        }
    
    def connect(self):
        """Connect to Milvus"""
        try:
            connections.connect(host=self.host, port=self.port)
            print(f"✅ Connected to Milvus at {self.host}:{self.port}")
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            exit(1)
    
    def create_collection(self):
        """Create test collection"""
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="vcon_uuid", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
            FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=30),
        ]
        
        schema = CollectionSchema(fields=fields, description="Load test collection")
        collection = Collection(name=self.collection_name, schema=schema)
        
        # Create index
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        
        print(f"✅ Created collection: {self.collection_name}")
        return collection
    
    def generate_test_vcon(self, index):
        """Generate test vCon data"""
        vcon_uuid = f"load-test-{index}-{uuid.uuid4().hex[:8]}"
        text = f"Load test vCon {index}. This is sample conversation text for testing purposes. Customer called about billing issues and account updates."
        embedding = [random.uniform(-1, 1) for _ in range(1536)]
        created_at = datetime.now(UTC).isoformat()
        
        return {
            "vcon_uuid": vcon_uuid,
            "text": text,
            "embedding": embedding,
            "created_at": created_at
        }
    
    def insert_batch(self, collection, batch_data):
        """Insert a batch of data"""
        start_time = time.time()
        try:
            result = collection.insert(batch_data)
            collection.flush()
            insert_time = time.time() - start_time
            self.results['insert_times'].append(insert_time)
            return result.insert_count
        except Exception as e:
            self.results['errors'].append(f"Insert error: {e}")
            return 0
    
    def search_vectors(self, collection, num_searches=10):
        """Perform vector searches"""
        collection.load()
        search_times = []
        
        for i in range(num_searches):
            # Generate random search vector
            search_vector = [random.uniform(-1, 1) for _ in range(1536)]
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            
            start_time = time.time()
            try:
                results = collection.search(
                    data=[search_vector],
                    anns_field="embedding",
                    param=search_params,
                    limit=5,
                    output_fields=["vcon_uuid"]
                )
                search_time = time.time() - start_time
                search_times.append(search_time)
            except Exception as e:
                self.results['errors'].append(f"Search error: {e}")
        
        self.results['search_times'].extend(search_times)
        return search_times
    
    def concurrent_inserts(self, num_vcons, batch_size, num_workers):
        """Perform concurrent insertions"""
        collection = Collection(self.collection_name)
        
        def insert_worker(start_idx, end_idx):
            batch_data = []
            for i in range(start_idx, end_idx):
                batch_data.append(self.generate_test_vcon(i))
                
                if len(batch_data) >= batch_size:
                    self.insert_batch(collection, batch_data)
                    batch_data = []
            
            # Insert remaining data
            if batch_data:
                self.insert_batch(collection, batch_data)
        
        # Distribute work among workers
        vcons_per_worker = num_vcons // num_workers
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for i in range(num_workers):
                start_idx = i * vcons_per_worker
                end_idx = start_idx + vcons_per_worker
                if i == num_workers - 1:  # Last worker gets remaining
                    end_idx = num_vcons
                
                futures.append(executor.submit(insert_worker, start_idx, end_idx))
            
            # Wait for all workers to complete
            for future in futures:
                future.result()
    
    def cleanup(self):
        """Clean up test collection"""
        try:
            collection = Collection(self.collection_name)
            collection.drop()
            print(f"🧹 Cleaned up collection: {self.collection_name}")
        except:
            pass
        
        try:
            connections.disconnect("default")
        except:
            pass
    
    def print_results(self, num_vcons, num_workers):
        """Print test results"""
        print("\n" + "="*50)
        print("📊 LOAD TEST RESULTS")
        print("="*50)
        print(f"Total vCons: {num_vcons}")
        print(f"Concurrent workers: {num_workers}")
        print(f"Errors: {len(self.results['errors'])}")
        
        if self.results['insert_times']:
            total_insert_time = sum(self.results['insert_times'])
            avg_insert_time = statistics.mean(self.results['insert_times'])
            throughput = num_vcons / total_insert_time if total_insert_time > 0 else 0
            
            print(f"\n📈 INSERT PERFORMANCE:")
            print(f"  Total time: {total_insert_time:.2f}s")
            print(f"  Average batch time: {avg_insert_time:.3f}s")
            print(f"  Throughput: {throughput:.1f} vCons/second")
        
        if self.results['search_times']:
            avg_search_time = statistics.mean(self.results['search_times'])
            
            print(f"\n🔍 SEARCH PERFORMANCE:")
            print(f"  Average search time: {avg_search_time:.3f}s")
            print(f"  Total searches: {len(self.results['search_times'])}")
        
        if self.results['errors']:
            print(f"\n❌ ERRORS:")
            for error in self.results['errors'][:5]:  # Show first 5 errors
                print(f"  {error}")
            if len(self.results['errors']) > 5:
                print(f"  ... and {len(self.results['errors']) - 5} more")
        
        print("="*50)

def main():
    parser = argparse.ArgumentParser(description="Load test Milvus with vCon data")
    parser.add_argument("--vcons", type=int, default=100, help="Number of vCons to insert")
    parser.add_argument("--concurrent", type=int, default=5, help="Number of concurrent workers")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for inserts")
    parser.add_argument("--searches", type=int, default=50, help="Number of search operations")
    parser.add_argument("--host", default="localhost", help="Milvus host")
    parser.add_argument("--port", default="19530", help="Milvus port")
    
    args = parser.parse_args()
    
    print(f"🚀 Starting Milvus load test")
    print(f"   vCons: {args.vcons}")
    print(f"   Workers: {args.concurrent}")
    print(f"   Batch size: {args.batch_size}")
    print(f"   Searches: {args.searches}")
    
    tester = MilvusLoadTester(args.host, args.port)
    
    try:
        # Setup
        tester.connect()
        collection = tester.create_collection()
        
        # Load test
        print(f"\n📝 Inserting {args.vcons} vCons...")
        start_time = time.time()
        tester.concurrent_inserts(args.vcons, args.batch_size, args.concurrent)
        total_time = time.time() - start_time
        
        print(f"✅ Insertion completed in {total_time:.2f}s")
        
        # Search test
        print(f"\n🔍 Performing {args.searches} searches...")
        tester.search_vectors(collection, args.searches)
        print("✅ Search test completed")
        
        # Results
        tester.print_results(args.vcons, args.concurrent)
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
    finally:
        tester.cleanup()

if __name__ == "__main__":
    main()