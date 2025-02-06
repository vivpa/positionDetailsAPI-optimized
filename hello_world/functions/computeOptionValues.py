
def computeOptionValues(optionType, underlyingPrice, strikePrice, optionMidPrice, expectedDividend):
    # Compute intrinsic value 
    if optionType.lower() == "call": 
        intrinsicValue = max(0.0, underlyingPrice - strikePrice) 
    elif optionType.lower() == "put": 
        intrinsicValue = max(0.0, strikePrice - underlyingPrice) 
    
    # Time value = option price - intrinsic value 
    timeValue = optionMidPrice - intrinsicValue 
    # timeValue can be negative if there's stale data or illiquid quotes, so we can floor at min 0 
    # timeValue = max(timeValue, 0.0) 
    
    # For calls: check if in-the-money AND time_val < expected_dividend 
    # Typically ignoring interest rates & days to expiry for simplicity 
    if (optionType == "call") and (underlyingPrice > strikePrice) and (timeValue < expectedDividend): 
        earlyExercise = 'Y' 
    else:
        earlyExercise = 'N' 
    
    return intrinsicValue, timeValue, earlyExercise 
