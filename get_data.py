#!/usr/bin/env python2

import urllib2
import csv
import re
import pytz
import pandas as pd

from bs4 import BeautifulSoup
from datetime import datetime
from pandas.io.data import DataReader
import requests


def getSP500List():
    site_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    hdr = {'User-Agent': 'Mozilla/5.0'}
    req = urllib2.Request(site_url, headers=hdr)
    page = urllib2.urlopen(req)
    soup = BeautifulSoup(page)

    table = soup.find('table', {'class': 'wikitable sortable'})
    sector_tickers = dict()
    for row in table.findAll('tr'):
        col = row.findAll('td')
        if len(col) > 0:
            stock_symb = str(col[0].string.strip())
            stock_symb.replace('-', '')
            category = str(col[3].string.strip()).lower().replace(' ', '_')
            sector_tickers[stock_symb] = category
    return sector_tickers


RENAME = {"Gross Margin %": "Gross Margin %",
            "Earnings Per Share [A-Z]*": "EPS",
            "Free Cash Flow [A-Z]* Mil": "Free Cash Flow",
            "Revenue [A-Z]* Mil": "Revenue"
            }

class gradComanyStats(object):
    """
        Using morning star ajax call.
        Can only get one stock at a time.
    """
    def __init__(self):
        """ List of url parameters -- for url formation """
        self.base_url = 'http://financials.morningstar.com/ajax/exportKR2CSV.html?&callback=?&t='
        self.end_url = '&region=usa&culture=en-US&cur=&order=asc'
        self.url_additional_params = ''
        self.stock_list = []
        self.basic_attrs = []
        self.info_dict = {}
        self.yearly_data = {}

    def set_stock_list(self, list):
        self.stock_list = list

    def set_attr_list(self, list):
        self.basic_attrs = list

    def buildUrl(self, stock):
        url = self.base_url + stock + self.end_url
        return url

    def grad_attr(self, data):
        dict = {}
        csv_data = csv.reader(data.split('\n'), delimiter=',')
        csv_list = list(csv_data)
        for attr in self.basic_attrs:
            for row in csv_list:
                if len(row) < 3: continue
                if re.search(attr, row[0]) != None:
                    l = []
                    for n in row[6:]:
                        # from 2016 - current
                        if n == '':
                            l.append(0)
                        else:
                            l.append(float(n.replace(',','')))
                    dict[RENAME[attr]] = l
                    break
        return dict

    def gradCompanyData(self):
        for s in self.stock_list:
            url = self.buildUrl(s)
            data = requests.get(url, stream=True)
            self.info_dict[s] = self.grad_attr(data.content)
        print self.info_dict

    def gradStockPrice(self):
        # 5y stock price from 2012 - 2017
        # Note that some stock on market < 5y; so be careful
        for s in self.stock_list:
            if "Stock Price" not in self.info_dict[s]:
                self.info_dict[s]["Price"] = []
            url = "http://performance.morningstar.com/perform/Performance/stock/exportStockPrice.action?t={}&" \
                 "pd=5y&freq=a&sd=&ed=&pg=0&culture=en-US&order=asc".format(s)
            data = requests.get(url, stream=True)
            csv_data = csv.reader(data.content.split('\n'), delimiter=',')
            for row in csv_data:
                if len(row)>5:
                    try:
                        # to avoid the float("Date) error
                        a = float(row[4])
                    except:
                        continue
                    # time; stock price; market price
                    self.info_dict[s]["Price"].append([row[0], float(row[4]), float(row[4])*int(row[5].replace(',',''))])

    def organizeYearlyData(self):
        '''
        organize data by year in order of:
        Price; Market Price; P/E; Revenue; EPS; Free Cash flow; Gross Margin; Revenue Growth; EPS Growth
        '''
        for s in self.stock_list:
            print s
            info = self.info_dict[s]
            self.yearly_data[s] = {}
            for y in range(2012, 2018):
                l = [info["Revenue"][y-2012], info["EPS"][y-2012], info["Free Cash Flow"][y-2012], info["Gross Margin %"][y-2012]]

                if 2017-y >= len(info["Price"]) or str(y) not in info["Price"][2017-y][0]:
                    l = [None, None, None] + l
                else:
                    price_l = info["Price"][2017-y]
                    eps = l[1]
                    l = [price_l[1], price_l[2], price_l[1]/eps if eps!=0 else 0] + l

                if y > 2012:
                    if(info["Revenue"][y-2013] != 0):
                        l.append(info["Revenue"][y-2012] / info["Revenue"][y-2013])
                    else:
                        l.append(None)
                    if info["EPS"][y-2013] != 0:
                        l.append(info["EPS"][y - 2012] / info["EPS"][y - 2013])
                    else:
                        l.append(None)
                self.yearly_data[s][str(y)] = l

    def filter(self, s):
        self.stock_list.remove(s)
        del self.info_dict[s]
        return

    def hardCritia(self):
        '''
        Filter critia:
        1. Company price has to be > 1 billion
        2. Have to make profit, which means EPS > 0
        3. Free cash flow >= Revenue
        4. latest PE <= 20
        '''
        for s in self.stock_list:
            if self.info_dict[s]["EPS"]<=0 or self.info_dict[s]["Price"][2]<=1:
                self.filter(s)
            elif self.info_dict[s]["Free Cash Flow"] < self.info_dict[s]["Revenue"]:
                self.filter(s)
            elif self.yearly_data["2016"][2]>20 or self.yearly_data["2016"][3]<self.yearly_data["2015"][3]:
                self.filter(s)
            elif not (self.yearly_data["2016"][8]>0 and self.yearly_data["2016"][2]/self.yearly_data["2016"][8]<1.2):
                self.filter(s)
            else:
                continue

if __name__ == '__main__':
    pp = gradComanyStats()
    #pp.set_stock_list(['AAPL','BABA'])
    sp500 = getSP500List().keys()
    pp.set_stock_list(sp500[0:100])
    basic_attrs = ["Gross Margin %", "Earnings Per Share [A-Z]*", "Free Cash Flow [A-Z]* Mil", "Revenue [A-Z]* Mil"]
    pp.set_attr_list(basic_attrs)
    pp.gradCompanyData()
    pp.gradStockPrice()
    pp.organizeYearlyData()
    print pp.yearly_data
    pp.hardCritia()
    print pp.stock_list

