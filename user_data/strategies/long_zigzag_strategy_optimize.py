import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter
import talib.abstract as ta
from technical import qtpylib

from scipy.signal import argrelextrema


class LongZigZagStrategyOptimize(IStrategy):
    INTERFACE_VERSION = 3

    can_short: bool = False
    timeframe = "15m"
    startup_candle_count = 300 

    minimal_roi = {"0": 0.2} 
    stoploss = -0.1
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.06
    trailing_only_offset_is_reached = True

    use_exit_signal = True

    adx_min = IntParameter(15, 25, default=20, optimize=True, space="buy")
    zz_window = IntParameter(10, 30, default=20, optimize=True, space="buy")

    def _ema_slope(self, series: pd.Series, period: int = 200) -> pd.Series:
        ema = pd.Series(ta.EMA(series, timeperiod=period), index=series.index)
        slope = ema - ema.shift(1)
        return slope

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema200"] = pd.Series(
            ta.EMA(dataframe["close"], timeperiod=200), index=dataframe.index
        )
        dataframe["ema200_slope"] = self._ema_slope(dataframe["close"], 200)

        dataframe["adx"] = ta.ADX(dataframe)

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = (dataframe["atr"] / dataframe["close"]) * 100.0

        stoch_rsi = ta.STOCHRSI(
            dataframe, timeperiod=14, fastk_period=3, fastd_period=3
        )
        dataframe["stoch_rsi_k"] = stoch_rsi["fastk"]
        dataframe["stoch_rsi_d"] = stoch_rsi["fastd"]

        dataframe["vol_sma20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        window = int(self.zz_window.value) if hasattr(self, "zz_window") else 20
        highs_idx = argrelextrema(
            dataframe["high"].values, np.greater_equal, order=window
        )[0]
        lows_idx = argrelextrema(
            dataframe["low"].values, np.less_equal, order=window
        )[0]

        dataframe["zigzag_high"] = np.nan
        dataframe["zigzag_low"] = np.nan
        if len(highs_idx) > 0:
            dataframe.loc[
                dataframe.index[highs_idx], "zigzag_high"
            ] = dataframe["high"].iloc[highs_idx]
        if len(lows_idx) > 0:
            dataframe.loc[
                dataframe.index[lows_idx], "zigzag_low"
            ] = dataframe["low"].iloc[lows_idx]

        dataframe["resistance"] = dataframe["zigzag_high"].ffill()
        dataframe["support"] = dataframe["zigzag_low"].ffill()

        dataframe["dist_to_support"] = dataframe["close"] - dataframe["support"]
        dataframe["near_support"] = (
            (dataframe["dist_to_support"] >= 0)
            & (dataframe["dist_to_support"] <= 0.5 * dataframe["atr"])
        )

        dataframe["breakout_ok"] = (
            (dataframe["close"] > dataframe["resistance"] * 1.001)
            & (dataframe["volume"] > 1.2 * dataframe["vol_sma20"])
        )

        dataframe["bullish_close"] = dataframe["close"] > dataframe["open"]
        dataframe["stoch_cross_up_low"] = (
            qtpylib.crossed_above(dataframe["stoch_rsi_k"], dataframe["stoch_rsi_d"])
        ) & (dataframe["stoch_rsi_k"] < 30)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        adx_min = int(self.adx_min.value) if hasattr(self, "adx_min") else 20

        dataframe.loc[
            (
                (dataframe["close"] > dataframe["ema200"])
                & (dataframe["ema200_slope"] > 0)
                & (dataframe["adx"] >= adx_min)
                & (dataframe["atr_pct"] > 0.8)
                & (
                    dataframe["breakout_ok"]
                    | (
                        dataframe["near_support"]
                        & dataframe["bullish_close"]
                        & dataframe["stoch_cross_up_low"]
                    )
                )
                & (dataframe["volume"] > 0)
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

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 3},
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 30,
                "trade_limit": 5,
                "stop_duration_candles": 6,
                "max_allowed_drawdown": 0.2,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 2,
                "stop_duration_candles": 6,
                "only_per_pair": True,
            },
        ]