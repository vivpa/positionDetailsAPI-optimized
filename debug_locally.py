import json
import sys
import os

# Add the hello_world directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "hello_world"))

from app import lambda_handler

def main():
    # Load the test event
    with open('events/event_0408_1.json', 'r') as f:
        test_event = json.load(f)
    
    # Create a mock context (since we're not in AWS Lambda)
    class MockContext:
        def __init__(self):
            self.aws_request_id = "local-test-request-id"
    
    mock_context = MockContext()
    
    # Call the lambda handler
    print("Calling lambda_handler with test event...")
    response = lambda_handler(test_event, mock_context)
    
    # Print the response
    print("\nResponse:")
    print(json.dumps(response, indent=2))

if __name__ == "__main__":
    main() 
