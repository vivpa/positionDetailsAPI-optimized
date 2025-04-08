import datetime as dt 
import intrinio_sdk as intrinio 
import numpy as np 
import json 
import pandas as pd 
import snowflake.connector 

from functions.calcEquityDetails import calcEquityDetails 
from functions.calcOptionDetails import calcOptionDetails 
from functions.getLatestWeekday import getLatestWeekday 
from functions.getSecretsIntrinioApiKey import getSecretsIntrinioApiKey 
from functions.getSecretsSnowflake import getSecretsSnowflake 
from functions.retrieveIntrinioStockPricesAndDividends import retrieveIntrinioStockPricesAndDividends 

def calcPositionsDetails(jsonPositionsDetailsInput): 
    dictPositionsDetailsInput = json.loads(jsonPositionsDetailsInput) 
    
    dfInstrumentsDetails = pd.DataFrame(dictPositionsDetailsInput['dfInstrumentsDetails']).T 
    
    lstAllTickers = [dfInstrumentsDetails.loc['Ticker symbol', eachColumn] for eachColumn in dfInstrumentsDetails.columns] 
    
    lstAllTickersRevised = [] 
    for eachTicker in lstAllTickers: 
        if eachTicker.find(' ') != -1: 
            eachTickerModified = eachTicker.split(' ')[0] 
        elif eachTicker.find('_') != -1: 
            eachTickerModified = eachTicker.split('_')[0] 
        else: 
            eachTickerModified = eachTicker 
        
        lstAllTickersRevised = lstAllTickersRevised + [eachTickerModified] 
    
    lstAllTickersRevised = list(np.unique(lstAllTickersRevised)) 
    
    # Data for SPY extracted to calculate the beta 
    # Needs to be made dynamic to deal with fixed income underlyings as well 
    benchmarkTicker = 'SPY' 
    
    if benchmarkTicker not in lstAllTickersRevised: 
        lstAllTickersRevised = lstAllTickersRevised + [benchmarkTicker] 
    
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
    
    # Calculating the start and end dates for data extraction 
    numOfYearsForDataExtraction = 5 
    endDate = dt.datetime.now() 
    endDate = getLatestWeekday(endDate) 
    startDate = endDate - dt.timedelta(days = numOfYearsForDataExtraction * 365) 
    startDate = getLatestWeekday(startDate) 
    
    # Downloading the historical data from Intrinio 
    dfPricesSplitAdj, dfPricesFinalNonAdj, dfAdjFactors, dfDividendsNonAdj = retrieveIntrinioStockPricesAndDividends(lstAllTickersRevised, startDate, endDate, snowflakeConnection) 
    
    dfPricesSplitAdj = dfPricesSplitAdj.ffill() 
    dfPricesFinalNonAdj = dfPricesFinalNonAdj.ffill() 
    dfAdjFactors = dfAdjFactors.fillna(1) 
    dfDividendsNonAdj = dfDividendsNonAdj.ffill() 
    
    dfPricesSplitAdj.index = pd.to_datetime(dfPricesSplitAdj.index) 
    dfPricesFinalNonAdj.index = pd.to_datetime(dfPricesFinalNonAdj.index) 
    
    # Calculating the cumulative adjustment factors 
    dfCumuAdjFactors = dfAdjFactors.sort_index(ascending = False) 
    dfCumuAdjFactors = dfCumuAdjFactors.cumprod() 
    dfCumuAdjFactors = dfCumuAdjFactors.sort_index(ascending = True) 
    dfCumuAdjFactors = dfCumuAdjFactors.shift(-1).ffill() 
    
    # Calculating the split adjusted dividends 
    dfDividendsSplitAdj = (dfDividendsNonAdj * dfCumuAdjFactors).dropna(how = 'all') 
    
    dictPositionsDetailsOutput = {} 
    for eachColumn in dfInstrumentsDetails.columns: 
        eachTicker =  dfInstrumentsDetails.loc['Ticker symbol', eachColumn] 
        
        if eachTicker.find(' ') != -1: 
            eachTickerModified = eachTicker.split(' ')[0] 
        elif eachTicker.find('_') != -1: 
            eachTickerModified = eachTicker.split('_')[0] 
        else: 
            # Check if this is an alphanumeric ticker 
            hasAlphabets = any(eachCharacter.isalpha() for eachCharacter in eachTicker) 
            hasNumbers = any(eachCharacter.isdigit() for eachCharacter in eachTicker) 

            if hasAlphabets == True and hasNumbers == True: 
                # If this is an alphanumeric ticker, it means that this is an options ticker 
                # For an options ticker, the last 15 characters specify the option characteristice (expiry date, call or put, strike price) 
                # The remaining characters specify the stock 
                eachTickerModified = eachTicker[0 : len(eachTicker) - 15] 
            else: 
                # Otherwise this is a stock ticker 
                eachTickerModified = eachTicker 
        
        # Triggering the relevant algo depending on whether the ticker is for an option or a stock / ETF 
        if dfInstrumentsDetails[eachColumn]['Ticker type'].lower() == 'option': 
            if benchmarkTicker == eachTickerModified: 
                dictPositionsDetailsOutput[eachColumn] = calcOptionDetails(dfInstrumentsDetails[eachColumn], dfPricesSplitAdj[[eachTickerModified]], dfPricesFinalNonAdj[[eachTickerModified]], dfAdjFactors[[eachTickerModified]], dfDividendsSplitAdj[[eachTickerModified]], intrinioApiKey, snowflakeConnection) 
            else: 
                dictPositionsDetailsOutput[eachColumn] = calcOptionDetails(dfInstrumentsDetails[eachColumn], dfPricesSplitAdj[[eachTickerModified, benchmarkTicker]], dfPricesFinalNonAdj[[eachTickerModified, benchmarkTicker]], dfAdjFactors[[eachTickerModified, benchmarkTicker]], dfDividendsSplitAdj[[eachTickerModified, benchmarkTicker]], intrinioApiKey, snowflakeConnection) 
        elif dfInstrumentsDetails[eachColumn]['Ticker type'].lower() == 'equity': 
            if benchmarkTicker == eachTickerModified: 
                dictPositionsDetailsOutput[eachColumn] = calcEquityDetails(dfInstrumentsDetails[eachColumn], dfPricesSplitAdj[[eachTickerModified]], dfPricesFinalNonAdj[[eachTickerModified]], dfAdjFactors[[eachTickerModified]], dfDividendsSplitAdj[[eachTickerModified]], intrinioApiKey, snowflakeConnection) 
            else: 
                dictPositionsDetailsOutput[eachColumn] = calcEquityDetails(dfInstrumentsDetails[eachColumn], dfPricesSplitAdj[[eachTickerModified, benchmarkTicker]], dfPricesFinalNonAdj[[eachTickerModified, benchmarkTicker]], dfAdjFactors[[eachTickerModified, benchmarkTicker]], dfDividendsSplitAdj[[eachTickerModified, benchmarkTicker]], intrinioApiKey, snowflakeConnection) 
    
    dictPositionsDetailsOutputRevised = {} 
    for eachKey in dictPositionsDetailsOutput.keys(): 
        dictPositionsDetailsOutputRevised[eachKey] = pd.Series(dictPositionsDetailsOutput[eachKey]).fillna('NA').to_dict() 

    # Creating an output list 
    lstPositionsDetailsOutput = [] 
    for eachKey in dictPositionsDetailsOutputRevised.keys(): 
        lstPositionsDetailsOutput = lstPositionsDetailsOutput + [dictPositionsDetailsOutputRevised[eachKey]] 
    
    jsonPositionsDetailsOutput = json.dumps(lstPositionsDetailsOutput) 
    
    return jsonPositionsDetailsOutput 

