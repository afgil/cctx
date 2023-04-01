# -*- coding: utf-8 -*-

# PLEASE DO NOT EDIT THIS FILE, IT IS GENERATED AND WILL BE OVERWRITTEN:
# https://github.com/ccxt/ccxt/blob/master/CONTRIBUTING.md#how-to-contribute-code

import ccxt.async_support
from ccxt.async_support.base.ws.cache import ArrayCache, ArrayCacheBySymbolById, ArrayCacheByTimestamp
import hashlib
from ccxt.async_support.base.ws.client import Client
from typing import Optional
from ccxt.base.errors import NotSupported
from ccxt.base.errors import AuthenticationError


class cryptocom(ccxt.async_support.cryptocom):

    def describe(self):
        return self.deep_extend(super(cryptocom, self).describe(), {
            'has': {
                'ws': True,
                'watchBalance': True,
                'watchTicker': True,
                'watchTickers': False,  # for now
                'watchMyTrades': True,
                'watchTrades': True,
                'watchOrderBook': True,
                'watchOrders': True,
                'watchOHLCV': True,
            },
            'urls': {
                'api': {
                    'ws': {
                        'public': 'wss://stream.crypto.com/v2/market',
                        'private': 'wss://stream.crypto.com/v2/user',
                    },
                },
                'test': {
                    'public': 'wss://uat-stream.3ona.co/v2/market',
                    'private': 'wss://uat-stream.3ona.co/v2/user',
                },
            },
            'options': {
            },
            'streaming': {
            },
        })

    async def pong(self, client, message):
        # {
        #     "id": 1587523073344,
        #     "method": "public/heartbeat",
        #     "code": 0
        # }
        await client.send({'id': self.safe_integer(message, 'id'), 'method': 'public/respond-heartbeat'})

    async def watch_order_book(self, symbol: str, limit: Optional[int] = None, params={}):
        """
        watches information on open orders with bid(buy) and ask(sell) prices, volumes and other data
        see https://exchange-docs.crypto.com/spot/index.html#book-instrument_name-depth
        :param str symbol: unified symbol of the market to fetch the order book for
        :param int|None limit: the maximum amount of order book entries to return
        :param dict params: extra parameters specific to the cryptocom api endpoint
        :returns dict: A dictionary of `order book structures <https://docs.ccxt.com/#/?id=order-book-structure>` indexed by market symbols
        """
        await self.load_markets()
        market = self.market(symbol)
        if not market['spot']:
            raise NotSupported(self.id + ' watchOrderBook() supports spot markets only')
        messageHash = 'book' + '.' + market['id']
        orderbook = await self.watch_public(messageHash, params)
        return orderbook.limit()

    def handle_order_book_snapshot(self, client: Client, message):
        # full snapshot
        #
        # {
        #     "instrument_name":"LTC_USDT",
        #     "subscription":"book.LTC_USDT.150",
        #     "channel":"book",
        #     "depth":150,
        #     "data": [
        #          {
        #              'bids': [
        #                  [122.21, 0.74041, 4]
        #              ],
        #              'asks': [
        #                  [122.29, 0.00002, 1]
        #              ]
        #              't': 1648123943803,
        #              's':754560122
        #          }
        #      ]
        # }
        #
        messageHash = self.safe_string(message, 'subscription')
        marketId = self.safe_string(message, 'instrument_name')
        market = self.safe_market(marketId)
        symbol = market['symbol']
        data = self.safe_value(message, 'data')
        data = self.safe_value(data, 0)
        timestamp = self.safe_integer(data, 't')
        snapshot = self.parse_order_book(data, symbol, timestamp)
        snapshot['nonce'] = self.safe_integer(data, 's')
        orderbook = self.safe_value(self.orderbooks, symbol)
        if orderbook is None:
            limit = self.safe_integer(message, 'depth')
            orderbook = self.order_book({}, limit)
        orderbook.reset(snapshot)
        self.orderbooks[symbol] = orderbook
        client.resolve(orderbook, messageHash)

    async def watch_trades(self, symbol: str, since: Optional[int] = None, limit: Optional[int] = None, params={}):
        """
        get the list of most recent trades for a particular symbol
        :param str symbol: unified symbol of the market to fetch trades for
        :param int|None since: timestamp in ms of the earliest trade to fetch
        :param int|None limit: the maximum amount of trades to fetch
        :param dict params: extra parameters specific to the cryptocom api endpoint
        :returns [dict]: a list of `trade structures <https://docs.ccxt.com/en/latest/manual.html?#public-trades>`
        """
        await self.load_markets()
        market = self.market(symbol)
        symbol = market['symbol']
        if not market['spot']:
            raise NotSupported(self.id + ' watchTrades() supports spot markets only')
        messageHash = 'trade' + '.' + market['id']
        trades = await self.watch_public(messageHash, params)
        if self.newUpdates:
            limit = trades.getLimit(symbol, limit)
        return self.filter_by_since_limit(trades, since, limit, 'timestamp', True)

    def handle_trades(self, client: Client, message):
        #
        # {
        #     code: 0,
        #     method: 'subscribe',
        #     result: {
        #       instrument_name: 'BTC_USDT',
        #       subscription: 'trade.BTC_USDT',
        #       channel: 'trade',
        #       data: [
        #             {
        #                 "dataTime":1648122434405,
        #                 "d":"2358394540212355488",
        #                 "s":"SELL",
        #                 "p":42980.85,
        #                 "q":0.002325,
        #                 "t":1648122434404,
        #                 "i":"BTC_USDT"
        #              }
        #              (...)
        #       ]
        # }
        #
        channel = self.safe_string(message, 'channel')
        marketId = self.safe_string(message, 'instrument_name')
        symbolSpecificMessageHash = self.safe_string(message, 'subscription')
        market = self.safe_market(marketId)
        symbol = market['symbol']
        stored = self.safe_value(self.trades, symbol)
        if stored is None:
            limit = self.safe_integer(self.options, 'tradesLimit', 1000)
            stored = ArrayCache(limit)
            self.trades[symbol] = stored
        data = self.safe_value(message, 'data', [])
        parsedTrades = self.parse_trades(data, market)
        for j in range(0, len(parsedTrades)):
            stored.append(parsedTrades[j])
        client.resolve(stored, symbolSpecificMessageHash)
        client.resolve(stored, channel)

    async def watch_my_trades(self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None, params={}):
        """
        watches information on multiple trades made by the user
        :param str symbol: unified market symbol of the market orders were made in
        :param int|None since: the earliest time in ms to fetch orders for
        :param int|None limit: the maximum number of  orde structures to retrieve
        :param dict params: extra parameters specific to the cryptocom api endpoint
        :returns [dict]: a list of [order structures]{@link https://docs.ccxt.com/#/?id=order-structure
        """
        await self.load_markets()
        market = None
        if symbol is not None:
            market = self.market(symbol)
            symbol = market['symbol']
        defaultType = self.safe_string(self.options, 'defaultType', 'spot')
        messageHash = 'user.margin.trade' if (defaultType == 'margin') else 'user.trade'
        messageHash = (messageHash + '.' + market['id']) if (market is not None) else messageHash
        trades = await self.watch_private(messageHash, params)
        if self.newUpdates:
            limit = trades.getLimit(symbol, limit)
        return self.filter_by_symbol_since_limit(trades, symbol, since, limit, True)

    async def watch_ticker(self, symbol: str, params={}):
        """
        watches a price ticker, a statistical calculation with the information calculated over the past 24 hours for a specific market
        :param str symbol: unified symbol of the market to fetch the ticker for
        :param dict params: extra parameters specific to the cryptocom api endpoint
        :returns dict: a `ticker structure <https://docs.ccxt.com/#/?id=ticker-structure>`
        """
        await self.load_markets()
        market = self.market(symbol)
        if not market['spot']:
            raise NotSupported(self.id + ' watchTicker() supports spot markets only')
        messageHash = 'ticker' + '.' + market['id']
        return await self.watch_public(messageHash, params)

    def handle_ticker(self, client: Client, message):
        #
        # {
        #     "info":{
        #        "instrument_name":"BTC_USDT",
        #        "subscription":"ticker.BTC_USDT",
        #        "channel":"ticker",
        #        "data":[
        #           {
        #              "i":"BTC_USDT",
        #              "b":43063.19,
        #              "k":43063.2,
        #              "a":43063.19,
        #              "t":1648121165658,
        #              "v":43573.912409,
        #              "h":43498.51,
        #              "l":41876.58,
        #              "c":1087.43
        #           }
        #        ]
        #     }
        #  }
        #
        messageHash = self.safe_string(message, 'subscription')
        marketId = self.safe_string(message, 'instrument_name')
        market = self.safe_market(marketId)
        data = self.safe_value(message, 'data', [])
        for i in range(0, len(data)):
            ticker = data[i]
            parsed = self.parse_ticker(ticker, market)
            symbol = parsed['symbol']
            self.tickers[symbol] = parsed
            client.resolve(parsed, messageHash)

    async def watch_ohlcv(self, symbol: str, timeframe='1m', since: Optional[int] = None, limit: Optional[int] = None, params={}):
        """
        watches historical candlestick data containing the open, high, low, and close price, and the volume of a market
        :param str symbol: unified symbol of the market to fetch OHLCV data for
        :param str timeframe: the length of time each candle represents
        :param int|None since: timestamp in ms of the earliest candle to fetch
        :param int|None limit: the maximum amount of candles to fetch
        :param dict params: extra parameters specific to the cryptocom api endpoint
        :returns [[int]]: A list of candles ordered, open, high, low, close, volume
        """
        await self.load_markets()
        market = self.market(symbol)
        symbol = market['symbol']
        if not market['spot']:
            raise NotSupported(self.id + ' watchOHLCV() supports spot markets only')
        interval = self.safe_string(self.timeframes, timeframe, timeframe)
        messageHash = 'candlestick' + '.' + interval + '.' + market['id']
        ohlcv = await self.watch_public(messageHash, params)
        if self.newUpdates:
            limit = ohlcv.getLimit(symbol, limit)
        return self.filter_by_since_limit(ohlcv, since, limit, 0, True)

    def handle_ohlcv(self, client: Client, message):
        #
        #  {
        #       instrument_name: 'BTC_USDT',
        #       subscription: 'candlestick.1m.BTC_USDT',
        #       channel: 'candlestick',
        #       depth: 300,
        #       interval: '1m',
        #       data: [[Object]]
        #   }
        #
        messageHash = self.safe_string(message, 'subscription')
        marketId = self.safe_string(message, 'instrument_name')
        market = self.safe_market(marketId)
        symbol = market['symbol']
        interval = self.safe_string(message, 'interval')
        timeframe = self.find_timeframe(interval)
        self.ohlcvs[symbol] = self.safe_value(self.ohlcvs, symbol, {})
        stored = self.safe_value(self.ohlcvs[symbol], timeframe)
        if stored is None:
            limit = self.safe_integer(self.options, 'OHLCVLimit', 1000)
            stored = ArrayCacheByTimestamp(limit)
            self.ohlcvs[symbol][timeframe] = stored
        data = self.safe_value(message, 'data')
        for i in range(0, len(data)):
            tick = data[i]
            parsed = self.parse_ohlcv(tick, market)
            stored.append(parsed)
        client.resolve(stored, messageHash)

    async def watch_orders(self, symbol: Optional[str] = None, since: Optional[int] = None, limit: Optional[int] = None, params={}):
        """
        watches information on multiple orders made by the user
        :param str|None symbol: unified market symbol of the market orders were made in
        :param int|None since: the earliest time in ms to fetch orders for
        :param int|None limit: the maximum number of  orde structures to retrieve
        :param dict params: extra parameters specific to the cryptocom api endpoint
        :returns [dict]: a list of `order structures <https://docs.ccxt.com/#/?id=order-structure>`
        """
        await self.load_markets()
        market = None
        if symbol is not None:
            market = self.market(symbol)
            symbol = market['symbol']
        defaultType = self.safe_string(self.options, 'defaultType', 'spot')
        messageHash = 'user.margin.order' if (defaultType == 'margin') else 'user.order'
        messageHash = (messageHash + '.' + market['id']) if (market is not None) else messageHash
        orders = await self.watch_private(messageHash, params)
        if self.newUpdates:
            limit = orders.getLimit(symbol, limit)
        return self.filter_by_symbol_since_limit(orders, symbol, since, limit, True)

    def handle_orders(self, client: Client, message, subscription=None):
        #
        # {
        #     "method": "subscribe",
        #     "result": {
        #       "instrument_name": "ETH_CRO",
        #       "subscription": "user.order.ETH_CRO",
        #       "channel": "user.order",
        #       "data": [
        #         {
        #           "status": "ACTIVE",
        #           "side": "BUY",
        #           "price": 1,
        #           "quantity": 1,
        #           "order_id": "366455245775097673",
        #           "client_oid": "my_order_0002",
        #           "create_time": 1588758017375,
        #           "update_time": 1588758017411,
        #           "type": "LIMIT",
        #           "instrument_name": "ETH_CRO",
        #           "cumulative_quantity": 0,
        #           "cumulative_value": 0,
        #           "avg_price": 0,
        #           "fee_currency": "CRO",
        #           "time_in_force":"GOOD_TILL_CANCEL"
        #         }
        #       ],
        #       "channel": "user.order.ETH_CRO"
        #     }
        #
        channel = self.safe_string(message, 'channel')
        symbolSpecificMessageHash = self.safe_string(message, 'subscription')
        orders = self.safe_value(message, 'data', [])
        ordersLength = len(orders)
        if ordersLength > 0:
            if self.orders is None:
                limit = self.safe_integer(self.options, 'ordersLimit', 1000)
                self.orders = ArrayCacheBySymbolById(limit)
            stored = self.orders
            parsed = self.parse_orders(orders)
            for i in range(0, len(parsed)):
                stored.append(parsed[i])
            client.resolve(stored, symbolSpecificMessageHash)
            # non-symbol specific
            client.resolve(stored, channel)

    async def watch_balance(self, params={}):
        """
        query for balance and get the amount of funds available for trading or funds locked in orders
        :param dict params: extra parameters specific to the cryptocom api endpoint
        :returns dict: a `balance structure <https://docs.ccxt.com/en/latest/manual.html?#balance-structure>`
        """
        defaultType = self.safe_string(self.options, 'defaultType', 'spot')
        messageHash = 'user.margin.balance' if (defaultType == 'margin') else 'user.balance'
        return await self.watch_private(messageHash, params)

    def handle_balance(self, client: Client, message):
        #
        # {
        #     "method": "subscribe",
        #     "result": {
        #       "subscription": "user.balance",
        #       "channel": "user.balance",
        #       "data": [
        #         {
        #           "currency": "CRO",
        #           "balance": 99999999947.99626,
        #           "available": 99999988201.50826,
        #           "order": 11746.488,
        #           "stake": 0
        #         }
        #       ],
        #       "channel": "user.balance"
        #     }
        # }
        #
        messageHash = self.safe_string(message, 'subscription')
        data = self.safe_value(message, 'data')
        self.balance['info'] = data
        for i in range(0, len(data)):
            balance = data[i]
            currencyId = self.safe_string(balance, 'currency')
            code = self.safe_currency_code(currencyId)
            account = self.account()
            account['free'] = self.safe_string(balance, 'available')
            account['total'] = self.safe_string(balance, 'balance')
            self.balance[code] = account
            self.balance = self.safe_balance(self.balance)
        client.resolve(self.balance, messageHash)

    async def watch_public(self, messageHash, params={}):
        url = self.urls['api']['ws']['public']
        id = self.nonce()
        request = {
            'method': 'subscribe',
            'params': {
                'channels': [messageHash],
            },
            'nonce': id,
        }
        message = self.extend(request, params)
        return await self.watch(url, messageHash, message, messageHash)

    async def watch_private(self, messageHash, params={}):
        await self.authenticate()
        url = self.urls['api']['ws']['private']
        id = self.nonce()
        request = {
            'method': 'subscribe',
            'params': {
                'channels': [messageHash],
            },
            'nonce': id,
        }
        message = self.extend(request, params)
        return await self.watch(url, messageHash, message, messageHash)

    def handle_error_message(self, client: Client, message):
        # {
        #     id: 0,
        #     code: 10004,
        #     method: 'subscribe',
        #     message: 'invalid channel {"channels":["trade.BTCUSD-PERP"]}'
        # }
        errorCode = self.safe_integer(message, 'code')
        try:
            if errorCode:
                feedback = self.id + ' ' + self.json(message)
                self.throw_exactly_matched_exception(self.exceptions['exact'], errorCode, feedback)
                messageString = self.safe_value(message, 'message')
                if messageString is not None:
                    self.throw_broadly_matched_exception(self.exceptions['broad'], messageString, feedback)
            return False
        except Exception as e:
            if isinstance(e, AuthenticationError):
                messageHash = 'authenticated'
                client.reject(e, messageHash)
                if messageHash in client.subscriptions:
                    del client.subscriptions[messageHash]
            else:
                client.reject(e)
            return True

    def handle_message(self, client: Client, message):
        # ping
        # {
        #     "id": 1587523073344,
        #     "method": "public/heartbeat",
        #     "code": 0
        # }
        # auth
        #  {id: 1648132625434, method: 'public/auth', code: 0}
        # ohlcv
        # {
        #     code: 0,
        #     method: 'subscribe',
        #     result: {
        #       instrument_name: 'BTC_USDT',
        #       subscription: 'candlestick.1m.BTC_USDT',
        #       channel: 'candlestick',
        #       depth: 300,
        #       interval: '1m',
        #       data: [[Object]]
        #     }
        #   }
        # ticker
        # {
        #     "info":{
        #        "instrument_name":"BTC_USDT",
        #        "subscription":"ticker.BTC_USDT",
        #        "channel":"ticker",
        #        "data":[{}]
        #
        if self.handle_error_message(client, message):
            return
        subject = self.safe_string(message, 'method')
        if subject == 'public/heartbeat':
            self.handle_ping(client, message)
            return
        if subject == 'public/auth':
            self.handle_authenticate(client, message)
            return
        methods = {
            'candlestick': self.handle_ohlcv,
            'ticker': self.handle_ticker,
            'trade': self.handle_trades,
            'book': self.handle_order_book_snapshot,
            'user.order': self.handle_orders,
            'user.margin.order': self.handle_orders,
            'user.trade': self.handle_trades,
            'user.margin.trade': self.handle_trades,
            'user.balance': self.handle_balance,
            'user.margin.balance': self.handle_balance,
        }
        result = self.safe_value_2(message, 'result', 'info')
        channel = self.safe_string(result, 'channel')
        method = self.safe_value(methods, channel)
        if method is not None:
            method(client, result)

    def authenticate(self, params={}):
        self.check_required_credentials()
        url = self.urls['api']['ws']['private']
        client = self.client(url)
        messageHash = 'authenticated'
        future = self.safe_value(client.subscriptions, messageHash)
        if future is None:
            method = 'public/auth'
            nonce = str(self.nonce())
            auth = method + nonce + self.apiKey + nonce
            signature = self.hmac(self.encode(auth), self.encode(self.secret), hashlib.sha256)
            request = {
                'id': nonce,
                'nonce': nonce,
                'method': method,
                'api_key': self.apiKey,
                'sig': signature,
            }
            message = self.extend(request, params)
            future = self.watch(url, messageHash, message)
            client.subscriptions[messageHash] = future
        return future

    def handle_ping(self, client: Client, message):
        self.spawn(self.pong, client, message)

    def handle_authenticate(self, client: Client, message):
        #
        #  {id: 1648132625434, method: 'public/auth', code: 0}
        #
        client.resolve(message, 'authenticated')
