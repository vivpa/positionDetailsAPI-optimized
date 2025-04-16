import pandas as pd 

def validateRequestBody(parsedBody):
    # Check if all the required keys are present
    lstRequiredKeys = ['dfInstrumentsDetails'] 
    
    for eachKey in lstRequiredKeys: 
        if eachKey not in parsedBody: 
            error_response = {
                "error": {
                    "type": "ValidationError",
                    "message": f"Missing required key: {eachKey}",
                    "details": {
                        "field": eachKey,
                        "service": "position details api",
                        "component": "request_validation"
                    }
                }
            }
            return False, error_response            

    lstRequiredFields = ['Ticker symbol', 'Ticker type', 'Ticker position', 'Underlying position', 'Option entry price', 'Option trade date', 'position_detail_id'] 
    
    for eachField in lstRequiredFields: 
        if eachField not in list(pd.DataFrame(parsedBody['dfInstrumentsDetails']).columns): 
            error_response = {
                "error": {
                    "type": "ValidationError",
                    "message": f"Missing required field: {eachField}",
                    "details": {
                        "field": eachField,
                        "service": "position details api",
                        "component": "request_validation"
                    }
                }
            }
            return False, error_response            

    return True, "Valid request body"
