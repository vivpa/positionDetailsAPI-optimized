import datetime as dt 
import intrinio_sdk as intrinio 
import numpy as np 
import json 
import pandas as pd 
import re 
import requests 
import snowflake.connector 

from functions.calcEquityDetails import calcEquityDetails 
from functions.calcOptionDetails import calcOptionDetails 
from functions.getLatestWeekday import getLatestWeekday 
from functions.getSecretsIntrinioApiKey import getSecretsIntrinioApiKey 
from functions.getSecretsSnowflake import getSecretsSnowflake 
from functions.readCsvFromS3 import readCsvFromS3 
from functions.retrieveIntrinioStockPricesAndDividends import retrieveIntrinioStockPricesAndDividends 
from functions.snowflakeIdTestQuery import snowflakeIdTestQuery 
from functions.snowflakeIvolQueries import snowflakeIvolQueries 

def calcPositionsDetails(jsonPositionsDetailsInput): 
    dictPositionsDetailsInput = json.loads(jsonPositionsDetailsInput) 
    dfInstrumentsDetails = pd.DataFrame(dictPositionsDetailsInput['dfInstrumentsDetails']).T 
    
    if 'Benchmark' not in list(dfInstrumentsDetails.columns): 
        dfInstrumentsDetails.loc['Benchmark'] = np.nan 

    lstAllTickers = [dfInstrumentsDetails.loc['Ticker symbol', eachColumn] for eachColumn in dfInstrumentsDetails.columns] 
    
    # For all option tickers, remove spaces in the tickernames  
    for eachColumn in dfInstrumentsDetails.columns: 
        if dfInstrumentsDetails.loc['Ticker type', eachColumn].lower() == 'option': 
            if ' ' in dfInstrumentsDetails.loc['Ticker symbol', eachColumn]: 
                dfInstrumentsDetails.loc['Ticker symbol', eachColumn] = dfInstrumentsDetails.loc['Ticker symbol', eachColumn].replace(' ', '') 

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

    # Removing spurious tickers 
    if '' in lstAllTickersRevised: 
        lstAllTickersRevised.remove('') 
    if ' ' in lstAllTickersRevised: 
        lstAllTickersRevised.remove(' ') 
    
    lstAllBenchmarkTickersUnique =  list(np.unique([('SPY' if pd.isna(dfInstrumentsDetails.loc['Benchmark', eachColumn]) else dfInstrumentsDetails.loc['Benchmark', eachColumn]) for eachColumn in dfInstrumentsDetails.columns])) 

    for eachTicker in lstAllBenchmarkTickersUnique: 
        if eachTicker not in lstAllTickersRevised: 
            lstAllTickersRevised = lstAllTickersRevised + [eachTicker] 

    intrinioApiKey = getSecretsIntrinioApiKey() 
    intrinio.ApiClient().set_api_key(intrinioApiKey) 
    intrinio.ApiClient().allow_retries(True)
    
    strLoginName, strPassword, strWarehouse, strAccount = getSecretsSnowflake() 
    ctx = snowflake.connector.connect(user = strLoginName, password = strPassword, warehouse = "BACKTEST_LARGE_WH", account = strAccount) 
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
    
    dfCumuAdjFactors = dfAdjFactors.sort_index(ascending = False).cumprod().sort_index(ascending = True).shift(-1).ffill() 
    dfDividendsSplitAdj = (dfDividendsNonAdj * dfCumuAdjFactors).dropna(how='all') 
    
    # Collating all the option tickers 
    lstOptionTickers = [] 
    for eachColumn in dfInstrumentsDetails.columns: 
        if dfInstrumentsDetails.loc['Ticker type', eachColumn].lower() == 'option': 
            lstOptionTickers = lstOptionTickers + [dfInstrumentsDetails.loc['Ticker symbol', eachColumn]] 
    
    strAllTickersRevised = ','.join(lstAllTickersRevised) 
    
    url = f"https://api-v2.intrinio.com/stock_exchanges/USCOMP/quote?tickers={strAllTickersRevised}&api_key={intrinioApiKey}" 

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an error for bad status codes
        data = response.json() 
        
        # Extract and print ticker and last price for each security
        for eachItem in data['quotes']: 
            ticker = eachItem['security']['ticker'] 
            stockName = eachItem['security']['name'] 
            lastPrice = eachItem['last'] 
            print(f"Ticker: {ticker}; Name: {stockName}; Last price: ${lastPrice}") 
        
        lstPositionNamesAndPrices = data['quotes'] 
    except: 
        print(f"Could not extract quotes data for {strAllTickersRevised}") 
        
        lstPositionNamesAndPrices = [] 

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
    
    try: 
        if lstOptionTickers != []: 
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
        else: 
            dictOptionPrices = {} 

            print("No option tickers specified") 
    except: 
        dictOptionPrices = {} 

        print("Option tickers' data not extracted") 

    # Inspect results
    if dictOptionPrices != {}: 
        for eachPosition in dictOptionPrices["contracts"]:
            # Fixed the way the contract was pulled
            contract = eachPosition["option"]["code"] 
            lastPrice = eachPosition["price"]["last"] 
            delta = eachPosition.get("stats", {}).get("delta") 
            print(f"{contract}: last = {lastPrice}, delta = {delta}") 
    else: 
        print('No options data extracted') 
    
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
    
    # Calculating all equity tickers amongst the inputs 
    lstEquityTickers = [] 
    for eachColumn in dfInstrumentsDetails.columns: 
        eachPosition = dfInstrumentsDetails[eachColumn]
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
        
        if eachPosition['Ticker type'].lower() == 'equity': 
            lstEquityTickers = lstEquityTickers + [eachTickerModified] 
    
    if lstEquityTickers != []: 
        try: 
            dfSnowflakeIds, errorMessageStockIds = snowflakeIdTestQuery(lstEquityTickers, snowflakeConnection) 
        except: 
            dfSnowflakeIds, errorMessageStockIds = pd.DataFrame(), 'Stock IDs not found for any tickers' 
        
        print(errorMessageStockIds) 
        
        dfSnowflakeIds = dfSnowflakeIds[['STOCK_ID', 'SYMBOL']] 
    else: 
        errorMessageStockIds = 'Input does not contain any stocks' 

        print(errorMessageStockIds) 

        dfSnowflakeIds = pd.DataFrame() 

    startDate = (dt.datetime.now() - dt.timedelta(days = 30)).strftime("%Y%m%d") 
    endDate = dt.datetime.now().strftime("%Y%m%d") 

    if not dfSnowflakeIds.empty: 
        try: 
            dfImpliedVols1m, errorMessageImpliedVols = snowflakeIvolQueries(dfSnowflakeIds, lstEquityTickers, startDate, endDate, snowflakeConnection) 
        except: 
            dfImpliedVols1m, errorMessageImpliedVols = pd.DataFrame(), 'Implied volatilities not found for any tickers' 
    else: 
        dfImpliedVols1m = pd.DataFrame() 

        errorMessageImpliedVols = 'Input does not contain any stocks' 
    
    print(errorMessageImpliedVols) 

    # Calculating the position details for all the tickers 
    dictPositionsDetailsOutput = {} 
    lstPositionIds = dfInstrumentsDetails.loc['position_detail_id'].tolist() 
    for eachColumn in dfInstrumentsDetails.columns: 
        eachPosition = dfInstrumentsDetails[eachColumn]
        eachTicker = eachPosition['Ticker symbol'] 
        position_id = str(eachPosition['position_detail_id'])
        runPositionDetails = True 

        print(eachTicker) 

        # Checking that the ticker type is a string 
        if not isinstance(eachPosition['Ticker type'], str): 
            dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': 'Ticker type for position is not a string' } 

            runPositionDetails = False 
        
        # Checking that the ticker symbol is a string 
        if not isinstance(eachPosition['Ticker symbol'], str): 
            dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': 'Ticker for position is not a string' } 

            runPositionDetails = False 
        
        # Checking that the ticker symbol is not blank or NA 
        if eachPosition['Ticker symbol'].strip() == '' or pd.isna(eachPosition['Ticker symbol']): 
            dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': 'Ticker symbol for the position is blank' } 

            runPositionDetails = False 
        
        # Checking that position_detail_id's are not duplicate 
        if lstPositionIds.count(eachPosition['position_detail_id']) > 1: 
            dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': f'Multiple positions with position IDs {position_id}' } 

            runPositionDetails = False 
        
        # Checking that the ticker position is not a non-number 
        if not isinstance(eachPosition['Ticker position'], (int, float)): 
            dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': 'Ticker for position is not a string' } 

            runPositionDetails = False 
        
        # Checking that the ticker position is not negative 
        if eachPosition['Ticker position'] < 0: 
            dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': 'Ticker for position is negative' } 

            runPositionDetails = False 
        
        if eachPosition['Option trade date'] != 'NA' and eachPosition['Option trade date'] != None: 
            # Checking that the option trade date is a string 
            if not isinstance(eachPosition['Option trade date'], str): 
                dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': 'Option trade date is not a string' } 

                runPositionDetails = False 
        
            # Checking that the option trade date is in the correct format 
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', eachPosition['Option trade date']): 
                dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': "Option trade date not in the 'YYYY-MM-DD' format" } 

                runPositionDetails = False 
        
            # Checking that the option trade date is valid 
            try: 
                dt.datetime.strptime(eachPosition['Option trade date'], '%Y-%m-%d') 

                runPositionDetails = True 
            except: 
                dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': "Option trade date not in a valid date" } 

                runPositionDetails = False 
        
        if eachPosition['Option entry price'] != 'NA': 
            # Checking that the option entry price is a number 
            if not isinstance(eachPosition['Option entry price'], (int, float)): 
                dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': "Option entry price is not 'NA' or a number" } 

                runPositionDetails = False 
            else: 
                # If option entry price is a number, checking that it is positive 
                if eachPosition['Option entry price'] < 0: 
                    dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': "Option entry price is less than 0" } 

                    runPositionDetails = False 
        
        # Checking that the position_detail_id is a string 
        if not isinstance(eachPosition['position_detail_id'], str): 
            dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': "Position detail ID for position is not a string" } 

            runPositionDetails = False 
        
        # Checking that the position_detail_id is not blank 
        if eachPosition['position_detail_id'].strip() == '': 
            dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': "Position detail ID for position is blank" } 

            runPositionDetails = False 

        if eachPosition['Underlying position'] != 'NA': 
            # Checking that the underlying position is a number 
            if not isinstance(eachPosition['Underlying position'], (int, float)): 
                dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': "Underlying position is not 'NA' or a number" } 

                runPositionDetails = False 
            else: 
                # Checking that the underlying position is positive 
                if eachPosition['Underlying position'] < 0: 
                    dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': "Underlying position is less than 0" } 

                    runPositionDetails = False 
        
        if runPositionDetails == True: 
            benchmarkTicker = 'SPY' if pd.isna(dfInstrumentsDetails.loc['Benchmark', eachColumn]) else dfInstrumentsDetails.loc['Benchmark', eachColumn] 

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
            
            if eachPosition['Ticker type'].lower() not in ['equity', 'option', 'other']: 
                dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': "Position type should be one of 'equity', 'option' or 'other'" } 
            elif eachPosition['Ticker type'].lower() == 'option': 
                # Check if required columns exist in DataFrames
                if eachTickerModified not in dfPricesSplitAdj.columns:
                    dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': f'Price data not available for ticker: {eachTickerModified}' }
                elif benchmarkTicker == eachTickerModified: 
                    # Get available columns for the ticker
                    available_cols_prices = [col for col in [eachTickerModified] if col in dfPricesSplitAdj.columns]
                    available_cols_final = [col for col in [eachTickerModified] if col in dfPricesFinalNonAdj.columns]
                    available_cols_adj = [col for col in [eachTickerModified] if col in dfAdjFactors.columns]
                    available_cols_div = [col for col in [eachTickerModified] if col in dfDividendsSplitAdj.columns]
                    
                    try: 
                        dictPositionsDetailsOutput[position_id] = calcOptionDetails(eachPosition, dictOptionPrices, dfPricesSplitAdj[available_cols_prices], dfPricesFinalNonAdj[available_cols_final], dfAdjFactors[available_cols_adj], dfDividendsSplitAdj[available_cols_div], lstPositionNamesAndPrices, dfEarningsSelectedTickers, dfDividendsSelectedTickers, intrinioApiKey, snowflakeConnection) 
                    except: 
                        dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': 'Data not extracted for position' } 
                else: 
                    # Check if both tickers exist
                    required_tickers = [eachTickerModified, benchmarkTicker]
                    missing_tickers = [ticker for ticker in required_tickers if ticker not in dfPricesSplitAdj.columns]
                    
                    if missing_tickers:
                        dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': f'Price data not available for tickers: {", ".join(missing_tickers)}' }
                    else:
                        # Get available columns for both tickers
                        available_cols_prices = [col for col in required_tickers if col in dfPricesSplitAdj.columns]
                        available_cols_final = [col for col in required_tickers if col in dfPricesFinalNonAdj.columns]
                        available_cols_adj = [col for col in required_tickers if col in dfAdjFactors.columns]
                        available_cols_div = [col for col in required_tickers if col in dfDividendsSplitAdj.columns]
                        
                        try: 
                            dictPositionsDetailsOutput[position_id] = calcOptionDetails(eachPosition, dictOptionPrices, dfPricesSplitAdj[available_cols_prices], dfPricesFinalNonAdj[available_cols_final], dfAdjFactors[available_cols_adj], dfDividendsSplitAdj[available_cols_div], lstPositionNamesAndPrices, dfEarningsSelectedTickers, dfDividendsSelectedTickers, intrinioApiKey, snowflakeConnection) 
                        except: 
                            dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': 'Data not extracted for position' } 
            elif eachPosition['Ticker type'].lower() == 'equity': 
                # Check if required columns exist in DataFrames
                if eachTickerModified not in dfPricesSplitAdj.columns:
                    dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': f'Price data not available for ticker: {eachTickerModified}' }
                elif benchmarkTicker == eachTickerModified: 
                    # Get available columns for the ticker
                    available_cols_prices = [col for col in [eachTickerModified] if col in dfPricesSplitAdj.columns]
                    available_cols_final = [col for col in [eachTickerModified] if col in dfPricesFinalNonAdj.columns]
                    available_cols_adj = [col for col in [eachTickerModified] if col in dfAdjFactors.columns]
                    available_cols_div = [col for col in [eachTickerModified] if col in dfDividendsSplitAdj.columns]
                    
                    try: 
                        dictPositionsDetailsOutput[position_id] = calcEquityDetails(eachPosition, dfImpliedVols1m, dfPricesSplitAdj[available_cols_prices], dfPricesFinalNonAdj[available_cols_final], dfAdjFactors[available_cols_adj], dfDividendsSplitAdj[available_cols_div], lstPositionNamesAndPrices, dfEarningsSelectedTickers, dfDividendsSelectedTickers, intrinioApiKey, snowflakeConnection) 
                    except: 
                        dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': 'Data not extracted for position' } 
                else: 
                    # Check if both tickers exist
                    required_tickers = [eachTickerModified, benchmarkTicker]
                    missing_tickers = [ticker for ticker in required_tickers if ticker not in dfPricesSplitAdj.columns]
                    
                    if missing_tickers:
                        dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': f'Price data not available for tickers: {", ".join(missing_tickers)}' }
                    else:
                        # Get available columns for both tickers
                        available_cols_prices = [col for col in required_tickers if col in dfPricesSplitAdj.columns]
                        available_cols_final = [col for col in required_tickers if col in dfPricesFinalNonAdj.columns]
                        available_cols_adj = [col for col in required_tickers if col in dfAdjFactors.columns]
                        available_cols_div = [col for col in required_tickers if col in dfDividendsSplitAdj.columns]
                        
                        try: 
                            dictPositionsDetailsOutput[position_id] = calcEquityDetails(eachPosition, dfImpliedVols1m, dfPricesSplitAdj[available_cols_prices], dfPricesFinalNonAdj[available_cols_final], dfAdjFactors[available_cols_adj], dfDividendsSplitAdj[available_cols_div], lstPositionNamesAndPrices, dfEarningsSelectedTickers, dfDividendsSelectedTickers, intrinioApiKey, snowflakeConnection) 
                        except: 
                            dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': 'Data not extracted for position' } 
            elif eachPosition['Ticker type'].lower() == 'other': 
                dictPositionsDetailsOutput[position_id] = { 'detailsAvailable': False, 'errorMessage': 'Ticker is not a listed equity or option' } 
    
    # Convert each entry to dict and fill NAs
    dictPositionsDetailsOutputRevised = {
        key: pd.Series(value).fillna('NA').to_dict() for key, value in dictPositionsDetailsOutput.items()
    }

    jsonPositionsDetailsOutput = json.dumps(dictPositionsDetailsOutputRevised)

    return jsonPositionsDetailsOutput
