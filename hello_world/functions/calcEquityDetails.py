import datetime as dt 
import intrinio_sdk as intrinio 
import numpy as np 
import pandas as pd 
import requests 

from functions.calcRsi import calcRsi 
from functions.calcImpliedVol import calcImpliedVol 
from functions.getLatestWeekday import getLatestWeekday 

def calcEquityDetails(serPositionsDetailsInput, dfPricesSplitAdj, dfPricesFinalNonAdj, dfAdjFactors, dfDividendsSplitAdj, intrinioApiKey, snowflakeConnection): 
    benchmarkTicker = 'SPY' 
    
    # Getting prices for the stock or ETF 
    # If the underlying is a stock or an ETF, prices are obtained through SecurityApi() 
    startDate = (dt.datetime.now() - dt.timedelta(days = 7)).strftime('%Y-%m-%d') 
    endDate = dt.datetime.now().strftime('%Y-%m-%d') 
    frequency = 'daily' 
    pageSize = 100 
    nextPage = '' 
    
    try: 
        responseEquityPrices = intrinio.SecurityApi().get_security_stock_prices(serPositionsDetailsInput['Ticker symbol'], start_date = startDate, end_date = endDate, frequency = frequency, page_size = pageSize, next_page = nextPage) 
    except: 
        return { "detailsAvailable": False } 
    
    dictResponseEquityPrices = responseEquityPrices.to_dict() 
    
    print(f"Response for {serPositionsDetailsInput.loc['Ticker symbol']}: {responseEquityPrices}") 

    dictDetailsOutput = {} 
    
    dictDetailsOutput['Name'] = dictResponseEquityPrices['security']['name'] 
    
    dfStockPrices = pd.DataFrame(dictResponseEquityPrices['stock_prices']) 
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
        latestExDividendDate = dictResponseDividends['last_ex_dividend_date'] 
        if pd.to_datetime(latestExDividendDate, format = '%Y-%m-%d') > dt.datetime.now() - dt.timedelta(days = 1): 
            dictDetailsOutput['Next dividend ex date'] = dictResponseDividends['last_ex_dividend_date'] 
            dictDetailsOutput['Next dividend amount'] = dictResponseDividends['ex_dividend'] 
        else: 
            dictDetailsOutput['Next dividend ex date'] = 'NA' 
            dictDetailsOutput['Next dividend amount'] = 'NA' 
    
    endDate = dt.datetime.now() 
    endDate = getLatestWeekday(endDate) 
    
    # Calculation of the momentum indicators 
    dictDetailsOutput['SMA 20d'] = dfPricesSplitAdj[serPositionsDetailsInput['Ticker symbol']].rolling(20).mean().iloc[-1] 
    dictDetailsOutput['SMA 50d'] = dfPricesSplitAdj[serPositionsDetailsInput['Ticker symbol']].rolling(50).mean().iloc[-1] 
    dictDetailsOutput['RSI 1 week'] = calcRsi(dfPricesSplitAdj, serPositionsDetailsInput['Ticker symbol'], 5) 
    dictDetailsOutput['RSI 2 weeks'] = calcRsi(dfPricesSplitAdj, serPositionsDetailsInput['Ticker symbol'], 10) 
    dictDetailsOutput['RSI 1 month'] = calcRsi(dfPricesSplitAdj, serPositionsDetailsInput['Ticker symbol'], 22) 
    
    # Calculation of the volatility indicators 
    tickerSymbol = serPositionsDetailsInput['Ticker symbol'] 
    lastPrice = dfPricesSplitAdj[tickerSymbol].iloc[-1] 
    dictDetailsOutput['1m implied volatility'] = calcImpliedVol(tickerSymbol, lastPrice, snowflakeConnection) 
    dictDetailsOutput['1m realized volatility'] = (np.log(dfPricesSplitAdj[tickerSymbol] / dfPricesSplitAdj[tickerSymbol].shift(1))).rolling(22).std().iloc[-1] * np.sqrt(252) 
    dictDetailsOutput['1m implied volatility premium'] = dictDetailsOutput['1m implied volatility'] - dictDetailsOutput['1m realized volatility'] 
    
    # Calculation of beta versus benchmark 
    dfReturns = (dfPricesSplitAdj / dfPricesSplitAdj.shift(1) - 1).dropna() 
    dfCovMatrix = dfReturns.cov() 
    dictDetailsOutput['Beta versus benchmark'] = dfCovMatrix.loc[serPositionsDetailsInput['Ticker symbol'], benchmarkTicker] / (dfReturns[benchmarkTicker].std() ** 2) 
    
    strLastDate = dfDividendsSplitAdj.sort_index(ascending = True).index[-1].strftime('%Y-%m-%d') 
    strSecondLastDate = dfDividendsSplitAdj.sort_index(ascending = True).index[-2].strftime('%Y-%m-%d') 
    dictDetailsOutput[f'Dividend on {strLastDate}'] = dfDividendsSplitAdj[serPositionsDetailsInput['Ticker symbol']].iloc[-1] 
    dictDetailsOutput[f'Dividend on {strSecondLastDate}'] = dfDividendsSplitAdj[serPositionsDetailsInput['Ticker symbol']].iloc[-2] 
    
    date1yAgo = pd.to_datetime(endDate, format = '%Y-%m-%d') - dt.timedelta(days = 365) 
    dividends1y = dfDividendsSplitAdj[dfDividendsSplitAdj.index >= date1yAgo][serPositionsDetailsInput['Ticker symbol']].sum() 
    
    dictDetailsOutput['1y dividend yield'] = dividends1y / dictDetailsOutput['Last price'] 
    
    strLastDate = dfAdjFactors.sort_index(ascending = True).index[-1].strftime('%Y-%m-%d') 
    strSecondLastDate = dfAdjFactors.sort_index(ascending = True).index[-2].strftime('%Y-%m-%d') 
    splitFactorLastDate = dfAdjFactors[serPositionsDetailsInput['Ticker symbol']].iloc[-1] 
    splitFactorSecondLastDate = dfAdjFactors[serPositionsDetailsInput['Ticker symbol']].iloc[-2] 
    dictDetailsOutput[f'Split adjustment on {strLastDate}'] = 'None' if splitFactorLastDate == 1 else f'{int((1 / splitFactorLastDate) * 100) / 100} for 1 split' 
    dictDetailsOutput[f'Split adjustment on {strSecondLastDate}'] = 'None' if splitFactorSecondLastDate == 1 else f'{int((1 / splitFactorSecondLastDate) * 100) / 100} for 1 split' 
    
    dictDetailsOutput['detailsAvailable'] = True 

    return dictDetailsOutput 
