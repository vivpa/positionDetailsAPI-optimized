import json
from datetime import datetime
import sys

# Import functions to do things 
from functions.calcPositionsDetails import calcPositionsDetails 
from functions.validateRequestBody import validateRequestBody 

class first_call:
    def calcDetails(jsonPortfolioStatsInput): 
        # Compute process 
        jsonPortfolioStatsOutput = calcPositionsDetails(jsonPortfolioStatsInput) 

        return jsonPortfolioStatsOutput 


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

        error_response = {
            "error": {
                "type": ex_type.__name__,
                "message": str(ex_value),
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
