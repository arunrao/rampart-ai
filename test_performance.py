#!/usr/bin/env python3
"""
Test script to verify API performance improvements

Usage:
    python test_performance.py
    
Environment Variables:
    RAMPART_API_KEY - Your Rampart API key (required)
    RAMPART_API_URL - API base URL (default: http://localhost:8000/api/v1)
"""
import os
import sys
import time
import requests
from statistics import mean, median, stdev

# Configuration
API_KEY = os.getenv("RAMPART_API_KEY")
API_URL = os.getenv("RAMPART_API_URL", "http://localhost:8000/api/v1")

if not API_KEY:
    print("❌ Error: RAMPART_API_KEY environment variable not set")
    print("\nUsage:")
    print("  export RAMPART_API_KEY=rmp_live_your_key_here")
    print("  python test_performance.py")
    sys.exit(1)

# Test cases
TEST_CASES = [
    {
        "name": "PII Detection Only",
        "endpoint": f"{API_URL}/filter",
        "payload": {
            "content": "My email is john@example.com and phone is 555-1234",
            "filters": ["pii"],
            "redact": True
        }
    },
    {
        "name": "Security Analysis",
        "endpoint": f"{API_URL}/security/analyze",
        "payload": {
            "content": "What is the weather like today?",
            "context_type": "input"
        }
    },
    {
        "name": "Full Content Filter",
        "endpoint": f"{API_URL}/filter",
        "payload": {
            "content": "My name is John Doe. What is the capital of France?",
            "filters": ["pii", "toxicity", "prompt_injection"],
            "redact": True
        }
    }
]

def run_test(test_case, num_requests=10):
    """Run a single test case multiple times and collect metrics"""
    print(f"\n📊 Testing: {test_case['name']}")
    print(f"   Endpoint: {test_case['endpoint']}")
    print(f"   Requests: {num_requests}")
    
    latencies = []
    processing_times = []
    errors = 0
    
    for i in range(num_requests):
        try:
            start = time.time()
            response = requests.post(
                test_case['endpoint'],
                json=test_case['payload'],
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            end = time.time()
            
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)
            
            if response.status_code == 200:
                data = response.json()
                processing_time = data.get('processing_time_ms', 0)
                processing_times.append(processing_time)
                
                # Print progress
                print(f"   Request {i+1}/{num_requests}: {latency_ms:.1f}ms (processing: {processing_time:.2f}ms) ✓")
            else:
                errors += 1
                print(f"   Request {i+1}/{num_requests}: Error {response.status_code} ✗")
                
        except Exception as e:
            errors += 1
            print(f"   Request {i+1}/{num_requests}: Exception: {e} ✗")
    
    # Calculate statistics
    if latencies:
        print(f"\n   📈 Results:")
        print(f"      Total Latency (wall clock):")
        print(f"         Mean:   {mean(latencies):.1f}ms")
        print(f"         Median: {median(latencies):.1f}ms")
        print(f"         Min:    {min(latencies):.1f}ms")
        print(f"         Max:    {max(latencies):.1f}ms")
        if len(latencies) > 1:
            print(f"         StdDev: {stdev(latencies):.1f}ms")
        
        if processing_times:
            print(f"\n      Processing Time (reported by API):")
            print(f"         Mean:   {mean(processing_times):.2f}ms")
            print(f"         Median: {median(processing_times):.2f}ms")
            
            # Calculate overhead
            overhead = mean(latencies) - mean(processing_times)
            print(f"\n      Network + Overhead: {overhead:.1f}ms")
        
        # Success rate
        success_rate = ((num_requests - errors) / num_requests) * 100
        print(f"\n      Success Rate: {success_rate:.1f}%")
        
        # Performance assessment
        avg_latency = mean(latencies)
        if avg_latency < 50:
            print(f"\n      ✅ Performance: EXCELLENT (< 50ms)")
        elif avg_latency < 200:
            print(f"\n      ✅ Performance: GOOD (< 200ms)")
        elif avg_latency < 500:
            print(f"\n      ⚠️  Performance: ACCEPTABLE (< 500ms)")
        elif avg_latency < 1000:
            print(f"\n      ⚠️  Performance: SLOW (< 1000ms)")
        else:
            print(f"\n      ❌ Performance: VERY SLOW (> 1000ms)")
            print(f"         Expected: ~10-50ms after fix")
            print(f"         Possible issues: Database latency, network issues")
    
    return {
        "latencies": latencies,
        "processing_times": processing_times,
        "errors": errors
    }


def main():
    print("=" * 70)
    print("🚀 RAMPART API PERFORMANCE TEST")
    print("=" * 70)
    print(f"\nAPI URL: {API_URL}")
    print(f"API Key: {API_KEY[:20]}...")
    
    # Health check
    print("\n🏥 Health Check...")
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ API is healthy")
        else:
            print(f"   ❌ API health check failed: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"   ❌ Cannot reach API: {e}")
        sys.exit(1)
    
    # Run all tests
    all_results = {}
    for test_case in TEST_CASES:
        results = run_test(test_case, num_requests=10)
        all_results[test_case['name']] = results
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    
    for name, results in all_results.items():
        if results['latencies']:
            avg_latency = mean(results['latencies'])
            avg_processing = mean(results['processing_times']) if results['processing_times'] else 0
            success_rate = ((10 - results['errors']) / 10) * 100
            
            print(f"\n{name}:")
            print(f"  Avg Latency: {avg_latency:.1f}ms")
            print(f"  Avg Processing: {avg_processing:.2f}ms")
            print(f"  Success Rate: {success_rate:.0f}%")
    
    # Overall assessment
    all_latencies = []
    for results in all_results.values():
        all_latencies.extend(results['latencies'])
    
    if all_latencies:
        overall_avg = mean(all_latencies)
        print(f"\n{'=' * 70}")
        print(f"Overall Average Latency: {overall_avg:.1f}ms")
        
        if overall_avg < 50:
            print("✅ EXCELLENT - Performance fix is working!")
        elif overall_avg < 200:
            print("✅ GOOD - Acceptable performance")
        elif overall_avg < 1000:
            print("⚠️  SLOW - Performance could be improved")
        else:
            print("❌ VERY SLOW - Performance fix may not be deployed")
            print("\nTroubleshooting:")
            print("1. Ensure you're testing against production (not local dev)")
            print("2. Check if code has been deployed: cd aws/ && ./update.sh")
            print("3. Monitor deployment: cd aws/ && ./monitor-deployment.sh")
            print("4. Check database latency from EC2 instances")
    
    print(f"\n{'=' * 70}")
    print("✓ Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    main()

