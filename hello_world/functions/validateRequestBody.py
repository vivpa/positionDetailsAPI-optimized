
def validateRequestBody(parsedBody):
    # Check if all the required keys are present
    requiredFields = ['tickerSymbol', 'tickerType', 'tickerPosition'] 
    
    for eachField in requiredFields:
        if eachField not in parsedBody:
            return False, f"{eachField} is required" 

    return True, "Valid request body"
