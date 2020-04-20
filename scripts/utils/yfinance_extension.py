# extensions for the module "yfinance", because it does not have the ability to load all necessary data

# import modules
import requests as _requests
import json as _json
import collections
from pandas import DataFrame
from datetime import datetime


# Function to get the annualDilutedEPS from yahoo finance
def load_EPS(symbol):

    url = "https://finance.yahoo.com/quote/" + symbol + "/financials"

    dilutedEpsDict = {}
    basicEpsDict = {}
    html = _requests.get(url=url).text

    json_str = html.split('root.App.main =')[1].split(
        '(this)')[0].split(';\n}')[0].strip()
    
    if "QuoteTimeSeries" in html:
        annualDilutedEPSList = _json.loads(json_str)['context']['dispatcher']['stores']['QuoteTimeSeriesStore']['timeSeries']['annualDilutedEPS']

        for eps in annualDilutedEPSList:
            if eps is not None:
                dilutedEpsDict[eps['asOfDate']] = eps['reportedValue']['raw']

        annualBasicEPSList = _json.loads(json_str)['context']['dispatcher']['stores']['QuoteTimeSeriesStore']['timeSeries']['annualBasicEPS']
        for eps in annualBasicEPSList:
            if eps is not None:
                basicEpsDict[eps['asOfDate']] = eps['reportedValue']['raw']

    # sort dicts in descending order, from newest to oldest
    dilutedEpsDictSorted = sortDictDescending(dilutedEpsDict)
    basicEpsDictSorted = sortDictDescending(basicEpsDict)

    # create an empty pandas data frame
    df = DataFrame()

    # add diluted eps data
    for k,v in dilutedEpsDictSorted.items():
        df.loc['dilutedEPS', k] = v

    # add basic EPS data
    for k,v in basicEpsDictSorted.items():
        df.loc['basicEPS',k] = v

    return df

def load_CashFlow(symbol):
    url = "https://finance.yahoo.com/quote/" + symbol + "/cash-flow?p=" + symbol

    freecashflowDict = {}
    html = _requests.get(url=url).text

    json_str = html.split('root.App.main =')[1].split(
        '(this)')[0].split(';\n}')[0].strip()
    
    if "QuoteTimeSeries" in html:
        freeCashFlowList = _json.loads(json_str)['context']['dispatcher']['stores']['QuoteTimeSeriesStore']['timeSeries']['annualFreeCashFlow']

        for freecashflow in freeCashFlowList:
            if freecashflow is not None:
                freecashflowDict[freecashflow['asOfDate']] = freecashflow['reportedValue']['raw']

    # sort dicts in descending order, from newest to oldest
    freecasflowDictSorted = sortDictDescending(freecashflowDict)

    # create an empty pandas data frame
    df = DataFrame()

    # add diluted eps data
    for k,v in freecasflowDictSorted.items():
        df.loc['freeCashFlow', k] = v

    return df

def load_KeyStatistics(symbol):
    url = "https://finance.yahoo.com/quote/" + symbol + "/key-statistics?p=" + symbol

    sharesOutstanding = None
    html = _requests.get(url=url).text

    json_str = html.split('root.App.main =')[1].split(
        '(this)')[0].split(';\n}')[0].strip()
    
    if "QuoteSummaryStore" in html:
        sharesOutstanding = _json.loads(json_str)['context']['dispatcher']['stores']['QuoteSummaryStore']['defaultKeyStatistics']['sharesOutstanding']['raw']
        marketCap = _json.loads(json_str)['context']['dispatcher']['stores']['QuoteSummaryStore']['price']['marketCap']['raw']

    # create an empty pandas data frame
    keyStatisticDict =	{
        "sharesOutstanding": sharesOutstanding,
        "marketCap": marketCap
    }
    return keyStatisticDict

def sortDictDescending(dictionary):
    return dict(reversed(sorted(dictionary.items())))