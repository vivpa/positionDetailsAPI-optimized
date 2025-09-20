import datetime as dt 
import intrinio_sdk as intrinio 
import numpy as np 
import pandas as pd 
import pytz 
import requests 

from functions.computeOptionValues import computeOptionValues 
from functions.getLatestWeekday import getLatestWeekday 

def calcOptionDetails(serPositionsDetailsInput, dictOptionPrices, dfPricesSplitAdj, dfPricesFinalNonAdj, dfAdjFactors, dfDividendsSplitAdj, lstPositionNamesAndPrices, dfEarningsSelectedTickers, dfDividendsSelectedTickers, intrinioApiKey, snowflakeConnection): 
    benchmarkTicker = 'SPY' 
    
    if dictOptionPrices != {}: 
        for eachDictOptionDetails in dictOptionPrices['contracts']: 
            if eachDictOptionDetails['option']['code'] == serPositionsDetailsInput.loc['Ticker symbol']: 
                relevantOptionDetails = eachDictOptionDetails 

                break 
            else: 
                relevantOptionDetails = {} 
    else: 
        relevantOptionDetails = {} 
    
    print(f"Response for {serPositionsDetailsInput.loc['Ticker symbol']}: {relevantOptionDetails}") 

    returnNas = False 
    if relevantOptionDetails == {}: 
        returnNas = True 
    elif relevantOptionDetails['option']['code'] != serPositionsDetailsInput.loc['Ticker symbol']: 
        returnNas = True 
    
    if returnNas == True: 
        return { "detailsAvailable": False, "errorMessage": "Option details not available in database" } 
    
    dictDetailsOutput = {} 
    dictDetailsOutput['Option underlying ticker'] = relevantOptionDetails['option']['ticker'] 
    
    if len(lstPositionNamesAndPrices) > 0: 
        for eachItem in lstPositionNamesAndPrices: 
            if eachItem['security']['ticker'] == dictDetailsOutput['Option underlying ticker']: 
                relevantUnderlyingNameAndPrices = eachItem 

                break 
            else: 
                relevantUnderlyingNameAndPrices = {} 
    else: 
        relevantUnderlyingNameAndPrices = {} 
    
    if relevantUnderlyingNameAndPrices != {}: 
        dictDetailsOutput['Option underlying name'] = relevantUnderlyingNameAndPrices['security']['name'] 
    else: 
        dictDetailsOutput['Option underlying name'] = '' 
    
    dictDetailsOutput['Option underlying price'] = relevantOptionDetails['stats']['underlying_price'] 
    dictDetailsOutput['Option type'] = relevantOptionDetails['option']['type'] 
    dictDetailsOutput['Option expiry'] = pd.to_datetime(relevantOptionDetails['option']['expiration']).strftime('%Y-%m-%d') 
    dictDetailsOutput['Option strike'] = relevantOptionDetails['option']['strike'] 
    
    # Methodology to be fixed for deliverableMultiplier - Vivek seeking details from ivol 
    dictDetailsOutput['Deliverable multiplier'] = 100.0 
    
    dictDetailsOutput['Last price'] = relevantOptionDetails['price']['last'] 
    dictDetailsOutput['Last size'] = relevantOptionDetails['price']['last_size'] 
    dictDetailsOutput['Ask'] = relevantOptionDetails['price']['ask'] 
    dictDetailsOutput['Ask size'] = relevantOptionDetails['price']['ask_size'] 
    dictDetailsOutput['Bid'] = relevantOptionDetails['price']['bid'] 
    dictDetailsOutput['Bid size'] = relevantOptionDetails['price']['bid_size'] 
    if dictDetailsOutput['Ask'] is not None and dictDetailsOutput['Bid'] is not None:
        dictDetailsOutput['Mid'] = (dictDetailsOutput['Ask'] + dictDetailsOutput['Bid']) / 2
    elif dictDetailsOutput['Ask'] is not None:
        dictDetailsOutput['Mid'] = dictDetailsOutput['Ask']
    elif dictDetailsOutput['Bid'] is not None:
        dictDetailsOutput['Mid'] = dictDetailsOutput['Bid']
    else:
        dictDetailsOutput['Mid'] = None
    dictDetailsOutput['Option implied volatility'] = relevantOptionDetails['stats']['implied_volatility'] 
    dictDetailsOutput['Option moneyness'] = None if dictDetailsOutput['Option underlying price'] == 0 or dictDetailsOutput['Option underlying price'] is None else dictDetailsOutput['Option strike'] / dictDetailsOutput['Option underlying price'] 

    nyTimezone = pytz.timezone('America/New_York') 
    # Calculate days till expiration from current date (not current datetime)
    # This ensures that if today is the expiration date, it returns 1
    expiration_date = pd.to_datetime(relevantOptionDetails['option']['expiration'], format = '%Y-%m-%d').date()
    current_date = dt.datetime.now(tz = nyTimezone).date()
    dictDetailsOutput['Option days till expiration'] = (expiration_date - current_date).days + 1

    dictDetailsOutput['Option delta'] = relevantOptionDetails['stats']['delta'] or None 
    dictDetailsOutput['Option gamma'] = relevantOptionDetails['stats']['gamma'] or None 
    dictDetailsOutput['Option theta'] = relevantOptionDetails['stats']['theta'] or None 
    dictDetailsOutput['Option vega'] = relevantOptionDetails['stats']['vega'] or None 
    dictDetailsOutput['Option OTM probability'] = (1 - dictDetailsOutput['Option delta']) if dictDetailsOutput['Option delta'] != None else None 
    
    if not dfEarningsSelectedTickers.empty: 
        if dictDetailsOutput['Option underlying ticker'] not in list(dfEarningsSelectedTickers['TICKER']): 
            dictDetailsOutput['Next earnings date'] = 'NA' 
        else: 
            dictDetailsOutput['Next earnings date'] = dfEarningsSelectedTickers[dfEarningsSelectedTickers['TICKER'] == dictDetailsOutput['Option underlying ticker']]['NEXT_EARNINGS_DATE'].iloc[0] 
    else: 
        dictDetailsOutput['Next earnings date'] = 'NA' 

    if not dfDividendsSelectedTickers.empty: 
        if dictDetailsOutput['Option underlying ticker'] not in list(dfDividendsSelectedTickers['TICKER']): 
            dictDetailsOutput['Next dividend ex date'] = 'NA' 
            dictDetailsOutput['Next dividend amount'] = 'NA' 
        else: 
            latestExDividendDate = dfDividendsSelectedTickers[dfDividendsSelectedTickers['TICKER'] == dictDetailsOutput['Option underlying ticker']]['LAST_EX_DIVIDEND_DATE'].iloc[0] 
            if pd.to_datetime(latestExDividendDate, format = '%Y-%m-%d') > dt.datetime.now() - dt.timedelta(days = 1): 
                dictDetailsOutput['Next dividend ex date'] = latestExDividendDate 
                dictDetailsOutput['Next dividend amount'] = float(dfDividendsSelectedTickers[dfDividendsSelectedTickers['TICKER'] == dictDetailsOutput['Option underlying ticker']]['EX_DIVIDEND'].iloc[0]) if dfDividendsSelectedTickers[dfDividendsSelectedTickers['TICKER'] == dictDetailsOutput['Option underlying ticker']]['EX_DIVIDEND'].iloc[0] != '' else 0.0 
            else: 
                dictDetailsOutput['Next dividend ex date'] = 'NA' 
                dictDetailsOutput['Next dividend amount'] = 'NA' 
    else: 
        dictDetailsOutput['Next dividend ex date'] = 'NA' 
        dictDetailsOutput['Next dividend amount'] = 'NA' 
    
    # Option rho to be done later, Rajeev working on the model for option exercise probability 
    # optionRho = TBC 
    # optionExerciseProbability = TBC 
    
    # Calculation of option exercise value 
    optionWeekdaysTillExpiration = int(dictDetailsOutput['Option days till expiration'] * 5 / 7) 
    
    dfReturnsData = (dfPricesSplitAdj / dfPricesSplitAdj.shift(optionWeekdaysTillExpiration) - 1).dropna() 
    
    # Calculation of the option's expected value 
    lstPercentiles = [0.01 * i for i in range(101)] 
    dfReturnsDistribution = pd.DataFrame(index = lstPercentiles, columns = ['Underlying return', 'Underlying price', 'Option payoff']) 
    for eachPercentile in lstPercentiles: 
        
        dfReturnsDistribution.loc[eachPercentile, 'Underlying return'] = dfReturnsData[dictDetailsOutput['Option underlying ticker']].quantile(eachPercentile) 
        dfReturnsDistribution.loc[eachPercentile, 'Underlying price'] = None if dictDetailsOutput['Option underlying price'] is None or dfReturnsDistribution.loc[eachPercentile, 'Underlying return'] is None else dictDetailsOutput['Option underlying price'] * (1 + dfReturnsDistribution.loc[eachPercentile, 'Underlying return']) 
        
        if dictDetailsOutput['Option type'].lower() == 'call': 
            dfReturnsDistribution.loc[eachPercentile, 'Option payoff'] = max(0, dfReturnsDistribution.loc[eachPercentile, 'Underlying price'] - dictDetailsOutput['Option strike']) 
        elif dictDetailsOutput['Option type'].lower() == 'put': 
            dfReturnsDistribution.loc[eachPercentile, 'Option payoff'] = max(0, dictDetailsOutput['Option strike'] - dfReturnsDistribution.loc[eachPercentile, 'Underlying price']) 
    
    dictDetailsOutput['Option expected value'] = dfReturnsDistribution['Option payoff'].mean() 
    
    # Calculating the relevant quantities if the options position is available 
    if serPositionsDetailsInput.loc['Ticker position'] != 'NA': 
        dictDetailsOutput['Total shares deliverable'] = None if serPositionsDetailsInput['Ticker position'] is None or dictDetailsOutput['Deliverable multiplier'] is None else serPositionsDetailsInput['Ticker position'] * dictDetailsOutput['Deliverable multiplier'] 
        dictDetailsOutput['Total option notional'] = None if dictDetailsOutput['Option underlying price'] is None or dictDetailsOutput['Total shares deliverable'] is None else dictDetailsOutput['Option underlying price'] * dictDetailsOutput['Total shares deliverable'] 
        dictDetailsOutput['Total delta'] = None if dictDetailsOutput['Option delta'] is None or dictDetailsOutput['Total shares deliverable'] is None else dictDetailsOutput['Option delta'] * dictDetailsOutput['Total shares deliverable'] 
        dictDetailsOutput['Total gamma'] = None if dictDetailsOutput['Option gamma'] is None or dictDetailsOutput['Total shares deliverable'] is None else dictDetailsOutput['Option gamma'] * dictDetailsOutput['Total shares deliverable'] 
        dictDetailsOutput['Total theta'] = None if dictDetailsOutput['Option theta'] is None or dictDetailsOutput['Total shares deliverable'] is None else dictDetailsOutput['Option theta'] * dictDetailsOutput['Total shares deliverable'] 
        dictDetailsOutput['Total vega'] = None if dictDetailsOutput['Option vega'] is None or dictDetailsOutput['Total shares deliverable'] is None else dictDetailsOutput['Option vega'] * dictDetailsOutput['Total shares deliverable'] 
        
        if serPositionsDetailsInput['Underlying position'] != 'NA': 
            dictDetailsOutput['Coverage ratio'] = None if serPositionsDetailsInput['Underlying position'] == 0 or serPositionsDetailsInput['Underlying position'] is None else dictDetailsOutput['Total shares deliverable'] / serPositionsDetailsInput['Underlying position'] 
            dictDetailsOutput['Covered call delta'] = None if dictDetailsOutput['Coverage ratio'] is None or dictDetailsOutput['Option delta'] is None else (1 - dictDetailsOutput['Coverage ratio'] * dictDetailsOutput['Option delta']) 
            
            # Calculation of beta versus benchmark 
            dfReturns = (dfPricesSplitAdj / dfPricesSplitAdj.shift(1) - 1).dropna() 
            dfCovMatrix = dfReturns.cov() 
            
            benchmark_variance = dfReturns.std()[benchmarkTicker] ** 2
            betaVsBenchmark = None if benchmark_variance == 0 or benchmark_variance is None else dfCovMatrix.loc[dictDetailsOutput['Option underlying ticker'], benchmarkTicker] / benchmark_variance 
            
            dictDetailsOutput['Covered call beta'] = None if dictDetailsOutput['Covered call delta'] is None or betaVsBenchmark is None else dictDetailsOutput['Covered call delta'] * betaVsBenchmark 
            dictDetailsOutput['Total covered call delta'] = None if dictDetailsOutput['Covered call delta'] is None or dictDetailsOutput['Total shares deliverable'] is None else dictDetailsOutput['Covered call delta'] * dictDetailsOutput['Total shares deliverable'] 
            dictDetailsOutput['Total covered call beta'] = None if dictDetailsOutput['Covered call beta'] is None or dictDetailsOutput['Total shares deliverable'] is None else dictDetailsOutput['Covered call beta'] * dictDetailsOutput['Total shares deliverable'] 
    
    if serPositionsDetailsInput['Option trade date'] != 'NA': 
        tradeDate = pd.to_datetime(serPositionsDetailsInput['Option trade date'], format = '%Y-%m-%d').date() 
        underlyingPriceTradeDate = dfPricesSplitAdj[dfPricesSplitAdj.index <= pd.to_datetime(tradeDate)][dictDetailsOutput['Option underlying ticker']].iloc[-1] 
        if 'Option entry price' in serPositionsDetailsInput.index: 
            days_to_expiry = (pd.to_datetime(relevantOptionDetails['option']['expiration']).date() - tradeDate).days
            dictDetailsOutput['Annualized premium at inception'] = None if underlyingPriceTradeDate == 0 or underlyingPriceTradeDate is None or days_to_expiry == 0 else (serPositionsDetailsInput['Option entry price'] / underlyingPriceTradeDate) * (365 / days_to_expiry) 
    
    endDate = dt.datetime.now() 
    endDate = getLatestWeekday(endDate) 
    date1yAgo = (endDate - dt.timedelta(days = 365)).date() 
    dividendsLast1y = dfDividendsSplitAdj[dfDividendsSplitAdj.index >= date1yAgo][dictDetailsOutput['Option underlying ticker']].sum() 
    
    # Calculating intrinsic value, time value and whether or not the option is likely to be early exercised 
    # Expected dividend over the next year would be the same as the dividend over the last 1y multiplied by the number of years to maturity 
    daysToMaturity = (pd.to_datetime(dictDetailsOutput['Option expiry'], format = '%Y-%m-%d') - endDate).days 
    expectedDividend = None if dividendsLast1y is None or daysToMaturity is None else dividendsLast1y * daysToMaturity / 365.0 

    if dictDetailsOutput['Mid'] != None or dictDetailsOutput['Last price'] != None or dictDetailsOutput['Bid'] != None: 
        if dictDetailsOutput['Mid'] != None: 
            intrinsicValue, timeValue, earlyExercise = computeOptionValues(dictDetailsOutput['Option type'], dictDetailsOutput['Option underlying price'], dictDetailsOutput['Option strike'], dictDetailsOutput['Mid'], expectedDividend) 
        elif dictDetailsOutput['Last price'] != None: 
            intrinsicValue, timeValue, earlyExercise = computeOptionValues(dictDetailsOutput['Option type'], dictDetailsOutput['Option underlying price'], dictDetailsOutput['Option strike'], dictDetailsOutput['Last price'], expectedDividend) 
        elif dictDetailsOutput['Bid'] != None: 
            intrinsicValue, timeValue, earlyExercise = computeOptionValues(dictDetailsOutput['Option type'], dictDetailsOutput['Option underlying price'], dictDetailsOutput['Option strike'], dictDetailsOutput['Bid'], expectedDividend) 
        
        dictDetailsOutput['Intrinsic value'] = intrinsicValue 
        dictDetailsOutput['Time value'] = timeValue 
        dictDetailsOutput['Early exercise'] = earlyExercise 
    else: 
        dictDetailsOutput['Intrinsic value'] = None 
        dictDetailsOutput['Time value'] = None 
        dictDetailsOutput['Early exercise'] = '' 
    
    dictDetailsOutput['detailsAvailable'] = True 
    
    return dictDetailsOutput 
