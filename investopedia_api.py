from trade_common import Expiration, OrderLimit, TransactionType, OptionTrade, StockTrade
from api_models import OptionChain, Parsers, stock_quote, OptionScope
from session_singleton import Session
import warnings


class InvestopediaApi(object):
    def __init__(self, credentials, game_name=None, portfolio_id=None, game_id=None):
        Session.login(credentials)
        self.portfolios = Parsers.get_portfolios()
        if not self.portfolios:
            raise RuntimeError("No active Investopedia simulator portfolios were found.")
        self.portfolio = self.portfolios[0]
        if game_name is not None or portfolio_id is not None or game_id is not None:
            self.change_portfolio(game_name=game_name, game_id=game_id, portfolio_id=portfolio_id)
        print(
            "Initialized portfolio ID %s in game %s"
            % (self.portfolio.portfolio_id, self.portfolio.game_name)
        )

    def change_portfolio(self, game_name=None, game_id=None, portfolio_id=None):
        """Select a portfolio by its game name, game ID, or portfolio ID."""
        if game_name is not None:
            for portfolio in self.portfolios:
                if portfolio.game_name == game_name:
                    self.portfolio = portfolio
                    return
            warnings.warn("Portfolio not changed: no game named %s was found." % game_name)
            return

        if game_id is not None:
            for portfolio in self.portfolios:
                if str(portfolio.game_id) == str(game_id):
                    self.portfolio = portfolio
                    return
            warnings.warn("Portfolio not changed: no game ID %s was found." % game_id)
            return

        if portfolio_id is not None:
            for portfolio in self.portfolios:
                if str(portfolio.portfolio_id) == str(portfolio_id):
                    self.portfolio = portfolio
                    return
            warnings.warn("Portfolio not changed: no portfolio ID %s was found." % portfolio_id)
            return

        warnings.warn("Portfolio not changed: specify game_name, game_id, or portfolio_id.")

    def refresh_portfolio(self):
        current_portfolio_id = self.portfolio.portfolio_id
        self.portfolios = Parsers.get_portfolios()
        for portfolio in self.portfolios:
            if portfolio.portfolio_id == current_portfolio_id:
                self.portfolio = portfolio
                break
        else:
            raise RuntimeError("The selected portfolio is no longer available.")
        self.open_orders = self.portfolio.open_orders

    @staticmethod
    def get_option_chain(symbol):
        return OptionChain(symbol)

    @staticmethod
    def get_stock_quote(symbol):
        return stock_quote(symbol)


class StockTrade(StockTrade):
    pass


class OptionTrade(OptionTrade):
    pass


class Expiration(Expiration):
    pass


class OrderLimit(OrderLimit):
    pass


class TransactionType(TransactionType):
    pass


class OptionChain(OptionChain):
    pass


class OptionScope(OptionScope):
    pass
