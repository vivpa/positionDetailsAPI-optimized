import datetime as dt 
import intrinio_sdk as intrinio 
import pandas as pd 

from functions.getLatestWeekday import getLatestWeekday 
from functions.retrieveIntrinioStockPrices import retrieveIntrinioStockPrices 

def calcOptionDetails(dictPositionsDetailsInput, snowflakeConnection): 
    # Getting prices for the option 
    # If the underlying is an option, prices are obtained through OptionsApi() 
    source = '' 
    stockPriceSource = '' 
    model = '' 
    showExtendedPrice = '' 
    
    responseOptionDetails = intrinio.OptionsApi().get_options_prices_realtime(dictPositionsDetailsInput['tickerSymbol'], source = source, stock_price_source = stockPriceSource, model = model, show_extended_price = showExtendedPrice) 
    dictResponseOptionDetails = responseOptionDetails.to_dict() 
    
    dictDetailsOutput = {} 
    dictDetailsOutput['optionUnderlyingTicker'] = dictResponseOptionDetails['option']['ticker'] 
    
    startDate = (dt.datetime.now() - dt.timedelta(days = 5)).strftime('%Y-%m-%d') 
    endDate = dt.datetime.now().strftime('%Y-%m-%d') 
    frequency = 'daily' 
    pageSize = 100 
    nextPage = '' 
    responseEquityPrices = intrinio.SecurityApi().get_security_stock_prices(dictDetailsOutput['optionUnderlyingTicker'], start_date = startDate, end_date = endDate, frequency = frequency, page_size = pageSize, next_page = nextPage) 
    dictResponseEquityPrices = responseEquityPrices.to_dict() 
    
    dictDetailsOutput['optionUnderlyingName'] = dictResponseEquityPrices['security']['name']     # To be done further 
    dictDetailsOutput['optionUnderlyingPrice'] = dictResponseOptionDetails['stats']['underlying_price'] 
    dictDetailsOutput['optionType'] = dictResponseOptionDetails['option']['type'] 
    dictDetailsOutput['optionExpiry'] = pd.to_datetime(dictResponseOptionDetails['option']['expiration']).strftime('%Y-%m-%d') 
    dictDetailsOutput['optionStrike'] = dictResponseOptionDetails['option']['strike'] 
    
    # Methodology to be fixed for deliverableMultiplier - Vivek seeking details from ivol 
    dictDetailsOutput['deliverableMultiplier'] = 100.0 
    
    dictDetailsOutput['optionImpliedVol'] = dictResponseOptionDetails['stats']['implied_volatility'] 
    dictDetailsOutput['optionMoneyness'] = dictDetailsOutput['optionUnderlyingPrice'] / dictDetailsOutput['optionStrike'] 
    dictDetailsOutput['optionDaysTillExpiration'] = (dictResponseOptionDetails['option']['expiration'] - dt.datetime.now().date()).days 
    dictDetailsOutput['optionDelta'] = dictResponseOptionDetails['stats']['delta'] 
    dictDetailsOutput['optionGamma'] = dictResponseOptionDetails['stats']['gamma'] 
    dictDetailsOutput['optionTheta'] = dictResponseOptionDetails['stats']['theta'] 
    dictDetailsOutput['optionVega'] = dictResponseOptionDetails['stats']['vega'] 
    dictDetailsOutput['optionOtmProbability'] = 1 - dictDetailsOutput['optionDelta'] 
    
    # Option rho to be done later, Rajeev working on the model for option exercise probability 
    # optionRho = TBC 
    # optionExerciseProbability = TBC 
    
    # Calculation of option exercise value 
    optionWeekdaysTillExpiration = int(dictDetailsOutput['optionDaysTillExpiration'] * 5 / 7) 
    
    numOfYearsForDataExtraction = 5 
    endDate = dt.datetime.now() 
    endDate = getLatestWeekday(endDate) 
    startDate = endDate - dt.timedelta(days = numOfYearsForDataExtraction * 365) 
    startDate = getLatestWeekday(startDate) 
    
    # Data for SPY extracted to calculate the beta 
    # Needs to be made dynamic to deal with fixed income underlyings as well 
    benchmarkTicker = 'SPY' 
    
    dfPricesFinal = retrieveIntrinioStockPrices([dictDetailsOutput['optionUnderlyingTicker'], benchmarkTicker], startDate, endDate, 'adjclose', snowflakeConnection) 
    dfPricesFinal.index = pd.to_datetime(dfPricesFinal.index) 
    dfReturnsData = (dfPricesFinal / dfPricesFinal.shift(optionWeekdaysTillExpiration) - 1).dropna() 
    
    # Start date has been shifted to ~1y ago because we need the 1y adjustment factors option prices calcs 
    dfPricesFinalNonAdj, dfAdjFactors = retrieveIntrinioStockPrices([dictDetailsOutput['optionUnderlyingTicker'], benchmarkTicker], startDate - dt.timedelta(days = 400), endDate, 'close', snowflakeConnection) 
    dfPricesFinalNonAdj.index = pd.to_datetime(dfPricesFinalNonAdj.index) 
    
    # Rebasing the non-adjusted prices to start from the startDate 
    dfPricesFinalNonAdj = dfPricesFinalNonAdj[dfPricesFinalNonAdj.index >= startDate].copy() 
    
    # Calculating the cumulative adjustment factors 
    dfCumuAdjFactors = dfAdjFactors.sort_index(ascending = False) 
    dfCumuAdjFactors = dfCumuAdjFactors.cumprod() 
    dfCumuAdjFactors = dfCumuAdjFactors.sort_index(ascending = True) 
    dfCumuAdjFactors = dfCumuAdjFactors.shift(-1).ffill() 
    
    # Calculation of the option's expected value 
    lstPercentiles = [0.01 * i for i in range(101)] 
    dfReturnsDistribution = pd.DataFrame(index = lstPercentiles, columns = ['Underlying return', 'Underlying price', 'Option payoff']) 
    for eachPercentile in lstPercentiles: 
        dfReturnsDistribution.loc[eachPercentile, 'Underlying return'] = dfReturnsData[dictDetailsOutput['optionUnderlyingTicker']].quantile(eachPercentile) 
        dfReturnsDistribution.loc[eachPercentile, 'Underlying price'] = dictDetailsOutput['optionUnderlyingPrice'] * (1 + dfReturnsDistribution.loc[eachPercentile, 'Underlying return']) 
        
        if dictDetailsOutput['optionType'].lower() == 'call': 
            dfReturnsDistribution.loc[eachPercentile, 'Option payoff'] = max(0, dfReturnsDistribution.loc[eachPercentile, 'Underlying price'] - dictDetailsOutput['optionStrike']) 
        elif dictDetailsOutput['optionType'].lower() == 'put': 
            dfReturnsDistribution.loc[eachPercentile, 'Option payoff'] = max(0, dictDetailsOutput['optionStrike'] - dfReturnsDistribution.loc[eachPercentile, 'Underlying price']) 
    
    dictDetailsOutput['optionExpectedValue'] = dfReturnsDistribution.loc[eachPercentile, 'Option payoff'].mean() 
    
    # Calculating the relevant quantities if the options position is available 
    if 'tickerPosition' in dictPositionsDetailsInput.keys(): 
        dictDetailsOutput['sharesDeliverable'] = dictPositionsDetailsInput['tickerPosition'] * dictDetailsOutput['deliverableMultiplier'] 
        dictDetailsOutput['optionNotional'] = dictDetailsOutput['sharesDeliverable'] * dictDetailsOutput['optionUnderlyingPrice'] 
        dictDetailsOutput['totalDelta'] = dictDetailsOutput['optionDelta'] * dictDetailsOutput['sharesDeliverable'] 
        dictDetailsOutput['totalGamma'] = dictDetailsOutput['optionGamma'] * dictDetailsOutput['sharesDeliverable'] 
        dictDetailsOutput['totalTheta'] = dictDetailsOutput['optionTheta'] * dictDetailsOutput['sharesDeliverable'] 
        dictDetailsOutput['totalVega'] = dictDetailsOutput['optionVega'] * dictDetailsOutput['sharesDeliverable'] 
        
        if 'underlyingPosition' in dictPositionsDetailsInput.keys(): 
            dictDetailsOutput['coverageRatio'] = dictDetailsOutput['sharesDeliverable'] / dictPositionsDetailsInput['underlyingPosition'] 
            dictDetailsOutput['coveredCallDelta'] = 1 - dictDetailsOutput['coverageRatio'] * dictDetailsOutput['optionDelta'] 
            
            # Calculation of beta versus benchmark 
            dfReturns = (dfPricesFinal / dfPricesFinal.shift(1) - 1).dropna() 
            dfCovMatrix = dfReturns.cov() 
            
            betaVsBenchmark = dfCovMatrix.loc[dictDetailsOutput['optionUnderlyingTicker'], benchmarkTicker] / dfReturns.std()[benchmarkTicker] ** 2 
            
            dictDetailsOutput['coveredCallBeta'] = dictDetailsOutput['coveredCallDelta'] * betaVsBenchmark 
            dictDetailsOutput['totalCoveredCallDelta'] = dictDetailsOutput['coveredCallDelta'] * dictDetailsOutput['sharesDeliverable'] 
            dictDetailsOutput['totalCoveredCallBeta'] = dictDetailsOutput['coveredCallBeta'] * dictDetailsOutput['sharesDeliverable'] 
    
    if 'optionTradeDate' in dictPositionsDetailsInput.keys(): 
        tradeDate = pd.to_datetime(dictPositionsDetailsInput['optionTradeDate'], format = '%Y-%m-%d').date() 
        underlyingPriceTradeDate = dfPricesFinal[dfPricesFinal.index <= pd.to_datetime(tradeDate)][dictDetailsOutput['optionUnderlyingTicker']].iloc[-1] 
        if 'optionEntryPrice' in dictPositionsDetailsInput.keys() and 'optionTradeDate' in dictPositionsDetailsInput.keys(): 
            dictDetailsOutput['annualizedPremiumAtInception'] = (dictPositionsDetailsInput['optionEntryPrice'] / underlyingPriceTradeDate) * (365 / (pd.to_datetime(dictResponseOptionDetails['option']['expiration']).date() - tradeDate).days) 
    
    return dictDetailsOutput 
