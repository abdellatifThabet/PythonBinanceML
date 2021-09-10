import requests
import json
import firebase_admin
import calendar
import time
from multiprocessing import Process
from sklearn.linear_model import LinearRegression
import numpy as np
import datetime
from sklearn.metrics import mean_squared_error
import random
import threading
import operator
from firebase_admin import db


def from_binance(symbol):
    try:
        url_binance = "https://api.binance.com/api/v3/ticker/price?symbol="
        xrp_response = requests.request('GET', url_binance + symbol.upper() +"USDT")
        return float(json.loads(xrp_response.text)['price'])
    except:
        return -1
def from_bitrue(symbol):
    try:
        url_BitTrue = "https://www.bitrue.com/api/v1/ticker/price?symbol="
        xrp_response = requests.request('GET', url_BitTrue + symbol.upper() +"USDT")
        return float(json.loads(xrp_response.text)['price'])
    except:
        return -1
def from_huobi(symbol):
    try:
        url_Huobi = "https://api.huobi.pro/market/detail/merged?symbol="
        xrp_response = requests.request('GET', url_Huobi + symbol.lower()+"usdt")
        return float(json.loads(xrp_response.text)['tick']['close'])
    except:
        return -1
def from_kucoin(symbol):
    try:
        url_kucoin = "https://api.kucoin.com/api/v1/prices"
        response = requests.request('GET', url_kucoin)
        r = json.loads(response.text)
        return float(r['data'][symbol.upper()])
    except:
        return -1
def from_ftx(symbol):
    try:
        url_ftx = "https://ftx.com/api/markets/XRP-PERP"
        response = requests.get('https://ftx.com/api/markets/'+ symbol.upper() + '-PERP').json()
        return float(response['result']['ask'])
    except:
        return -1

def get_data(asset,api):
    if api=='binance':
        return from_binance(asset)
    elif api=='bitrue':
        return from_bitrue(asset)
    elif api=='huobi':
        return from_huobi(asset)
    elif api=='kucoin':
        return from_kucoin(asset)
    elif api=='ftx':
        return from_ftx(asset)
    else:
        return 'api not supported !'


databaseURL = 'https://submit-prices-71f2e-default-rtdb.firebaseio.com/'
cred_object = firebase_admin.credentials.Certificate('submit-prices-71f2e-firebase-adminsdk-7ap2f-ca5b22301d.json')
default_app = firebase_admin.initialize_app(cred_object, {
    'databaseURL':databaseURL
    })



class PriceApp:

    def __init__(self, asset, api):
        self.asset = asset  #this variable containes the name of the asset(XRP,LTC,XLM,DOGE for example)
        self.api = api    # this variable contains the api's name from which we'll get the data(price)
        #self.submit_time = 0
        self.data = [] ## current epoch data points
        self.ref = db.reference('/'+api.lower()+'/'+asset.lower()) # this is a refrence to the firebase
        
    def get_api(self):
        return self.api
    
    def get_asset(self):
        return self.asset
    
    def get_ref(self):
        return self.ref
    
    def get_submit_time(self):
        return self.submit_time
        
    def get_data(self):
        return self.data
           
    def set_submit_time(self, nst):
        self.submit_time = nst
        
    def update_data(self):
        if(len(self.data)<6): ## here we fixed 6 data points because sometimes this might be more or less which is not accepted by the ML model
             # this function will update the current price
            self.data.append(get_data(self.asset, self.api))
    
    def reset_data(self):
        self.data = []
    
    def get_inputs(self):
        try:
            return self.ref.get()['inputs'][:-1]
        except:
            return 
    
    def get_outputs(self):
        try:
            return self.ref.get()['outputs']
        except:
            return
        
    def get_predicted(self):
        try:
            return self.ref.get()['predicted'][:-2]
        except:
            return
        
    def set_inputs(self, index, val):
        self.ref.child('inputs').update({ index: val})
    
    def set_outputs(self, index, val):
        self.ref.child('outputs').update({ index: val})
    
    def set_predicted(self, index, val):
        self.ref.child('predicted').update({ index: val})


def compute_error(instance):
    predicted_prices = instance.get_predicted()
    result_prices = instance.get_outputs()
    return mean_squared_error(predicted_prices, result_prices)

def predict_price(instance, lr):
    X = instance.get_inputs()
    Y = instance.get_ouputs()
    lr.fit(X, Y)
    return 


def run_epoch(instance):
    epoch_time = 120 # for now untill we get from aipRewards
    optimal_time =  30  #this value will be adjusted(how many seconds before the end of the epoch we'll start submitting)
    T1 = T2 = time.time()
    Refresh1 = 13  ## if we set 15 it wiil take more than 15 secs.
    instance.update_data()
    while(time.time() - T2 < epoch_time-optimal_time):
        if time.time() - T1 > Refresh1 :
            ## here we'll ping for data 
            instance.update_data()
            T1 = time.time()

        else:
            pass
    return



