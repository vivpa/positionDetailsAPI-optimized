import datetime as dt 
import intrinio_sdk as intrinio 
import numpy as np 
import json 
import pandas as pd 
import requests 
import snowflake.connector 

from functions.calcEquityDetails import calcEquityDetails 
from functions.calcOptionDetails import calcOptionDetails 
from functions.getLatestWeekday import getLatestWeekday 
from functions.getSecretsIntrinioApiKey import getSecretsIntrinioApiKey 
from functions.getSecretsSnowflake import getSecretsSnowflake 
from functions.readCsvFromS3 import readCsvFromS3 
from functions.retrieveIntrinioStockPricesAndDividends import retrieveIntrinioStockPricesAndDividends 

def calcPositionsDetails(jsonPositionsDetailsInput): 
    dictPositionsDetailsInput = json.loads(jsonPositionsDetailsInput) 
    dfInstrumentsDetails = pd.DataFrame(dictPositionsDetailsInput['dfInstrumentsDetails']).T 
    
    lstAllTickers = [dfInstrumentsDetails.loc['Ticker symbol', eachColumn] for eachColumn in dfInstrumentsDetails.columns] 
    
    i = 0 
    lstAllTickersRevised = [] 
    for eachTicker in lstAllTickers: 
        if ' ' in eachTicker: 
            eachTickerModified = eachTicker.split(' ')[0] 
        elif '_' in eachTicker: 
            eachTickerModified = eachTicker.split('_')[0] 
        elif dfInstrumentsDetails.loc['Ticker type'].iloc[i].lower() == 'option': 
            eachTickerModified = eachTicker[: (len(eachTicker) - 15)] 
        else: 
            eachTickerModified = eachTicker 
        
        lstAllTickersRevised.append(eachTickerModified) 

        i = i + 1 
    
    lstAllTickersRevised = list(np.unique(lstAllTickersRevised)) 

    benchmarkTicker = 'SPY' 
    if benchmarkTicker not in lstAllTickersRevised: 
        lstAllTickersRevised.append(benchmarkTicker)
    
    intrinioApiKey = getSecretsIntrinioApiKey() 
    intrinio.ApiClient().set_api_key(intrinioApiKey) 
    intrinio.ApiClient().allow_retries(True)
    
    # strAllTickersRevised = ','.join(lstAllTickersRevised) 
    # # f'https://api-v2.intrinio.com/securities/search?query={strAllTickersRevised}&api_key={intrinioApiKey}' 
    
    # url = "https://api-v2.intrinio.com/securities/search"
    # params = {
    #     "query": strAllTickersRevised, 
    #     "api_key": intrinioApiKey, 
    #     # "source": "uscomp", 
    # }

    # try:
    #     response = requests.get(url, params=params)
    #     response.raise_for_status()  # Raises an error for bad status codes
    #     data = response.json()
        
    #     # Extract and print ticker and name for each security
    #     for security in data.get("securities", []):
    #         print(f"Ticker: {security['ticker']}, Name: {security['name']}")
    # except requests.exceptions.RequestException as e:
    #     print(f"Error: {e}")
    
    # url = "https://api-v2.intrinio.com/securities/snapshots"
    # params = {
    #     "tickers": strAllTickersRevised,
    #     "api_key": intrinioApiKey,
    #     # "source": "iex"  # Optional: specify 'iex', 'multi_exchange', or 'delayed_sip'
    # }

    # try:
    #     response = requests.get(url, params=params)
    #     response.raise_for_status()  # Raises an error for bad status codes
    #     data = response.json()
        
    #     # Extract and print ticker and last price for each security
    #     for snapshot in data.get("snapshots", []):
    #         ticker = snapshot.get("security", {}).get("ticker", "N/A")
    #         last_price = snapshot.get("market", {}).get("last_price", "N/A")
    #         print(f"Ticker: {ticker}, Last Price: ${last_price}")
    # except requests.exceptions.RequestException as e:
    #     print(f"Error: {e}")
    
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
    
    # Collating all the option tickers 
    lstOptionTickers = [] 
    for eachColumn in dfInstrumentsDetails.columns: 
        if dfInstrumentsDetails.loc['Ticker type', eachColumn].lower() == 'option': 
            lstOptionTickers = lstOptionTickers + [dfInstrumentsDetails.loc['Ticker symbol', eachColumn]] 
    
    # Getting Intrinio details for all the option tickers in bulk 
    # Build request 
    url = "https://api-v2.intrinio.com/options/prices/realtime/batch"
    
    headers = { 
        "Accept": "application/json", 
        "Content-Type": "application/json", 
        "Authorization": f'Bearer {intrinioApiKey}' 
    } 
    
    params = {
        "source": "delayed", 
        "show_stats": "true", 
        "stock_price_source": "bats_delayed", 
        "model": "black_scholes", 
        "show_extended_price": "true", 
        "api_key": intrinioApiKey 
    }
    
    body = {
        "contracts": lstOptionTickers
    }
    
    # Call the API
    responseOptionPrices = requests.post( 
        url, 
        headers = headers, 
        params = params, 
        json = body, 
        # Use Bearer Token in header or querystring for authorization https://docs.intrinio.com/documentation/api_v2/authentication
    )
    
    responseOptionPrices.raise_for_status()
    dictOptionPrices = responseOptionPrices.json()
    
    # Inspect results
    for eachPosition in dictOptionPrices["contracts"]:
        # Fixed the way the contract was pulled
        contract = eachPosition["option"]["code"] 
        lastPrice = eachPosition["price"]["last"] 
        delta = eachPosition.get("stats", {}).get("delta") 
        print(f"{contract}: last = {lastPrice}, delta = {delta}") 

    # Extracting the dividends and earnings details for all tickers 
    bucket = 'plasmaartifact' 
    folder = 'security_classification' 
    filenameEarnings = 'wsh_earnings.csv' 
    filenameDividends = 'wsh_dividends.csv' 

    lstRowsEarnings = readCsvFromS3(bucket, folder, filenameEarnings) 
    lstRowsDividends = readCsvFromS3(bucket, folder, filenameDividends) 

    dfEarnings = pd.DataFrame(lstRowsEarnings[1:], columns = lstRowsEarnings[0]) 
    dfDividends = pd.DataFrame(lstRowsDividends[1:], columns = lstRowsDividends[0]) 

    dfEarningsSelectedTickers = pd.DataFrame() 
    dfDividendsSelectedTickers = pd.DataFrame() 
    for eachTicker in lstAllTickersRevised: 
        if eachTicker in list(dfEarnings['TICKER']): 
            if dfEarningsSelectedTickers.empty: 
                dfEarningsSelectedTickers = dfEarnings[dfEarnings['TICKER'] == eachTicker] 
            else: 
                dfEarningsSelectedTickers = pd.concat([dfEarningsSelectedTickers, dfEarnings[dfEarnings['TICKER'] == eachTicker]], ignore_index = True) 
            
        if eachTicker in list(dfDividends['TICKER']): 
            if dfDividendsSelectedTickers.empty: 
                dfDividendsSelectedTickers = dfDividends[dfDividends['TICKER'] == eachTicker] 
            else: 
                dfDividendsSelectedTickers = pd.concat([dfDividendsSelectedTickers, dfDividends[dfDividends['TICKER'] == eachTicker]], ignore_index = True) 
    
    # Calculating the position details for all the tickers 
    dictPositionsDetailsOutput = {} 
    for eachColumn in dfInstrumentsDetails.columns: 
        eachPosition = dfInstrumentsDetails[eachColumn]
        position_id = str(eachPosition['position_detail_id'])
        eachTicker = eachPosition['Ticker symbol'] 

        print(f"Position ticker: {dfInstrumentsDetails.loc['Ticker symbol', eachColumn]}") 
        
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
        
        if eachPosition['Ticker type'].lower() == 'option': 
            if benchmarkTicker == eachTickerModified: 
                dictPositionsDetailsOutput[position_id] = calcOptionDetails(eachPosition, dictOptionPrices, dfPricesSplitAdj[[eachTickerModified]], dfPricesFinalNonAdj[[eachTickerModified]], dfAdjFactors[[eachTickerModified]], dfDividendsSplitAdj[[eachTickerModified]], dfEarningsSelectedTickers, dfDividendsSelectedTickers, intrinioApiKey, snowflakeConnection) 
            else: 
                dictPositionsDetailsOutput[position_id] = calcOptionDetails(eachPosition, dictOptionPrices, dfPricesSplitAdj[[eachTickerModified, benchmarkTicker]], dfPricesFinalNonAdj[[eachTickerModified, benchmarkTicker]], dfAdjFactors[[eachTickerModified, benchmarkTicker]], dfDividendsSplitAdj[[eachTickerModified, benchmarkTicker]], dfEarningsSelectedTickers, dfDividendsSelectedTickers, intrinioApiKey, snowflakeConnection) 
        elif eachPosition['Ticker type'].lower() == 'equity': 
            if benchmarkTicker == eachTickerModified: 
                dictPositionsDetailsOutput[position_id] = calcEquityDetails(eachPosition, dfPricesSplitAdj[[eachTickerModified]], dfPricesFinalNonAdj[[eachTickerModified]], dfAdjFactors[[eachTickerModified]], dfDividendsSplitAdj[[eachTickerModified]], dfEarningsSelectedTickers, dfDividendsSelectedTickers, intrinioApiKey, snowflakeConnection) 
            else: 
                dictPositionsDetailsOutput[position_id] = calcEquityDetails(eachPosition, dfPricesSplitAdj[[eachTickerModified, benchmarkTicker]], dfPricesFinalNonAdj[[eachTickerModified, benchmarkTicker]], dfAdjFactors[[eachTickerModified, benchmarkTicker]], dfDividendsSplitAdj[[eachTickerModified, benchmarkTicker]], dfEarningsSelectedTickers, dfDividendsSelectedTickers, intrinioApiKey, snowflakeConnection) 
        elif eachPosition['Ticker type'].lower() == 'other': 
            dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False } 
    
    # Convert each entry to dict and fill NAs
    dictPositionsDetailsOutputRevised = {
        key: pd.Series(value).fillna('NA').to_dict() for key, value in dictPositionsDetailsOutput.items()
    }

    jsonPositionsDetailsOutput = json.dumps(dictPositionsDetailsOutputRevised)

    return jsonPositionsDetailsOutput
