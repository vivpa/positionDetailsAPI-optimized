import intrinio_sdk as intrinio 
import json 
import pandas as pd 
import snowflake.connector 

from functions.calcEquityDetails import calcEquityDetails 
from functions.calcOptionDetails import calcOptionDetails 
from functions.getSecretsIntrinioApiKey import getSecretsIntrinioApiKey 
from functions.getSecretsSnowflake import getSecretsSnowflake 

def calcPositionsDetails(jsonPositionsDetailsInput): 
    dictPositionsDetailsInput = json.loads(jsonPositionsDetailsInput) 

    dfInstrumentsDetails = pd.DataFrame(dictPositionsDetailsInput['dfInstrumentsDetails']) 
    
    # Initializing the Intrinio API 
    intrinioApiKey = getSecretsIntrinioApiKey() 
    intrinio.ApiClient().set_api_key(intrinioApiKey) 
    intrinio.ApiClient().allow_retries(True)
    
    # Establishing the Snowflake connection 
    strLoginName, strPassword, strWarehouse, strAccount = getSecretsSnowflake() 
    
    ctx = snowflake.connector.connect( 
        user = strLoginName, 
        password = strPassword, 
        warehouse = "BACKTEST_LARGE_WH", 
        account = strAccount 
    ) 
    
    snowflakeConnection = ctx.cursor() 
    
    dictPositionsDetailsOutput = {} 
    for eachIndex in dfInstrumentsDetails.index: 
        # Triggering the relevant algo depending on whether the ticker is for an option or a stock / ETF 
        if dfInstrumentsDetails.loc[eachIndex, 'Ticker type'].lower() == 'option': 
            dictPositionsDetailsOutput[eachIndex] = calcOptionDetails(dfInstrumentsDetails.loc[eachIndex], intrinioApiKey, snowflakeConnection) 
        elif dfInstrumentsDetails.loc[eachIndex, 'Ticker type'].lower() == 'equity': 
            dictPositionsDetailsOutput[eachIndex] = calcEquityDetails(dfInstrumentsDetails.loc[eachIndex], intrinioApiKey, snowflakeConnection) 
    
    jsonPositionsDetailsOutput = json.dumps(dictPositionsDetailsOutput) 
    
    return jsonPositionsDetailsOutput 
