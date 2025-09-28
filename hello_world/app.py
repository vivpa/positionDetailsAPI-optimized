import json
from datetime import datetime
import sys
import os
import re
import sentry_sdk
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration

# Import functions to do things 
from functions.calcPositionsDetails import calcPositionsDetails 
from functions.validateRequestBody import validateRequestBody 

# Initialize Sentry with environment variable
sentry_dsn = os.getenv('SENTRY_DSN')
if sentry_dsn:
    # Get sampling rates from environment variables with sensible defaults
    traces_sample_rate = float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1'))  # 10% default
    profile_sample_rate = float(os.getenv('SENTRY_PROFILE_SAMPLE_RATE', '0.1'))  # 10% default
    
    sentry_sdk.init(
        dsn=sentry_dsn,
        # Add data like request headers and IP for users, if applicable;
        # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
        send_default_pii=True,
        # Set traces_sample_rate to capture a percentage of transactions for tracing.
        # Default is 0.1 (10%) to balance monitoring with performance and costs.
        traces_sample_rate=traces_sample_rate,
        # To collect profiles for a percentage of profile sessions.
        # Default is 0.1 (10%) to balance profiling with performance and costs.
        profile_session_sample_rate=profile_sample_rate,
        # Profiles will be automatically collected while
        # there is an active span.
        profile_lifecycle="trace",
        integrations=[
            AwsLambdaIntegration(timeout_warning=True),
        ],
    )
    print(f"Sentry initialized with traces_sample_rate={traces_sample_rate}, profile_sample_rate={profile_sample_rate}")
else:
    print("Warning: SENTRY_DSN environment variable not set. Sentry monitoring disabled.") 

class first_call:
    def calcDetails(jsonPortfolioStatsInput): 
        # Compute process 
        jsonPortfolioStatsOutput = calcPositionsDetails(jsonPortfolioStatsInput) 

        return jsonPortfolioStatsOutput 
    
def mask_api_key_in_url(message):
    if "api_key=" in message:
        return re.sub(r"(api_key=)[^&]+", r"\1****", message)
    return message


def lambda_handler(event, context): 
    print('Entered lambda handler') 
    try:
        # Start clock
        start_time = datetime.now()
        print("Start time", start_time)

        # Event parameters from Lambda
        parsedBody = json.loads(event["body"]) 

        print("parsedBody: ", parsedBody) 

        valid, validMsg = validateRequestBody(parsedBody)
        if not valid:
            return {"statusCode": 400, "body": validMsg}

        print("Function call start")
        jsonPositionDetails = first_call.calcDetails(json.dumps(parsedBody))

        # f is the output of the previous function 
        dictPositionDetails = json.loads(jsonPositionDetails) 

        print("Function call end")

        print("Output", dictPositionDetails)

        # End the clock
        end_time = datetime.now()
        print("End time", end_time)
        print("Duration: {}".format(end_time - start_time))

        return {"statusCode": 200, "body": json.dumps(dictPositionDetails)}

    except Exception as ex:
        ex_type, ex_value, ex_traceback = sys.exc_info()

        # Capture error with Sentry
        if sentry_dsn:
            print("Capturing error with Sentry")
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("service", "position details api")
                scope.set_tag("stage", "development")
                scope.set_context("request", {
                    "request_id": context.aws_request_id if context else None,
                    "timestamp": datetime.now().isoformat()
                })
                sentry_sdk.capture_exception(ex)

        message = mask_api_key_in_url(str(ex_value))
        error_response = {
            "error": {
                "type": ex_type.__name__,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "request_id": context.aws_request_id if context else None,
                "details": {
                    "service": "position details api",
                    "stage": "development"  # You might want to make this an env variable
                }
            }
        }

        return {
            "statusCode": 400,
            "body": json.dumps(error_response),
            "headers": {
                "Content-Type": "application/json"
            }
        }
