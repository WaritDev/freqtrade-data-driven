FROM freqtradeorg/freqtrade:stable

WORKDIR /freqtrade

COPY user_data /freqtrade/user_data

RUN mkdir -p /freqtrade/user_data/logs /freqtrade/user_data/plot /freqtrade/user_data/strategies

EXPOSE 8080
ENV TZ=Asia/Bangkok

CMD ["trade","--config","/freqtrade/user_data/config.json","--logfile","/freqtrade/user_data/logs/freqtrade.log","--db-url","sqlite:////freqtrade/user_data/tradesv3.sqlite","--strategy","LongZigZagStrategyOptimize","--rest-api","--rest-host","0.0.0.0","--rest-port","8080"]