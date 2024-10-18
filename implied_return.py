from requests import get
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import style
import numpy as np
style.use('dark_background')

class ImpliedReturn:
    def __init__(self, asset: str = 'BTC') -> None:
        self.asset = asset
        self.kind = 'option'
        self.api_req = 'https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency='+self.asset+'&kind='+self.kind
        self.reload()
    
    def reload(self) -> None:
        r = get(self.api_req, verify=False)
        options = r.json()['result']
        opt = {'currency':    [option['instrument_name'].split('-')[0] for option in options],
                'expiry_date': [option['instrument_name'].split('-')[1] for option in options],
                'strike':      [int(option['instrument_name'].split('-')[2]) for option in options],
                'put_call':    [option['instrument_name'].split('-')[3] for option in options],
                'midprice':    [option['mid_price'] for option in options],
                'bidprice':    [option['bid_price'] for option in options],
                'askprice':    [option['ask_price'] for option in options],
                'real':        [True for option in options],
                'u_price':     [option['underlying_price'] for option in options]}
        self.df_opt = pd.DataFrame.from_dict(opt)
        self.exp_dates = self.df_opt['expiry_date'].unique()

    def get_expiry_date(self) -> list:
        return self.exp_dates

    def print_options(self, 
                      exp_date: str = None, 
                      put_call: str = 'C') -> None:

        if not exp_date:
            exp_date = self.exp_dates[-1]
        elif exp_date not in self.exp_dates:
            print(f'Expiry date not found, try one of {self.exp_dates}')
            return

        ax = self.df_opt[(self.df_opt['expiry_date'] == exp_date) & (self.df_opt['put_call'] == put_call)].sort_values('askprice').plot('strike', 'bidprice', c='r')
        self.df_opt[(self.df_opt['expiry_date'] == exp_date) & (self.df_opt['put_call'] == put_call)].sort_values('askprice').plot('strike', 'askprice', c='b', ax=ax)
        self.df_opt[(self.df_opt['expiry_date'] == exp_date) & (self.df_opt['put_call'] == put_call)].sort_values('askprice').plot('strike', 'midprice', c='g', ax=ax)
    
    def interpolate_pc(self, 
                       exp_date: str = None, 
                       put_call: str = 'P') -> pd.DataFrame:

        if not exp_date:
            exp_date = self.exp_dates[-1]
        elif exp_date not in self.exp_dates:
            print(f'Expiry date not found, try one of {self.exp_dates}')
            return

        # For put options
        dfp = self.df_opt[(self.df_opt['expiry_date'] == exp_date) & (self.df_opt['put_call'] == put_call)].sort_values('strike').reset_index(drop=True) 
        # dfp['butterfly'] = dfp['askprice'].shift(1) - 2*dfp['bidprice'] + dfp['askprice'].shift(-1)
        
        # Getting range to complete the strikes
        start = dfp['strike'].min()
        step = int((dfp['strike'] - dfp['strike'].shift(1)).min())
        end = dfp['strike'].max() + step
        strikes = [strike for strike in range(start, end, step)]

        new_strikes = [strike for strike in strikes if strike not in dfp['strike'].values]

        append_new_strikes = {'currency':    [dfp['currency'].unique()[0] for strike in new_strikes],
                              'expiry_date': [dfp['expiry_date'].unique()[0] for strike in new_strikes],
                              'strike':      [strike for strike in new_strikes],
                              'put_call':    [dfp['put_call'].unique()[0] for strike in new_strikes],
                              'midprice':    [np.nan for strike in new_strikes],
                              'bidprice':    [np.nan for strike in new_strikes],
                              'askprice':    [np.nan for strike in new_strikes],
                              'real':        [False for strike in new_strikes]}

        temp_df = pd.DataFrame.from_dict(append_new_strikes)
        # Replace the append method with pd.concat
        dfp = pd.concat([dfp, temp_df], ignore_index=True).sort_values('strike').reset_index(drop=True)

        dfp['askprice'] = dfp['askprice'].interpolate(method='linear')
        dfp['bidprice'] = dfp['bidprice'].interpolate(method='linear')
        dfp['midprice'] = (dfp['askprice'] + dfp['bidprice']) / 2

        # substitui preços possivelmente divergentes na média desses preços para facilitar contas
        dfp['u_price'] = [dfp['u_price'].unique()[~np.isnan(dfp['u_price'].unique())].mean() for _ in range(len(dfp['u_price']))]

        dfp['butterfly'] = (dfp['askprice'].shift(1) - 2*dfp['bidprice'] + dfp['askprice'].shift(-1)) * dfp['u_price']/ (dfp['strike'] - dfp['strike'].shift(1))
        dfp['s_butterfly'] = (-dfp['bidprice'].shift(1) + 2*dfp['askprice'] - dfp['bidprice'].shift(-1))  * dfp['u_price']/ (dfp['strike'] - dfp['strike'].shift(1))
        if put_call == 'P':
            dfp['l_spread'] = (dfp['askprice'] - dfp['bidprice'].shift(1)) * dfp['u_price']/ (dfp['strike'] - dfp['strike'].shift(1))
        elif put_call == 'C':
            dfc = dfp
            dfc['l_spread'] = (dfc['askprice'].shift(1) - dfc['bidprice']) * dfc['u_price']/ (dfc['strike'] - dfc['strike'].shift(1))

        return dfp

    def interpolate(self, exp_date=None) -> tuple:
        if not exp_date:
            exp_date = self.exp_dates[-1]
        elif exp_date not in self.exp_dates:
            print(f'Expiry date not found, try one of {self.exp_dates}')
            return

        self.dfp = self.interpolate_pc(exp_date, 'P')
        self.dfc = self.interpolate_pc(exp_date, 'C')
        return self.dfp, self.dfc
    
    def butterflies(self, 
                    exp_date: str = None,
                    lim_strike: int = None) -> None:

        if not exp_date:
            exp_date = self.exp_dates[-1]
        elif exp_date not in self.exp_dates:
            print(f'Expiry date not found, try one of {self.exp_dates}')
            return

        p, c = self.interpolate(exp_date)

        if not lim_strike:
            lim_strike = self.df_opt['u_price'].mode()[0] * 1.2

        ax = c[(c['strike'] < lim_strike) & (c['real'] == True)].plot(x='strike', y='butterfly', c='g', label='long call', title=exp_date)
        c[(c['strike'] < lim_strike) & (c['real'] == True)].plot(x='strike', y='s_butterfly', c='lime', label='short call', ax=ax)

        p[(p['strike'] < lim_strike) & (p['real'] == True)].plot(x='strike', y='butterfly', c='r', label='long put', ax=ax)
        p[(p['strike'] < lim_strike) & (p['real'] == True)].plot(x='strike', y='s_butterfly', c='magenta', label='short put', ax=ax)



if __name__ == '__main__':
    ir = ImpliedReturn(asset='BTC')
    ir.print_options()
    ir.butterflies()