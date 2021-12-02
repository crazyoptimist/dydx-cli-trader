import os
import time
from dotenv import load_dotenv
from dydx3 import Client
from dydx3.constants import API_HOST_MAINNET, NETWORK_ID_MAINNET, \
        ORDER_SIDE_BUY, ORDER_SIDE_SELL, \
        ORDER_TYPE_LIMIT, ORDER_TYPE_TRAILING_STOP, ORDER_TYPE_TAKE_PROFIT, \
        ORDER_STATUS_OPEN, ORDER_STATUS_PENDING, ORDER_STATUS_FILLED, ORDER_STATUS_UNTRIGGERED, \
        POSITION_STATUS_OPEN, POSITION_STATUS_CLOSED
from web3 import Web3
import pandas as pd
import numpy as np
from pprint import pprint


load_dotenv()
WEB3_PROVIDER_URL = 'https://mainnet.infura.io/v3/' + os.getenv('INFURA_PROJECT_ID')
# multiply of standard deviation
DEVIATION_THRESHOLD = 2.5
CANDLE_RESOLUTION = '1HOUR'
TARGET_MARKET = os.getenv('TARGET_MARKET')
ORDER_SIZE = os.getenv('ORDER_SIZE')
ORDER_SIDE = os.getenv('ORDER_SIDE')
TRAILING_PERCENT = 5
PRICE_DELTA = 0.055


api_key_credentials = {
    'key': os.getenv('API_KEY'),
    'passphrase': os.getenv('API_PASSPHRASE'),
    'secret': os.getenv('API_SECRET')
}

client = Client(
    network_id=NETWORK_ID_MAINNET,
    host=API_HOST_MAINNET,
    default_ethereum_address=os.getenv('ETH_ADDRESS'),
    web3=Web3(Web3.HTTPProvider(WEB3_PROVIDER_URL)),
    stark_private_key=os.getenv('STARK_PRIVATE_KEY'),
    api_key_credentials=api_key_credentials
)


class DydxData:
    def __init__(self):
        candles_response = client.public.get_candles(
            market=TARGET_MARKET,
            resolution=CANDLE_RESOLUTION,
            limit=100
        )
        self.data = candles_response.data['candles']
        self.df = pd.DataFrame(self.data)
        self.df['close'] = self.df['close'].astype(float)

    def find_z(self):
        mean = self.df['close'].mean()
        std = np.std(self.df['close'])
        z_score = (self.df['close'].iloc[0] - mean)/std
        return z_score


def place_order(order_params):
    order_creation_response = client.private.create_order(**order_params)
    pprint(order_creation_response.data)


def job():
    dydx_data = DydxData()
    z_score = dydx_data.find_z()

    markets_response = client.public.get_markets()
    index_price = float(markets_response.data['markets'][TARGET_MARKET]['indexPrice'])

    order_params = {
        'position_id': os.getenv('POSITION_ID'),
        'market': TARGET_MARKET,
        'post_only': False,
        'size': ORDER_SIZE,
        'limit_fee': 0.001,
        'expiration_epoch_seconds': int(time.time()) + 4 * 7 * 1440 * 60,
    }
    if ORDER_SIDE == 'BUY':
        buy_order_params = {
            **order_params,
            'order_type': ORDER_TYPE_LIMIT,
            'side': ORDER_SIDE_BUY,
            'price': str(round(index_price * (1 + PRICE_DELTA), 3))
        }
        place_order(buy_order_params)
        sell_order_params = {
            **order_params,
            'order_type': ORDER_TYPE_TRAILING_STOP,
            'side': ORDER_SIDE_SELL,
            'trailing_percent': -TRAILING_PERCENT,
            'price': str(round(index_price * (1 - PRICE_DELTA), 3))
        }
        place_order(sell_order_params)
        return
    elif ORDER_SIDE == 'SELL':
        sell_order_params = {
            **order_params,
            'order_type': ORDER_TYPE_LIMIT,
            'side': ORDER_SIDE_SELL,
            'price': str(round(index_price * (1 - PRICE_DELTA), 3))
        }
        place_order(sell_order_params)
        stop_order_params = {
            **order_params,
            'order_type': ORDER_TYPE_TRAILING_STOP,
            'side': ORDER_SIDE_BUY,
            'trailing_percent': TRAILING_PERCENT,
            'price': str(round(index_price * (1 + PRICE_DELTA), 3))
        }
        place_order(stop_order_params)
        return


job()
