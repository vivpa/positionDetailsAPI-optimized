import datetime as dt 
import intrinio_sdk as intrinio 
import numpy as np 
import pandas as pd 
import requests 

from functions.calcRsi import calcRsi 
from functions.calcImpliedVol import calcImpliedVol 
from functions.getLatestWeekday import getLatestWeekday 

def calcEquityDetails(serPositionsDetailsInput, dfImpliedVols1m, dfPricesSplitAdj, dfPricesFinalNonAdj, dfAdjFactors, dfDividendsSplitAdj, lstPositionNamesAndPrices, dfEarningsSelectedTickers, dfDividendsSelectedTickers, intrinioApiKey, snowflakeConnection): 
    benchmarkTicker = 'SPY' 
    
    if len(lstPositionNamesAndPrices) > 0: 
        for eachItem in lstPositionNamesAndPrices: 
            if eachItem['security']['ticker'] == serPositionsDetailsInput.loc['Ticker symbol']: 
                relevantPositionNameAndPrices = eachItem 

                break 
            else: 
                relevantPositionNameAndPrices = {} 
    else: 
        relevantPositionNameAndPrices = {} 
    
    # # Getting prices for the stock or ETF 
    # # If the underlying is a stock or an ETF, prices are obtained through SecurityApi() 
    # startDate = (dt.datetime.now() - dt.timedelta(days = 7)).strftime('%Y-%m-%d') 
    # endDate = dt.datetime.now().strftime('%Y-%m-%d') 
    # frequency = 'daily' 
    # pageSize = 100 
    # nextPage = '' 
    
    # try: 
    #     responseEquityPrices = intrinio.SecurityApi().get_security_stock_prices(serPositionsDetailsInput['Ticker symbol'], start_date = startDate, end_date = endDate, frequency = frequency, page_size = pageSize, next_page = nextPage) 
    # except: 
    #     return { "detailsAvailable": False } 
    
    # dictResponseEquityPrices = responseEquityPrices.to_dict() 
    
    # print(f"Response for {serPositionsDetailsInput.loc['Ticker symbol']}: {responseEquityPrices}") 

    # dfStockPrices = pd.DataFrame(dictResponseEquityPrices['stock_prices']) 
    # maxDate = dfStockPrices['date'].max() 
    
    dictDetailsOutput = {} 
    
    if relevantPositionNameAndPrices != {}: 
        dictDetailsOutput['Name'] = relevantPositionNameAndPrices['security']['name'] 
        dictDetailsOutput['Last price'] = relevantPositionNameAndPrices['last'] 
        dictDetailsOutput['Open'] = relevantPositionNameAndPrices['open'] 
        dictDetailsOutput['High'] = relevantPositionNameAndPrices['high'] 
        dictDetailsOutput['Low'] = relevantPositionNameAndPrices['low'] 
        dictDetailsOutput['Price change'] = relevantPositionNameAndPrices['change_percent'] 
        dictDetailsOutput['52 week high'] = relevantPositionNameAndPrices['eod_fifty_two_week_high'] 
        dictDetailsOutput['52 week low'] = relevantPositionNameAndPrices['eod_fifty_two_week_low'] 
    else: 
        dictDetailsOutput['Name'] = '' 
        dictDetailsOutput['Last price'] = None 
        dictDetailsOutput['Open'] = None 
        dictDetailsOutput['High'] = None 
        dictDetailsOutput['Low'] = None 
        dictDetailsOutput['Price change'] = None 
        dictDetailsOutput['52 week high'] = None 
        dictDetailsOutput['52 week low'] = None 

    if not dfEarningsSelectedTickers.empty: 
        if serPositionsDetailsInput['Ticker symbol'] not in list(dfEarningsSelectedTickers['TICKER']): 
            dictDetailsOutput['Next earnings date'] = 'NA' 
        else: 
            dictDetailsOutput['Next earnings date'] = dfEarningsSelectedTickers[dfEarningsSelectedTickers['TICKER'] == serPositionsDetailsInput['Ticker symbol']]['NEXT_EARNINGS_DATE'].iloc[0] 
    else: 
        dictDetailsOutput['Next earnings date'] = 'NA' 
    
    if not dfDividendsSelectedTickers.empty: 
        if serPositionsDetailsInput['Ticker symbol'] not in list(dfDividendsSelectedTickers['TICKER']): 
            dictDetailsOutput['Next dividend ex date'] = 'NA' 
            dictDetailsOutput['Next dividend amount'] = 'NA' 
        else: 
            latestExDividendDate = dfDividendsSelectedTickers[dfDividendsSelectedTickers['TICKER'] == serPositionsDetailsInput['Ticker symbol']]['LAST_EX_DIVIDEND_DATE'].iloc[0] 
            if pd.to_datetime(latestExDividendDate, format = '%Y-%m-%d') > dt.datetime.now() - dt.timedelta(days = 1): 
                dictDetailsOutput['Next dividend ex date'] = latestExDividendDate 
                dictDetailsOutput['Next dividend amount'] = float(dfDividendsSelectedTickers[dfDividendsSelectedTickers['TICKER'] == serPositionsDetailsInput['Ticker symbol']]['EX_DIVIDEND'].iloc[0]) if dfDividendsSelectedTickers[dfDividendsSelectedTickers['TICKER'] == serPositionsDetailsInput['Ticker symbol']]['EX_DIVIDEND'].iloc[0] != '' else 0.0 
            else: 
                dictDetailsOutput['Next dividend ex date'] = 'NA' 
                dictDetailsOutput['Next dividend amount'] = 'NA' 
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

    if tickerSymbol in list(dfImpliedVols1m.index): 
        dictDetailsOutput['1m implied volatility'] = dfImpliedVols1m[dfImpliedVols1m.index == tickerSymbol]['Implied vol 1m'].iloc[0] 
    else: 
        dictDetailsOutput['1m implied volatility'] = 'NA' 
    
    dictDetailsOutput['1m realized volatility'] = (np.log(dfPricesSplitAdj[tickerSymbol] / dfPricesSplitAdj[tickerSymbol].shift(1))).rolling(22).std().iloc[-1] * np.sqrt(252) 

    if dictDetailsOutput['1m implied volatility'] != 'NA': 
        dictDetailsOutput['1m implied volatility premium'] = dictDetailsOutput['1m implied volatility'] - dictDetailsOutput['1m realized volatility'] 
    else: 
        dictDetailsOutput['1m implied volatility premium'] = 'NA' 

    # Calculation of beta versus benchmark 
    dfReturns = (dfPricesSplitAdj / dfPricesSplitAdj.shift(1) - 1).dropna() 
    dfCovMatrix = dfReturns.cov() 
    benchmark_variance = dfReturns[benchmarkTicker].std() ** 2
    dictDetailsOutput['Beta versus benchmark'] = None if benchmark_variance == 0 or benchmark_variance is None else dfCovMatrix.loc[serPositionsDetailsInput['Ticker symbol'], benchmarkTicker] / benchmark_variance 
    
    strLastDate = dfDividendsSplitAdj.sort_index(ascending = True).index[-1].strftime('%Y-%m-%d') 
    strSecondLastDate = dfDividendsSplitAdj.sort_index(ascending = True).index[-2].strftime('%Y-%m-%d') 
    dictDetailsOutput[f'Dividend on {strLastDate}'] = dfDividendsSplitAdj[serPositionsDetailsInput['Ticker symbol']].iloc[-1] 
    dictDetailsOutput[f'Dividend on {strSecondLastDate}'] = dfDividendsSplitAdj[serPositionsDetailsInput['Ticker symbol']].iloc[-2] 
    
    date1yAgo = (endDate - dt.timedelta(days = 365)).date() 
    dividends1y = dfDividendsSplitAdj[dfDividendsSplitAdj.index >= date1yAgo][serPositionsDetailsInput['Ticker symbol']].sum() 
    
    dictDetailsOutput['1y dividend yield'] = None if dictDetailsOutput['Last price'] == None or dictDetailsOutput['Last price'] == 0 else (dividends1y / dictDetailsOutput['Last price']) 
    
    strLastDate = dfAdjFactors.sort_index(ascending = True).index[-1].strftime('%Y-%m-%d') 
    strSecondLastDate = dfAdjFactors.sort_index(ascending = True).index[-2].strftime('%Y-%m-%d') 
    splitFactorLastDate = dfAdjFactors[serPositionsDetailsInput['Ticker symbol']].iloc[-1] 
    splitFactorSecondLastDate = dfAdjFactors[serPositionsDetailsInput['Ticker symbol']].iloc[-2] 
    dictDetailsOutput[f'Split adjustment on {strLastDate}'] = 'None' if splitFactorLastDate == 1 or splitFactorLastDate == 0 or splitFactorLastDate is None else f'{int((1 / splitFactorLastDate) * 100) / 100} for 1 split' 
    dictDetailsOutput[f'Split adjustment on {strSecondLastDate}'] = 'None' if splitFactorSecondLastDate == 1 or splitFactorSecondLastDate == 0 or splitFactorSecondLastDate is None else f'{int((1 / splitFactorSecondLastDate) * 100) / 100} for 1 split' 
    
    dictDetailsOutput['detailsAvailable'] = True 

    return dictDetailsOutput 
