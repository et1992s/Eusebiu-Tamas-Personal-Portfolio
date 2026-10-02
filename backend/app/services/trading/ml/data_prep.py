import pickle
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import talib

warnings.filterwarnings('ignore')
sns.set_style('whitegrid')
deciles = np.arange(0.1, 1, 0.1)
idx = pd.IndexSlice

from pathlib import Path
import pandas as pd
from tqdm import tqdm

class DataPrep:
    def __init__(self, data_path='data/nasdaq100/1min_taq'):
        # Convert data_path to a Path object
        self.data_path = Path(data_path)
        self.tcols = ['openbartime', 'firsttradetime', 'highbidtime', 'highasktime', 'hightradetime',
                      'lowbidtime', 'lowasktime', 'lowtradetime', 'closebartime', 'lasttradetime']
        self.drop_cols = ['unknowntickvolume', 'cancelsize', 'tradeatcrossorlocked']
        self.columns = {
            'volumeweightprice': 'price', 'finravolume': 'fvolume', 'finravolumeweightprice': 'fprice',
            'uptickvolume': 'up', 'downtickvolume': 'down', 'repeatuptickvolume': 'rup',
            'repeatdowntickvolume': 'rdown', 'firsttradeprice': 'first', 'hightradeprice': 'high',
            'lowtradeprice': 'low', 'lasttradeprice': 'last', 'nbboquotecount': 'nbbo',
            'totaltrades': 'ntrades', 'openbidprice': 'obprice', 'openbidsize': 'obsize',
            'openaskprice': 'oaprice', 'openasksize': 'oasize', 'highbidprice': 'hbprice',
            'highbidsize': 'hbsize', 'highaskprice': 'haprice', 'highasksize': 'hasize',
            'lowbidprice': 'lbprice', 'lowbidsize': 'lbsize', 'lowaskprice': 'laprice',
            'lowasksize': 'lasize', 'closebidprice': 'cbprice', 'closebidsize': 'cbsize',
            'closeaskprice': 'caprice', 'closeasksize': 'casize', 'firsttradesize': 'firstsize',
            'hightradesize': 'highsize', 'lowtradesize': 'lowsize', 'lasttradesize': 'lastsize',
            'tradetomidvolweight': 'volweight', 'tradetomidvolweightrelative': 'volweightrel'
        }

    def extract_and_combine_data(self):
        data = []
        for f in tqdm(list(self.data_path.glob('*/**/*.csv.gz'))):
            df = pd.read_csv(f, parse_dates=[['Date', 'TimeBarStart']])
            df = (df.rename(columns=str.lower)
                  .drop(self.tcols + self.drop_cols, axis=1)
                  .rename(columns=self.columns)
                  .set_index('date_timebarstart')
                  .sort_index()
                  .between_time('9:30', '16:00')
                  .set_index('ticker', append=True)
                  .swaplevel()
                  .rename(columns=lambda x: x.replace('tradeat', 'at')))
            data.append(df)
        data = pd.concat(data).apply(pd.to_numeric, downcast='integer')
        data.index = data.index.rename(['ticker', 'date_time'])
        print(data.info(show_counts=True))
        data.to_pickle(self.data_path / 'algoseek.pkl')


class LoadingData:
    def __init__(self, data_file):
        self.data_file = data_file
        self.df = None

    def load_data(self):
        self.df = pd.read_pickle(self.data_file)
        print("Data loaded successfully!")

    def date_column(self):
        if self.df is not None:
            if isinstance(self.df.index, pd.MultiIndex):
                if 'date_time' in self.df.index.names:
                    self.df['date'] = pd.to_datetime(self.df.index.get_level_values('date_time').date)
                    print("Added 'date' column!")
                else:
                    print("Error: 'date_time' level not found in the index.")
            else:
                self.df['date'] = self.df.index.date
                print("Added 'date' column (single-level index)!")
        else:
            print("No data loaded. Please call load_data() first.")

    def save_data(self, output_file):
        if self.df is not None:
            self.df.to_pickle(output_file)
            print(f"Data saved to {output_file}!")
        else:
            print("No data loaded. Please call load_data() first.")

    def show_data_info(self):
        if self.df is not None:
            print("First few rows of data:")
            print(self.df.head())
            print("\nColumn names:")
            print(self.df.columns)
            print("\nIndex info:")
            print(self.df.index)