def Run_asset(instance):
    if(epoch_index == 1):
        run_epoch(instance)
        # calculate the average of last points:
        avg_xrp = sum(instance.get_data()) / len(instance.get_data())
        ## send inputs to database
        instance.set_inputs(epoch_index-1, instance.get_data())
        ## send predicted price to database
        instance.set_predicted(epoch_index-1, avg_xrp)
        ## send avg_xrp as predicted price to api
        ## ....................................
        ## at the end of each epoch we need to reset the current data
        instance.reset_data()
    elif(epoch_index == 2):
        run_epoch(instance)
        # reavel epoch #1 guess
        ## ....................................
        avg_xrp = sum(instance.get_data()) / len(instance.get_data())
        ## send inputs to database
        instance.set_inputs(epoch_index-1, instance.get_data())
        ## send predicted price to database
        instance.set_predicted(epoch_index-1, avg_xrp)
        ## send avg_xrp as predicted price to api
        ## .....................................
        instance.reset_data()
    else:
        ## get epoch #epoch_index-2 output price from api
        ## ....................................
        ## here we're just replacing the api result with random choice for testing
        result_price = random.uniform(1.1, 1.3)
        ## send output to corresponding inputs to database
        instance.set_outputs(epoch_index-3, result_price)

        # reavel epoch #epoch_index-1 guess
        ## ....................................
        lr =  LinearRegression()
        ## train ML model and run epoch in same time
        po = Process(target = run_epoch(instance))
        po.start()
        pp = Process(target = predict_price(instance, lr))
        pp.start()
        
        predicted_price = lr.predict([instance.get_data()])[0]
        #print('the predicted output price is :', predicted_price)
        ## send predicted price to database to calculate mse later
        instance.set_predicted(epoch_index-1, predicted_price)
        ## send inputs to database
        instance.set_inputs(epoch_index-1, instance.get_data())
        
        ## send predicted price to api  ## here we'll switch every 20 epoch to the api which performs the best (less mse value)
        if(not(best_mse.keys())):
            if(instance.get_api().lower() == 'binance'):
                print("send "+ instance.get_asset() +" to default api which is binance !")
                ## send all assets of binance (we took binance as default api)
                ## ...........................................................
        else:
            if(best_mse[instance.get_asset().lower()] == instance.get_api().lower()):
                print('send by '+instance.get_asset()+'_'+instance.get_api())
                ## .....................................
                
        ## calculating mse
        if(epoch_index % 5 == 0):
            mse = compute_error(instance)
            #instance.set_mse(epoch_index/20, mse)
            # save plot for mse for each instance to give a better visaulization
            
            ## add mse to an object to determine from which api are we going to use each 20 epoch
            all_mse[instance.get_asset().lower()].update({instance.get_api().lower() : mse})
            
        instance.reset_data()
    return

def multi_threading_fnct(lst):
    for i,l in enumerate(lst):
        exec('t'+str(i) +'= threading.Thread(target=Run_asset, args=([l]))')
        exec('t'+str(i)+'.start()')
    for i in range(len(lst)):
        exec('t'+str(i)+'.join()')
    return


xrp_binance = PriceApp('XRP','binance') 
ltc_binance = PriceApp('LTC','binance')
xlm_binance = PriceApp('XLM','binance') 
doge_binance = PriceApp('DOGE','binance')

xrp_bitrue = PriceApp('XRP','bitrue') 
ltc_bitrue = PriceApp('LTC','bitrue')
xlm_bitrue = PriceApp('XLM','bitrue') 
doge_bitrue = PriceApp('DOGE','bitrue')

xrp_huobi = PriceApp('XRP','huobi') 
ltc_huobi = PriceApp('LTC','huobi')
xlm_huobi = PriceApp('XLM','huobi') 
doge_huobi = PriceApp('DOGE','huobi')

xrp_kucoin = PriceApp('XRP','kucoin') 
ltc_kucoin = PriceApp('LTC','kucoin')
xlm_kucoin = PriceApp('XLM','kucoin') 
doge_kucoin = PriceApp('DOGE','kucoin')

xrp_ftx = PriceApp('XRP','ftx') 
ltc_ftx = PriceApp('LTC','ftx')
xlm_ftx = PriceApp('XLM','ftx') 
doge_ftx = PriceApp('DOGE','ftx')

lst = [xrp_binance, ltc_binance, xlm_binance, doge_binance,xrp_bitrue, ltc_bitrue, xlm_bitrue, doge_bitrue, xrp_huobi, ltc_huobi, xlm_huobi, doge_huobi, xrp_kucoin, ltc_kucoin, xlm_kucoin, doge_kucoin, xrp_ftx, ltc_ftx, xlm_ftx, doge_ftx]


if __name__ == '__main__':
    epoch_index=0
    all_mse = {'xrp':{},'ltc':{},'xlm':{},'doge':{}}
    best_mse = {}
    while True:
        epoch_index = epoch_index+1
        print(epoch_index)
        #
        multi_threading_fnct(lst)
        if(epoch_index % 5 ==0):
            for key, _ in all_mse.items():
                best_mse[key] = min(all_mse[key].items(), key=operator.itemgetter(1))[0]
