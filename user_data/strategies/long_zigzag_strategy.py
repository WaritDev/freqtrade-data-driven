import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter
import talib.abstract as ta
from technical import qtpylib

from scipy.signal import argrelextrema


class LongZigZagStrategy(IStrategy):
    INTERFACE_VERSION = 3

    can_short: bool = False
    timeframe = "4h"
    startup_candle_count = 200

    minimal_roi = {"0": 0.3}  # 5%
    stoploss = -0.1

    trailing_stop = False

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)

        stoch_rsi = ta.STOCHRSI(dataframe, timeperiod=14, fastk_period=3, fastd_period=3)
        dataframe["stoch_rsi_k"] = stoch_rsi["fastk"]
        dataframe["stoch_rsi_d"] = stoch_rsi["fastd"]

        window = 10
        dataframe["zigzag_high"] = dataframe["high"].iloc[argrelextrema(dataframe["high"].values, np.greater_equal, order=window)[0]]
        dataframe["zigzag_low"] = dataframe["low"].iloc[argrelextrema(dataframe["low"].values, np.less_equal, order=window)[0]]

        dataframe["resistance"] = dataframe["zigzag_high"].ffill()
        dataframe["support"] = dataframe["zigzag_low"].ffill()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["close"] > dataframe["ema200"])
                &
                (
                    (dataframe["close"] > dataframe["resistance"].shift(1))
                    |
                    (
                        (dataframe["close"] > dataframe["support"])
                        & (dataframe["stoch_rsi_k"] > dataframe["stoch_rsi_d"])
                        & (dataframe["stoch_rsi_k"] < 30)
                    )
                )
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["stoch_rsi_k"] > 70)
                & (dataframe["stoch_rsi_k"] < dataframe["stoch_rsi_d"])
            ),
            "exit_long",
        ] = 1
        return dataframe