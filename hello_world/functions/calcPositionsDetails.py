import intrinio_sdk as intrinio 
import json 
import snowflake.connector 

from functions.calcEquityDetails import calcEquityDetails 
from functions.calcOptionDetails import calcOptionDetails 
from functions.getSecretsIntrinioApiKey import getSecretsIntrinioApiKey 
from functions.getSecretsSnowflake import getSecretsSnowflake 

def calcPositionsDetails(jsonPositionsDetailsInput): 
    dictPositionsDetailsInput = json.loads(jsonPositionsDetailsInput) 
    
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
    
    # Triggering the relevant algo depending on whether the ticker is for an option or a stock / ETF 
    if dictPositionsDetailsInput['tickerType'].lower() == 'option': 
        dictPositionsDetailsOutput = calcOptionDetails(dictPositionsDetailsInput, snowflakeConnection) 
    elif dictPositionsDetailsInput['tickerType'].lower() == 'equity': 
        dictPositionsDetailsOutput = calcEquityDetails(dictPositionsDetailsInput, snowflakeConnection) 
    
    jsonPositionsDetailsOutput = json.dumps(dictPositionsDetailsOutput) 
    
    return jsonPositionsDetailsOutput 
