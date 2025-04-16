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
        if ' ' in eachTicker: 
            eachTickerModified = eachTicker.split(' ')[0] 
        elif '_' in eachTicker: 
            eachTickerModified = eachTicker.split('_')[0] 
        else: 
            eachTickerModified = eachTicker 
        lstAllTickersRevised.append(eachTickerModified)
    
    lstAllTickersRevised = list(np.unique(lstAllTickersRevised)) 
    
    benchmarkTicker = 'SPY' 
    if benchmarkTicker not in lstAllTickersRevised: 
        lstAllTickersRevised.append(benchmarkTicker)
    
    intrinioApiKey = getSecretsIntrinioApiKey() 
    intrinio.ApiClient().set_api_key(intrinioApiKey) 
    intrinio.ApiClient().allow_retries(True)
    
    strLoginName, strPassword, strWarehouse, strAccount = getSecretsSnowflake() 
    ctx = snowflake.connector.connect(user=strLoginName, password=strPassword, warehouse="BACKTEST_LARGE_WH", account=strAccount) 
    snowflakeConnection = ctx.cursor() 
    
    numOfYearsForDataExtraction = 5 
    endDate = getLatestWeekday(dt.datetime.now()) 
    startDate = getLatestWeekday(endDate - dt.timedelta(days=numOfYearsForDataExtraction * 365)) 
    
    dfPricesSplitAdj, dfPricesFinalNonAdj, dfAdjFactors, dfDividendsNonAdj = retrieveIntrinioStockPricesAndDividends(lstAllTickersRevised, startDate, endDate, snowflakeConnection) 
    
    dfPricesSplitAdj = dfPricesSplitAdj.ffill() 
    dfPricesFinalNonAdj = dfPricesFinalNonAdj.ffill() 
    dfAdjFactors = dfAdjFactors.fillna(1) 
    dfDividendsNonAdj = dfDividendsNonAdj.ffill() 
    
    dfPricesSplitAdj.index = pd.to_datetime(dfPricesSplitAdj.index) 
    dfPricesFinalNonAdj.index = pd.to_datetime(dfPricesFinalNonAdj.index) 
    
    dfCumuAdjFactors = dfAdjFactors.sort_index(ascending=False).cumprod().sort_index(ascending=True).shift(-1).ffill() 
    dfDividendsSplitAdj = (dfDividendsNonAdj * dfCumuAdjFactors).dropna(how='all') 
    
    dictPositionsDetailsOutput = {} 
    for eachColumn in dfInstrumentsDetails.columns: 
        eachPosition = dfInstrumentsDetails[eachColumn]
        position_id = str(eachPosition['position_detail_id'])
        eachTicker = eachPosition['Ticker symbol'] 
        
        if ' ' in eachTicker: 
            eachTickerModified = eachTicker.split(' ')[0] 
        elif '_' in eachTicker: 
            eachTickerModified = eachTicker.split('_')[0] 
        else: 
            hasAlphabets = any(c.isalpha() for c in eachTicker) 
            hasNumbers = any(c.isdigit() for c in eachTicker) 
            if hasAlphabets and hasNumbers: 
                eachTickerModified = eachTicker[0: len(eachTicker) - 15] 
            else: 
                eachTickerModified = eachTicker 
        
        try:
            if eachPosition['Ticker type'].lower() == 'option': 
                if benchmarkTicker == eachTickerModified: 
                    details = calcOptionDetails(eachPosition, dfPricesSplitAdj[[eachTickerModified]], dfPricesFinalNonAdj[[eachTickerModified]], dfAdjFactors[[eachTickerModified]], dfDividendsSplitAdj[[eachTickerModified]], intrinioApiKey, snowflakeConnection) 
                else: 
                    details = calcOptionDetails(eachPosition, dfPricesSplitAdj[[eachTickerModified, benchmarkTicker]], dfPricesFinalNonAdj[[eachTickerModified, benchmarkTicker]], dfAdjFactors[[eachTickerModified, benchmarkTicker]], dfDividendsSplitAdj[[eachTickerModified, benchmarkTicker]], intrinioApiKey, snowflakeConnection) 
                dictPositionsDetailsOutput[position_id] = pd.Series(details).fillna('NA').to_dict()
                dictPositionsDetailsOutput[position_id]["detailsAvailable"] = True
            elif eachPosition['Ticker type'].lower() == 'equity': 
                if benchmarkTicker == eachTickerModified: 
                    details = calcEquityDetails(eachPosition, dfPricesSplitAdj[[eachTickerModified]], dfPricesFinalNonAdj[[eachTickerModified]], dfAdjFactors[[eachTickerModified]], dfDividendsSplitAdj[[eachTickerModified]], intrinioApiKey, snowflakeConnection) 
                else: 
                    details = calcEquityDetails(eachPosition, dfPricesSplitAdj[[eachTickerModified, benchmarkTicker]], dfPricesFinalNonAdj[[eachTickerModified, benchmarkTicker]], dfAdjFactors[[eachTickerModified, benchmarkTicker]], dfDividendsSplitAdj[[eachTickerModified, benchmarkTicker]], intrinioApiKey, snowflakeConnection) 
                dictPositionsDetailsOutput[position_id] = pd.Series(details).fillna('NA').to_dict()
                dictPositionsDetailsOutput[position_id]["detailsAvailable"] = True
            else:
                details = None
                dictPositionsDetailsOutput[position_id]["detailsAvailable"] = True

        except Exception as e:
            # If there's an error or processing fails for a position
            dictPositionsDetailsOutput[position_id] = {"detailsAvailable": False}

    jsonPositionsDetailsOutput = json.dumps(dictPositionsDetailsOutput)
    return jsonPositionsDetailsOutput
