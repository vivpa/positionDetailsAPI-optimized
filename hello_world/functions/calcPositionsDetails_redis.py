import datetime as dt 
import intrinio_sdk as intrinio 
import numpy as np 
import json 
import pandas as pd 
import re 
import requests 
import snowflake.connector 
from typing import Dict, List, Any, Tuple
import time

from functions.calcEquityDetails import calcEquityDetails 
from functions.calcOptionDetails import calcOptionDetails 
from functions.getLatestWeekday import getLatestWeekday 
from functions.getSecretsIntrinioApiKey import getSecretsIntrinioApiKey 
from functions.getSecretsSnowflake import getSecretsSnowflake 
from functions.readCsvFromS3 import readCsvFromS3 
from functions.retrieveIntrinioStockPricesAndDividends import retrieveIntrinioStockPricesAndDividends 
from functions.snowflakeIdTestQuery import snowflakeIdTestQuery 
from functions.snowflakeIvolQueries import snowflakeIvolQueries 
from functions.financial_cache import financial_cache
from functions.async_api_client import fetch_all_data_sync

def calcPositionsDetails(jsonPositionsDetailsInput: str) -> str:
    """
    Redis-cached version of calcPositionsDetails with massive performance improvements
    """
    start_time = time.time()
    print(f"Starting Redis-cached calcPositionsDetails at {time.time()}")
    
    dictPositionsDetailsInput = json.loads(jsonPositionsDetailsInput) 
    dfInstrumentsDetails = pd.DataFrame(dictPositionsDetailsInput['dfInstrumentsDetails']).T 
    
    if 'Benchmark' not in list(dfInstrumentsDetails.columns): 
        dfInstrumentsDetails.loc['Benchmark'] = np.nan

    # Extract and process tickers more efficiently
    lstAllTickers = dfInstrumentsDetails.loc['Ticker symbol'].tolist()
    
    # Process option tickers more efficiently
    option_mask = dfInstrumentsDetails.loc['Ticker type'].str.lower() == 'option'
    dfInstrumentsDetails.loc[option_mask, 'Ticker symbol'] = dfInstrumentsDetails.loc[option_mask, 'Ticker symbol'].str.replace(' ', '')

    # Extract underlying tickers more efficiently
    lstAllTickersRevised = []
    for i, eachTicker in enumerate(lstAllTickers):
        if ' ' in eachTicker: 
            eachTickerModified = eachTicker.split(' ')[0] 
        elif '_' in eachTicker: 
            eachTickerModified = eachTicker.split('_')[0] 
        elif dfInstrumentsDetails.loc['Ticker type'].iloc[i].lower() == 'option': 
            eachTickerModified = eachTicker[: (len(eachTicker) - 15)] 
        else: 
            eachTickerModified = eachTicker 
        
        lstAllTickersRevised.append(eachTickerModified) 
    
    lstAllTickersRevised = list(np.unique(lstAllTickersRevised))
    
    # Remove empty tickers
    lstAllTickersRevised = [t for t in lstAllTickersRevised if t and t != ' ']
    
    # Add benchmark tickers
    lstAllBenchmarkTickersUnique = list(np.unique([
        'SPY' if pd.isna(dfInstrumentsDetails.loc['Benchmark', col]) 
        else dfInstrumentsDetails.loc['Benchmark', col] 
        for col in dfInstrumentsDetails.columns
    ]))
    
    for ticker in lstAllBenchmarkTickersUnique:
        if ticker not in lstAllTickersRevised:
            lstAllTickersRevised.append(ticker)

    print(f"Ticker processing completed in {time.time() - start_time:.2f}s")

    # Get API credentials
    intrinioApiKey = getSecretsIntrinioApiKey() 
    intrinio.ApiClient().set_api_key(intrinioApiKey) 
    intrinio.ApiClient().allow_retries(True)
    
    # Get Snowflake credentials
    strLoginName, strPassword, strWarehouse, strAccount = getSecretsSnowflake() 
    
    # Check cache for historical data first
    numOfYearsForDataExtraction = 2  # Reduced from 5 years
    endDate = getLatestWeekday(dt.datetime.now()) 
    startDate = getLatestWeekday(endDate - dt.timedelta(days=numOfYearsForDataExtraction * 365)) 
    
    start_date_str = startDate.strftime('%Y-%m-%d')
    end_date_str = endDate.strftime('%Y-%m-%d')
    
    cached_historical_data = financial_cache.get_historical_data(lstAllTickersRevised, start_date_str, end_date_str)
    
    if cached_historical_data:
        print("✅ Using cached historical data")
        dfPricesSplitAdj = pd.DataFrame(cached_historical_data['prices_split_adj'])
        dfPricesFinalNonAdj = pd.DataFrame(cached_historical_data['prices_final_non_adj'])
        dfAdjFactors = pd.DataFrame(cached_historical_data['adj_factors'])
        dfDividendsNonAdj = pd.DataFrame(cached_historical_data['dividends_non_adj'])
        
        # Convert index back to datetime
        dfPricesSplitAdj.index = pd.to_datetime(dfPricesSplitAdj.index)
        dfPricesFinalNonAdj.index = pd.to_datetime(dfPricesFinalNonAdj.index)
    else:
        print("❌ Fetching fresh historical data from Snowflake")
        ctx = snowflake.connector.connect(
            user=strLoginName, 
            password=strPassword, 
            warehouse="BACKTEST_LARGE_WH", 
            account=strAccount
        ) 
        snowflakeConnection = ctx.cursor() 
        
        dfPricesSplitAdj, dfPricesFinalNonAdj, dfAdjFactors, dfDividendsNonAdj = retrieveIntrinioStockPricesAndDividends(
            lstAllTickersRevised, startDate, endDate, snowflakeConnection
        ) 
        
        # Cache the data
        historical_data = {
            'prices_split_adj': dfPricesSplitAdj.to_dict(),
            'prices_final_non_adj': dfPricesFinalNonAdj.to_dict(),
            'adj_factors': dfAdjFactors.to_dict(),
            'dividends_non_adj': dfDividendsNonAdj.to_dict()
        }
        financial_cache.set_historical_data(lstAllTickersRevised, start_date_str, end_date_str, historical_data, ttl_hours=4)
        
        ctx.close()

    print(f"Historical data processing completed in {time.time() - start_time:.2f}s")

    # Process data more efficiently
    dfPricesSplitAdj = dfPricesSplitAdj.ffill() 
    dfPricesFinalNonAdj = dfPricesFinalNonAdj.ffill() 
    dfAdjFactors = dfAdjFactors.fillna(1) 
    dfDividendsNonAdj = dfDividendsNonAdj.ffill() 
    
    dfPricesSplitAdj.index = pd.to_datetime(dfPricesSplitAdj.index) 
    dfPricesFinalNonAdj.index = pd.to_datetime(dfPricesFinalNonAdj.index) 
    
    dfCumuAdjFactors = dfAdjFactors.sort_index(ascending=False).cumprod().sort_index(ascending=True).shift(-1).ffill() 
    dfDividendsSplitAdj = (dfDividendsNonAdj * dfCumuAdjFactors).dropna(how='all') 
    
    # Extract option tickers more efficiently
    option_mask = dfInstrumentsDetails.loc['Ticker type'].str.lower() == 'option'
    lstOptionTickers = dfInstrumentsDetails.loc[option_mask, 'Ticker symbol'].tolist()
    
    print(f"Data processing completed in {time.time() - start_time:.2f}s")

    # Check cache for external API data
    cached_quotes = financial_cache.get_api_quotes(lstAllTickersRevised)
    cached_options = financial_cache.get_options_data(lstOptionTickers)
    
    if cached_quotes and cached_options:
        print("✅ Using cached API data")
        quotes_data = cached_quotes
        options_data = cached_options
    else:
        print("❌ Fetching fresh API data")
        api_start = time.time()
        quotes_data, options_data = fetch_all_data_sync(intrinioApiKey, lstAllTickersRevised, lstOptionTickers)
        print(f"External API calls completed in {time.time() - api_start:.2f}s")
        
        # Cache the API data
        financial_cache.set_api_quotes(lstAllTickersRevised, quotes_data, ttl_minutes=15)
        financial_cache.set_options_data(lstOptionTickers, options_data, ttl_minutes=15)

    print(f"External API processing completed in {time.time() - start_time:.2f}s")

    # Check cache for earnings and dividends data
    cached_earnings = financial_cache.get_earnings_dividends('earnings')
    cached_dividends = financial_cache.get_earnings_dividends('dividends')
    
    if cached_earnings and cached_dividends:
        print("✅ Using cached earnings and dividends data")
        dfEarnings = pd.DataFrame(cached_earnings)
        dfDividends = pd.DataFrame(cached_dividends)
    else:
        print("❌ Fetching fresh earnings and dividends data")
        bucket = 'plasmaartifact' 
        folder = 'security_classification' 
        filenameEarnings = 'wsh_earnings.csv' 
        filenameDividends = 'wsh_dividends.csv' 

        lstRowsEarnings = readCsvFromS3(bucket, folder, filenameEarnings) 
        lstRowsDividends = readCsvFromS3(bucket, folder, filenameDividends) 

        dfEarnings = pd.DataFrame(lstRowsEarnings[1:], columns=lstRowsEarnings[0]) 
        dfDividends = pd.DataFrame(lstRowsDividends[1:], columns=lstRowsDividends[0])
        
        # Cache the data
        financial_cache.set_earnings_dividends('earnings', dfEarnings.to_dict(), ttl_hours=24)
        financial_cache.set_earnings_dividends('dividends', dfDividends.to_dict(), ttl_hours=24)

    # Filter data more efficiently
    dfEarningsSelectedTickers = dfEarnings[dfEarnings['TICKER'].isin(lstAllTickersRevised)]
    dfDividendsSelectedTickers = dfDividends[dfDividends['TICKER'].isin(lstAllTickersRevised)]

    print(f"Earnings/dividends processing completed in {time.time() - start_time:.2f}s")

    # Calculate position details with optimized processing
    print("Calculating position details...")
    calc_start = time.time()
    
    dictPositionsDetailsOutput = {} 
    
    # Process positions in batches for better memory management
    batch_size = 5
    positions = list(dfInstrumentsDetails.columns)
    
    for i in range(0, len(positions), batch_size):
        batch = positions[i:i + batch_size]
        
        for eachColumn in batch:
            eachPosition = dfInstrumentsDetails[eachColumn]
            position_id = str(eachPosition['position_detail_id'])
            eachTicker = eachPosition['Ticker symbol'] 

            print(f"Processing position ticker: {eachTicker}") 
            
            # Extract underlying ticker more efficiently
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
            
            # Get benchmark ticker for this position
            benchmark_ticker = 'SPY' if pd.isna(eachPosition.get('Benchmark')) else eachPosition['Benchmark']
            
            if eachPosition['Ticker type'].lower() == 'option': 
                if benchmark_ticker == eachTickerModified: 
                    dictPositionsDetailsOutput[position_id] = calcOptionDetails(
                        eachPosition, options_data, 
                        dfPricesSplitAdj[[eachTickerModified]], 
                        dfPricesFinalNonAdj[[eachTickerModified]], 
                        dfAdjFactors[[eachTickerModified]], 
                        dfDividendsSplitAdj[[eachTickerModified]], 
                        list(quotes_data.values()), dfEarningsSelectedTickers, 
                        dfDividendsSelectedTickers, intrinioApiKey, None
                    ) 
                else: 
                    dictPositionsDetailsOutput[position_id] = calcOptionDetails(
                        eachPosition, options_data,
                        dfPricesSplitAdj[[eachTickerModified, benchmark_ticker]], 
                        dfPricesFinalNonAdj[[eachTickerModified, benchmark_ticker]], 
                        dfAdjFactors[[eachTickerModified, benchmark_ticker]], 
                        dfDividendsSplitAdj[[eachTickerModified, benchmark_ticker]], 
                        list(quotes_data.values()), dfEarningsSelectedTickers, 
                        dfDividendsSelectedTickers, intrinioApiKey, None
                    ) 
            elif eachPosition['Ticker type'].lower() == 'equity': 
                if benchmark_ticker == eachTickerModified: 
                    dictPositionsDetailsOutput[position_id] = calcEquityDetails(
                        eachPosition, dfPricesSplitAdj[[eachTickerModified]], 
                        dfPricesFinalNonAdj[[eachTickerModified]], 
                        dfAdjFactors[[eachTickerModified]], 
                        dfDividendsSplitAdj[[eachTickerModified]], 
                        list(quotes_data.values()), dfEarningsSelectedTickers, 
                        dfDividendsSelectedTickers, intrinioApiKey, None
                    ) 
                else: 
                    dictPositionsDetailsOutput[position_id] = calcEquityDetails(
                        eachPosition, dfPricesSplitAdj[[eachTickerModified, benchmark_ticker]], 
                        dfPricesFinalNonAdj[[eachTickerModified, benchmark_ticker]], 
                        dfAdjFactors[[eachTickerModified, benchmark_ticker]], 
                        dfDividendsSplitAdj[[eachTickerModified, benchmark_ticker]], 
                        list(quotes_data.values()), dfEarningsSelectedTickers, 
                        dfDividendsSelectedTickers, intrinioApiKey, None
                    ) 
            elif eachPosition['Ticker type'].lower() == 'other': 
                dictPositionsDetailsOutput[position_id] = {'detailsAvailable': False}

    print(f"Position calculations completed in {time.time() - calc_start:.2f}s")
    print(f"Total processing time: {time.time() - start_time:.2f}s")

    # Convert each entry to dict and fill NAs more efficiently
    dictPositionsDetailsOutputRevised = {}
    for key, value in dictPositionsDetailsOutput.items():
        if isinstance(value, dict):
            dictPositionsDetailsOutputRevised[key] = {k: (v if pd.notna(v) else 'NA') for k, v in value.items()}
        else:
            dictPositionsDetailsOutputRevised[key] = pd.Series(value).fillna('NA').to_dict()

    jsonPositionsDetailsOutput = json.dumps(dictPositionsDetailsOutputRevised)
    
    print(f"Total function execution time: {time.time() - start_time:.2f}s")
    return jsonPositionsDetailsOutput