class Engineering:
    def __init__(self, df_path):
        self.df_path = Path(df_path)
        self.df = self.load_data()

    def load_data(self):
        if self.df_path.exists():
            with open(self.df_path, 'rb') as f:
                return pickle.load(f)
        raise FileNotFoundError("File doesn't exist")

    def feature_engineering(self):
        self.df.sort_index().groupby('ticker', group_keys=False)
        sort_by_ticker = self.df.sort_index().groupby('ticker', group_keys=False)

        data = pd.DataFrame(index=self.df.index)
        data['date'] = pd.factorize(self.df['date'], sort=True)[0]
        data['minute'] = pd.to_timedelta(data.index.get_level_values('date_time').time.astype(str))
        data.minute = (data.minute.dt.seconds.sub(data.minute.dt.seconds.min()).div(60).astype(int))

        returns = np.log(self.df['last'] / self.df.groupby('ticker')['last'].shift(1))
        volatility = returns.groupby('ticker').std() * np.sqrt(260)
        top_tickers = volatility.nlargest(6).index.tolist()
        print(f"Top 6 most volatile tickers:\n{volatility.loc[top_tickers].to_string()}")

        for f in ['up', 'down', 'rup', 'rdown']:
            data[f] = self.df.loc[:, f].div(self.df.volume).replace(np.inf, np.nan)
        print(data.loc[:, ['rup', 'up', 'rdown', 'down']].describe(deciles).to_latex())

        def compute_mfi():
            return sort_by_ticker.apply(lambda x: talib.MFI(x.high, x.low, x['last'],
                                                            x.volume, timeperiod=14).shift())

        def compute_cci():
            return sort_by_ticker.apply(lambda x: talib.CCI(x.high, x.low, x['last'],
                                                            timeperiod=14).shift())

        data['MFI'] = compute_mfi()
        data['CCI'] = compute_cci()
        print(data[['MFI', 'CCI']].describe(deciles).to_latex())

        def compute_sma5():
            return sort_by_ticker.apply(lambda x: talib.SMA(x['last'], timeperiod=5).shift())

        data['SMA_5'] = compute_sma5()

        def compute_sma10():
            return sort_by_ticker.apply(lambda x: talib.SMA(x['last'], timeperiod=10).shift())

        data['SMA_10'] = compute_sma10()

        def compute_sma20():
            return sort_by_ticker.apply(lambda x: talib.SMA(x['last'], timeperiod=20).shift())

        data['SMA_20'] = compute_sma20()

        def compute_ema5():
            return sort_by_ticker.apply(lambda x: talib.EMA(x['last'], timeperiod=5).shift())

        data['EMA_5'] = compute_ema5()

        def compute_ema20():
            return sort_by_ticker.apply(lambda x: talib.EMA(x['last'], timeperiod=20).shift())

        data['EMA_20'] = compute_ema20()

        def compute_macd():
            return data['EMA_5'] - data['EMA_20']

        data['MACD'] = compute_macd()

        def compute_macd_signal():
            return data['MACD'].ewm(span=9, adjust=False).mean()

        data['MACD_SIGNAL'] = compute_macd_signal()

        def compute_macd_hist():
            return data['MACD'] - data['MACD_SIGNAL']

        data['MACD_HIST'] = compute_macd_hist()

        def compute_stochrsi():
            return sort_by_ticker.apply(lambda x: talib.STOCHRSI(x['last'].ffill(),
                                                                 timeperiod=14,
                                                                 fastk_period=14,
                                                                 fastd_period=3,
                                                                 fastd_matype=0)[0])

        data['STOCHRSI'] = compute_stochrsi()

        def compute_willr():
            return sort_by_ticker.apply(lambda x: talib.WILLR(x.high, x.low, x['last'],
                                                              timeperiod=14).shift())

        data['WILLR'] = compute_willr()

        def compute_stoch(x, fastk_period=14, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0):
            slowk, slowd = talib.STOCH(x.high.ffill(), x.low.ffill(), x['last'].ffill(),
                                       fastk_period=fastk_period, slowk_period=slowk_period, slowk_matype=slowk_matype,
                                       slowd_period=slowd_period,slowd_matype=slowd_matype)
            return pd.DataFrame({'slowd': slowd,'slowk': slowk},index=x.index)

        data = data.join(sort_by_ticker.apply(compute_stoch))
        data.info(show_counts=True)

        features = ['rup', 'rdown', 'MFI', 'CCI', 'SMA_5', 'SMA_10', 'SMA_20', 'EMA_5', 'EMA_20',
                    'MACD', 'MACD_SIGNAL', 'MACD_HIST', 'STOCHRSI', 'WILLR', 'slowd', 'slowk']

        sample = data.sample(n=100000)
        fig, axes = plt.subplots(nrows=4, ncols=4, figsize=(26, 10))
        axes = axes.flatten()

        for i, feature in enumerate(features):
            sns.histplot(sample[feature], kde=True, ax=axes[i])
            axes[i].set_title(feature.upper())

        sns.despine()
        fig.tight_layout()
        plt.show()

        cmap = sns.diverging_palette(250, 10, as_cmap=True)
        corr = sample.loc[:, features].corr()
        sns.clustermap(corr, cmap=cmap, center=0, vmin=-1, vmax=1, annot=True, fmt=".2f", linewidths=0.5, )
        plt.show()

        final_data = pd.concat([data[features],
                                self.df[['first', 'high', 'low', 'last', 'price',
                                         'volume', 'atask', 'atbid']]], axis=1)

        final_data.info(show_counts=True)
        final_data.to_pickle('final_data.pkl')
