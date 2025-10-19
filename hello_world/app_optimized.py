import json
from datetime import datetime
import sys
import os
import re
import sentry_sdk
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration
import time

# Import optimized functions
from functions.calcPositionsDetails_optimized import calcPositionsDetails 
from functions.validateRequestBody import validateRequestBody 

# Initialize Sentry with environment variable
sentry_dsn = os.getenv('SENTRY_DSN')
if sentry_dsn:
    # Get sampling rates from environment variables with sensible defaults
    traces_sample_rate = float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1'))  # 10% default
    profile_sample_rate = float(os.getenv('SENTRY_PROFILE_SAMPLE_RATE', '0.1'))  # 10% default
    
    sentry_sdk.init(
        dsn=sentry_dsn,
        send_default_pii=True,
        traces_sample_rate=traces_sample_rate,
        profile_session_sample_rate=profile_sample_rate,
        profile_lifecycle="trace",
        integrations=[
            AwsLambdaIntegration(timeout_warning=True),
        ],
    )
    print(f"Sentry initialized with traces_sample_rate={traces_sample_rate}, profile_sample_rate={profile_sample_rate}")
else:
    print("Warning: SENTRY_DSN environment variable not set. Sentry monitoring disabled.") 

class OptimizedCalculator:
    """Optimized calculator class with performance monitoring"""
    
    @staticmethod
    def calcDetails(jsonPortfolioStatsInput: str) -> str:
        """Optimized calculation process with timing"""
        start_time = time.time()
        print(f"Starting calcDetails at {start_time}")
        
        try:
            jsonPortfolioStatsOutput = calcPositionsDetails(jsonPortfolioStatsInput)
            print(f"calcDetails completed in {time.time() - start_time:.2f}s")
            return jsonPortfolioStatsOutput
        except Exception as e:
            print(f"Error in calcDetails: {e}")
            raise
    
def mask_api_key_in_url(message):
    """Mask API keys in error messages"""
    if "api_key=" in message:
        return re.sub(r"(api_key=)[^&]+", r"\1****", message)
    return message

def lambda_handler(event, context): 
    """Optimized Lambda handler with performance monitoring"""
    print('Entered optimized lambda handler') 
    
    # Start comprehensive timing
    total_start_time = time.time()
    
    try:
        # Parse event body
        parse_start = time.time()
        parsedBody = json.loads(event["body"]) 
        print(f"Event parsing completed in {time.time() - parse_start:.2f}s")

        print("parsedBody: ", parsedBody) 

        # Validate request body
        validation_start = time.time()
        valid, validMsg = validateRequestBody(parsedBody)
        if not valid:
            return {"statusCode": 400, "body": validMsg}
        print(f"Request validation completed in {time.time() - validation_start:.2f}s")

        # Perform calculations
        print("Starting optimized function call")
        calc_start = time.time()
        jsonPositionDetails = OptimizedCalculator.calcDetails(json.dumps(parsedBody))
        print(f"Function call completed in {time.time() - calc_start:.2f}s")

        # Parse output
        output_start = time.time()
        dictPositionDetails = json.loads(jsonPositionDetails) 
        print(f"Output parsing completed in {time.time() - output_start:.2f}s")

        print("Output", dictPositionDetails)

        # Calculate total execution time
        total_time = time.time() - total_start_time
        print(f"Total Lambda execution time: {total_time:.2f}s")

        # Add performance metrics to response headers
        response_headers = {
            "Content-Type": "application/json",
            "X-Execution-Time": f"{total_time:.2f}s",
            "X-Performance-Optimized": "true"
        }

        return {
            "statusCode": 200, 
            "body": json.dumps(dictPositionDetails),
            "headers": response_headers
        }

    except Exception as ex:
        ex_type, ex_value, ex_traceback = sys.exc_info()

        # Capture error with Sentry
        if sentry_dsn:
            print("Capturing error with Sentry")
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("service", "position details api")
                scope.set_tag("stage", "production")
                scope.set_context("request", {
                    "request_id": context.aws_request_id if context else None,
                    "timestamp": datetime.now().isoformat(),
                    "execution_time": f"{time.time() - total_start_time:.2f}s"
                })
                sentry_sdk.capture_exception(ex)

        message = mask_api_key_in_url(str(ex_value))
        error_response = {
            "error": {
                "type": ex_type.__name__,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "request_id": context.aws_request_id if context else None,
                "execution_time": f"{time.time() - total_start_time:.2f}s",
                "details": {
                    "service": "position details api",
                    "stage": "production"
                }
            }
        }

        return {
            "statusCode": 400,
            "body": json.dumps(error_response),
            "headers": {
                "Content-Type": "application/json",
                "X-Execution-Time": f"{time.time() - total_start_time:.2f}s"
            }
        }
