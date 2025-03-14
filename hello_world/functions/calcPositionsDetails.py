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

    dfInstrumentsDetails = pd.DataFrame(dictPositionsDetailsInput['dfInstrumentsDetails']).T 
    
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
    for eachColumn in dfInstrumentsDetails.columns: 
        if len(dfInstrumentsDetails.loc['Ticker symbol', eachColumn]) >= 5 and len(dfInstrumentsDetails.loc['Ticker symbol', eachColumn]) <= 6 and dfInstrumentsDetails.loc['Ticker symbol', eachColumn].endswith("X"): 
            dictPositionsDetailsOutput[eachColumn] = {'Underlying type': 'Mutual fund'} 

            continue 
        
        # Triggering the relevant algo depending on whether the ticker is for an option or a stock / ETF 
        if dfInstrumentsDetails[eachColumn]['Ticker type'].lower() == 'option': 
            dictPositionsDetailsOutput[eachColumn] = calcOptionDetails(dfInstrumentsDetails[eachColumn], intrinioApiKey, snowflakeConnection) 
        elif dfInstrumentsDetails[eachColumn]['Ticker type'].lower() == 'equity': 
            dictPositionsDetailsOutput[eachColumn] = calcEquityDetails(dfInstrumentsDetails[eachColumn], intrinioApiKey, snowflakeConnection) 
        else: 
            if len(dfInstrumentsDetails.loc['Ticker symbol', eachColumn]) >= 5 and len(dfInstrumentsDetails.loc['Ticker symbol', eachColumn]) <= 6 and dfInstrumentsDetails.loc['Ticker symbol', eachColumn].endswith("X"): 
                dictPositionsDetailsOutput[eachColumn] = {'Underlying type': 'Mutual fund'} 
            else: 
                dictPositionsDetailsOutput[eachColumn] = {'Underlying type': 'Other'} 
    
    dictPositionsDetailsOutputRevised = {} 
    for eachKey in dictPositionsDetailsOutput.keys(): 
        dictPositionsDetailsOutputRevised[eachKey] = pd.Series(dictPositionsDetailsOutput[eachKey]).fillna('NA').to_dict() 

    # Creating an output list 
    lstPositionsDetailsOutput = [] 
    for eachKey in dictPositionsDetailsOutputRevised.keys(): 
        lstPositionsDetailsOutput = lstPositionsDetailsOutput + [dictPositionsDetailsOutputRevised[eachKey]] 
    
    jsonPositionsDetailsOutput = json.dumps(lstPositionsDetailsOutput) 
    
    return jsonPositionsDetailsOutput 

