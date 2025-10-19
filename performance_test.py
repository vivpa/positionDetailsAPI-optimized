import json
import sys
import os
import time
import statistics
from typing import List, Dict, Any

# Add the hello_world directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "hello_world"))

from app_optimized import lambda_handler

def load_test_events() -> List[Dict[str, Any]]:
    """Load various test events for performance testing"""
    test_events = []
    
    # Load different event files
    event_files = [
        'events/event_0925_1.json',
        'events/event_0617_2.json', 
        'events/event_0419_1.json',
        'events/event_0325_1.json'
    ]
    
    for event_file in event_files:
        try:
            with open(event_file, 'r') as f:
                test_event = json.load(f)
                test_events.append(test_event)
        except FileNotFoundError:
            print(f"Warning: {event_file} not found")
    
    return test_events

def create_mock_context():
    """Create a mock Lambda context"""
    class MockContext:
        def __init__(self):
            self.aws_request_id = f"perf-test-{int(time.time())}"
    
    return MockContext()

def run_performance_test(num_iterations: int = 5) -> Dict[str, Any]:
    """Run performance tests and collect metrics"""
    print(f"Running performance test with {num_iterations} iterations...")
    
    test_events = load_test_events()
    if not test_events:
        print("No test events found!")
        return {}
    
    execution_times = []
    success_count = 0
    error_count = 0
    
    for i in range(num_iterations):
        print(f"\n--- Iteration {i+1}/{num_iterations} ---")
        
        # Use different events for variety
        test_event = test_events[i % len(test_events)]
        mock_context = create_mock_context()
        
        start_time = time.time()
        
        try:
            response = lambda_handler(test_event, mock_context)
            end_time = time.time()
            
            execution_time = end_time - start_time
            execution_times.append(execution_time)
            
            if response.get('statusCode') == 200:
                success_count += 1
                print(f"✅ Success - Execution time: {execution_time:.2f}s")
            else:
                error_count += 1
                print(f"❌ Error - Status: {response.get('statusCode')}")
                print(f"Response: {response.get('body', 'No body')}")
                
        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            execution_times.append(execution_time)
            error_count += 1
            print(f"❌ Exception - Execution time: {execution_time:.2f}s")
            print(f"Error: {str(e)}")
    
    # Calculate performance metrics
    if execution_times:
        metrics = {
            'total_iterations': num_iterations,
            'success_count': success_count,
            'error_count': error_count,
            'success_rate': (success_count / num_iterations) * 100,
            'execution_times': execution_times,
            'avg_execution_time': statistics.mean(execution_times),
            'median_execution_time': statistics.median(execution_times),
            'min_execution_time': min(execution_times),
            'max_execution_time': max(execution_times),
            'std_deviation': statistics.stdev(execution_times) if len(execution_times) > 1 else 0
        }
        
        # Check if we meet the 15-second target
        metrics['meets_target'] = metrics['avg_execution_time'] < 15.0
        metrics['target_compliance'] = sum(1 for t in execution_times if t < 15.0) / len(execution_times) * 100
        
    else:
        metrics = {'error': 'No successful executions'}
    
    return metrics

def print_performance_report(metrics: Dict[str, Any]):
    """Print a detailed performance report"""
    print("\n" + "="*60)
    print("PERFORMANCE TEST REPORT")
    print("="*60)
    
    if 'error' in metrics:
        print(f"❌ Test failed: {metrics['error']}")
        return
    
    print(f"📊 Total Iterations: {metrics['total_iterations']}")
    print(f"✅ Successful: {metrics['success_count']}")
    print(f"❌ Errors: {metrics['error_count']}")
    print(f"📈 Success Rate: {metrics['success_rate']:.1f}%")
    print()
    
    print("⏱️  EXECUTION TIME METRICS:")
    print(f"   Average: {metrics['avg_execution_time']:.2f}s")
    print(f"   Median:  {metrics['median_execution_time']:.2f}s")
    print(f"   Min:     {metrics['min_execution_time']:.2f}s")
    print(f"   Max:     {metrics['max_execution_time']:.2f}s")
    print(f"   Std Dev: {metrics['std_deviation']:.2f}s")
    print()
    
    print("🎯 TARGET COMPLIANCE:")
    target_met = "✅ YES" if metrics['meets_target'] else "❌ NO"
    print(f"   Meets 15s target: {target_met}")
    print(f"   Compliance rate: {metrics['target_compliance']:.1f}%")
    print()
    
    print("📋 DETAILED TIMES:")
    for i, exec_time in enumerate(metrics['execution_times'], 1):
        status = "✅" if exec_time < 15.0 else "❌"
        print(f"   Run {i}: {exec_time:.2f}s {status}")
    
    print("\n" + "="*60)
    
    # Recommendations
    if not metrics['meets_target']:
        print("🚨 RECOMMENDATIONS:")
        print("   - Consider implementing more aggressive caching")
        print("   - Optimize database queries further")
        print("   - Reduce data extraction period")
        print("   - Implement connection pooling")
    else:
        print("🎉 PERFORMANCE TARGET ACHIEVED!")
        print("   The optimized version meets the 15-second requirement.")

def main():
    """Main performance testing function"""
    print("🚀 Starting Performance Test for Optimized Position Details API")
    print("Target: < 15 seconds execution time")
    print()
    
    # Run performance test
    metrics = run_performance_test(num_iterations=5)
    
    # Print detailed report
    print_performance_report(metrics)

if __name__ == "__main__":
    main()
