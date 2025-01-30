import pandas as pd 

def validateRequestBody(parsedBody):
    # Check if all the required keys are present
    lstRequiredKeys = ['dfInstrumentsDetails'] 
    
    for eachKey in lstRequiredKeys: 
        if eachKey not in parsedBody: 
            return False, f"Key {eachKey} is required amongst the inputs" 

    lstRequiredFields = ['Ticker symbol', 'Ticker type', 'Ticker position', 'Underlying position', 'Option entry price', 'Option trade date'] 
    
    for eachField in lstRequiredFields: 
        if eachField not in list(pd.DataFrame(parsedBody['dfInstrumentsDetails']).columns): 
            return False, f"Field '{eachField}' is required for each position" 

    return True, "Valid request body"
