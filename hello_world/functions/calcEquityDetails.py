import datetime as dt 
import intrinio_sdk as intrinio 
import numpy as np 
import pandas as pd 
import requests 

from functions.calcRsi import calcRsi 
from functions.calcImpliedVol import calcImpliedVol 
from functions.getLatestWeekday import getLatestWeekday 
from functions.getSecretsSnowflake import getSecretsSnowflake 
from functions.retrieveIntrinioStockPrices import retrieveIntrinioStockPrices 

def calcEquityDetails(serPositionsDetailsInput, intrinioApiKey, snowflakeConnection): 
    dictDetailsOutput = {} 
    
    # Getting prices for the stock or ETF 
    # If the underlying is a stock or an ETF, prices are obtained through SecurityApi() 
    startDate = (dt.datetime.now() - dt.timedelta(days = 7)).strftime('%Y-%m-%d') 
    endDate = dt.datetime.now().strftime('%Y-%m-%d') 
    frequency = 'daily' 
    pageSize = 100 
    nextPage = '' 
    
    responseSecurityPrices = intrinio.SecurityApi().get_security_stock_prices(serPositionsDetailsInput['Ticker symbol'], start_date = startDate, end_date = endDate, frequency = frequency, page_size = pageSize, next_page = nextPage) 
    dictResponseSecurityPrices = responseSecurityPrices.to_dict() 
    
    dictDetailsOutput['Name'] = dictResponseSecurityPrices['security']['name'] 
    
    dfStockPrices = pd.DataFrame(dictResponseSecurityPrices['stock_prices']) 
    maxDate = dfStockPrices['date'].max() 
    
    dictDetailsOutput['Last price'] = dfStockPrices[dfStockPrices['date'] == maxDate]['close'].iloc[0] 
    dictDetailsOutput['Open'] = dfStockPrices[dfStockPrices['date'] == maxDate]['open'].iloc[0] 
    dictDetailsOutput['High'] = dfStockPrices[dfStockPrices['date'] == maxDate]['high'].iloc[0] 
    dictDetailsOutput['Low'] = dfStockPrices[dfStockPrices['date'] == maxDate]['low'].iloc[0] 
    dictDetailsOutput['Price change'] = dfStockPrices[dfStockPrices['date'] == maxDate]['percent_change'].iloc[0] 
    dictDetailsOutput['52 week high'] = dfStockPrices[dfStockPrices['date'] == maxDate]['fifty_two_week_high'].iloc[0] 
    dictDetailsOutput['52 week low'] = dfStockPrices[dfStockPrices['date'] == maxDate]['fifty_two_week_low'].iloc[0] 
    
    responseEarnings = requests.get(f"https://api-v2.intrinio.com/securities/{serPositionsDetailsInput['Ticker symbol']}/earnings/latest?api_key={intrinioApiKey}") 
    dictResponseEarnings = responseEarnings.json() 
    if 'error' in dictResponseEarnings.keys(): 
        dictDetailsOutput['Next earnings date'] = 'NA' 
    else: 
        dictDetailsOutput['Next earnings date'] = dictResponseEarnings['next_earnings_date'] 
    
    responseDividends = requests.get(f"https://api-v2.intrinio.com/securities/{serPositionsDetailsInput['Ticker symbol']}/dividends/latest?api_key={intrinioApiKey}") 
    dictResponseDividends = responseDividends.json() 
    if 'error' in dictResponseDividends.keys(): 
        dictDetailsOutput['Next dividend ex date'] = 'NA' 
        dictDetailsOutput['Next dividend amount'] = 'NA' 
    else: 
        if dictResponseDividends['last_ex_dividend_date'] == None: 
            dictDetailsOutput['Next dividend ex date'] = 'NA' 
            dictDetailsOutput['Next dividend amount'] = 'NA' 
        else: 
            latestExDividendDate = dictResponseDividends['last_ex_dividend_date'] 
            if pd.to_datetime(latestExDividendDate, format = '%Y-%m-%d') > dt.datetime.now() - dt.timedelta(days = 1): 
                dictDetailsOutput['Next dividend ex date'] = dictResponseDividends['last_ex_dividend_date'] 
                dictDetailsOutput['Next dividend amount'] = dictResponseDividends['ex_dividend'] 
            else: 
                dictDetailsOutput['Next dividend ex date'] = 'NA' 
                dictDetailsOutput['Next dividend amount'] = 'NA' 
    
    # Extracting historical price data 
    numOfYearsForDataExtraction = 5 
    endDate = dt.datetime.now() 
    endDate = getLatestWeekday(endDate) 
    startDate = endDate - dt.timedelta(days = numOfYearsForDataExtraction * 365) 
    startDate = getLatestWeekday(startDate) 
    
    # Data for bebnchmark extracted to calculate the beta 
    # Needs to be made dynamic to deal with fixed income underlyings as well 
    benchmarkTicker = 'SPY' 
    dfPricesFinal = retrieveIntrinioStockPrices([serPositionsDetailsInput['Ticker symbol'], benchmarkTicker], startDate, endDate, 'adjclose', snowflakeConnection) 
    dfPricesFinal.index = pd.to_datetime(dfPricesFinal.index) 
    
    dfPricesFinalNonAdj, dfAdjFactors = retrieveIntrinioStockPrices([serPositionsDetailsInput['Ticker symbol'], benchmarkTicker], startDate, endDate, 'close', snowflakeConnection) 
    dfPricesFinalNonAdj.index = pd.to_datetime(dfPricesFinalNonAdj.index) 
    
    # Rebasing the non-adjusted prices to start from the startDate 
    dfPricesFinalNonAdj = dfPricesFinalNonAdj[dfPricesFinalNonAdj.index >= startDate].copy() 
    
    # Calculating the cumulative adjustment factors 
    dfCumuAdjFactors = dfAdjFactors.sort_index(ascending = False) 
    dfCumuAdjFactors = dfCumuAdjFactors.cumprod() 
    dfCumuAdjFactors = dfCumuAdjFactors.sort_index(ascending = True) 
    dfCumuAdjFactors = dfCumuAdjFactors.shift(-1).ffill() 
    
    # Calculating the split adjusted prices 
    dfPricesFinalSplitAdj = (dfPricesFinalNonAdj * dfCumuAdjFactors).dropna(how = 'all') 
    
    dfDividendsNonAdj = retrieveIntrinioStockPrices([serPositionsDetailsInput['Ticker symbol'], benchmarkTicker], startDate, endDate, 'dividend', snowflakeConnection) 
    
    # Calculating the split adjusted dividends 
    dfDividendsSplitAdj = (dfDividendsNonAdj * dfCumuAdjFactors).dropna(how = 'all') 
    
    # Calculation of the momentum indicators 
    dictDetailsOutput['SMA 20d'] = dfPricesFinal[serPositionsDetailsInput['Ticker symbol']].rolling(20).mean().iloc[-1] 
    dictDetailsOutput['SMA 50d'] = dfPricesFinal[serPositionsDetailsInput['Ticker symbol']].rolling(50).mean().iloc[-1] 
    dictDetailsOutput['RSI 14d'] = calcRsi(dfPricesFinal, serPositionsDetailsInput['Ticker symbol'], 14) 
    
    # Calculation of the volatility indicators 
    tickerSymbol = serPositionsDetailsInput['Ticker symbol'] 
    lastPrice = dfPricesFinal[tickerSymbol].iloc[-1] 
    dictDetailsOutput['1m implied volatility'] = calcImpliedVol(tickerSymbol, lastPrice, snowflakeConnection) 
    dictDetailsOutput['1m realized volatility'] = (np.log(dfPricesFinal[tickerSymbol] / dfPricesFinal[tickerSymbol].shift(1))).rolling(22).std().iloc[-1] * np.sqrt(252) 
    dictDetailsOutput['1m implied volatility premium'] = dictDetailsOutput['1m implied volatility'] - dictDetailsOutput['1m realized volatility'] 
    
    # Calculation of beta versus benchmark 
    dfReturns = (dfPricesFinal / dfPricesFinal.shift(1) - 1).dropna() 
    dfCovMatrix = dfReturns.cov() 
    dictDetailsOutput['Beta versus benchmark'] = dfCovMatrix.loc[serPositionsDetailsInput['Ticker symbol'], benchmarkTicker] / (dfReturns[benchmarkTicker].std() ** 2) 
    
    strLastDate = dfDividendsSplitAdj.sort_index(ascending = True).index[-1].strftime('%Y-%m-%d') 
    strSecondLastDate = dfDividendsSplitAdj.sort_index(ascending = True).index[-2].strftime('%Y-%m-%d') 
    dictDetailsOutput[f'Dividend on {strLastDate}'] = dfDividendsSplitAdj[serPositionsDetailsInput['Ticker symbol']].iloc[-1] 
    dictDetailsOutput[f'Dividend on {strSecondLastDate}'] = dfDividendsSplitAdj[serPositionsDetailsInput['Ticker symbol']].iloc[-2] 
    
    date1yAgo = endDate - dt.timedelta(days = 365) 
    dividends1y = dfDividendsSplitAdj[pd.to_datetime(dfDividendsSplitAdj.index) >= date1yAgo][serPositionsDetailsInput['Ticker symbol']].sum() 
    
    dictDetailsOutput['1y dividend yield'] = dividends1y / dictDetailsOutput['Last price'] 
    
    strLastDate = dfAdjFactors.sort_index(ascending = True).index[-1].strftime('%Y-%m-%d') 
    strSecondLastDate = dfAdjFactors.sort_index(ascending = True).index[-2].strftime('%Y-%m-%d') 
    splitFactorLastDate = dfAdjFactors[serPositionsDetailsInput['Ticker symbol']].ffill().iloc[-1] 
    splitFactorSecondLastDate = dfAdjFactors[serPositionsDetailsInput['Ticker symbol']].ffill().iloc[-2] 
    dictDetailsOutput[f'Split adjustment on {strLastDate}'] = 'None' if splitFactorLastDate == 1 else f'{int((1 / splitFactorLastDate) * 100) / 100} for 1 split' 
    dictDetailsOutput[f'Split adjustment on {strSecondLastDate}'] = 'None' if splitFactorSecondLastDate == 1 else f'{int((1 / splitFactorSecondLastDate) * 100) / 100} for 1 split' 
    
    return dictDetailsOutput 
