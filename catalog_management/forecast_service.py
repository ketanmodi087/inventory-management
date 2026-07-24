import logging
import pandas as pd
from prophet import Prophet
from django.db import connections
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing

logger = logging.getLogger(__name__)


def prophet_forecast(articulo, months=6):
    """
    Runs Prophet forecasting for a single product.
    """
    sql = """
    SELECT date_trunc('month', "DS")::date AS ds,
           SUM("Y") AS y
    FROM ims_items_sales_history
    WHERE "ARTICULO" = %s AND date_trunc('month', "DS") < date_trunc('month', CURRENT_DATE)
    GROUP BY date_trunc('month', "DS")
    ORDER BY ds;
    """
    try:
        df = pd.read_sql(sql, connections['default'], params=[articulo])

        if df.empty:
            return []
        df['ds'] = pd.to_datetime(df['ds'])
        df['y'] = df['y'].astype(float)
        df = df.sort_values("ds")
        df = df.set_index("ds")
        monthly = df.resample("ME").sum().fillna(0).reset_index()
        model = Prophet()
        model.fit(monthly)
        future = model.make_future_dataframe(periods=months, freq='ME')
        result = model.predict(future)
        fc = result[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
        return fc.tail(months).to_dict(orient='records')
    except (ValueError, KeyError) as e:
        logger.info("Prophet error:", e)
        return []


def sarima_forecast(articulo, periods: int = 6):
    sql = """
    SELECT date_trunc('month', "DS")::date AS fecha,
           SUM("Y") AS cantinad
    FROM ims_items_sales_history
    WHERE "ARTICULO" = %s AND date_trunc('month', "DS") < date_trunc('month', CURRENT_DATE)
    GROUP BY date_trunc('month', "DS")
    ORDER BY fecha;
    """
    df = pd.read_sql(sql, connections['default'], params=[articulo])
    try:
        if df.empty:
            return {}
        df['fecha'] = pd.to_datetime(df['fecha'])
        df['cantinad'] = df['cantinad'].astype(float)

        df = df.sort_values("fecha")
        df = df.set_index("fecha")

        monthly = df.resample("ME").sum().fillna(0)

        # SARIMA order (you can tune these)

        # order = (1, 1, 1)
        order = (1, 1, 3)  # adjusted for MA 3
        seasonal_order = (1, 1, 1, 12)
        model = SARIMAX(monthly, order=order, seasonal_order=seasonal_order, freq='ME',
                        enforce_stationarity=False, enforce_invertibility=False)
        fitted = model.fit(disp=False)

        forecast = fitted.forecast(steps=periods)
        return {str(k.date()): float(v) for k, v in forecast.items()}

    except (ValueError, KeyError) as e:
        logger.info("SARIMA error:", e)
        return {}


def holt_winters_forecast(
        articulo,
        periods: int = 6,
        seasonal_periods: int = 12,  # monthly seasonality
        trend: str = "add",
        seasonal: str = "add"
):
    """
    Holt-Winters (Triple Exponential Smoothing) forecast.
    Works on monthly aggregated sales from ims_items_sales_history.
    """
    sql = """
    SELECT date_trunc('month', "DS")::date AS fecha,
           SUM("Y") AS cantidad
    FROM ims_items_sales_history
    WHERE "ARTICULO" = %s AND date_trunc('month', "DS") < date_trunc('month', CURRENT_DATE)
    GROUP BY date_trunc('month', "DS")
    ORDER BY fecha;
    """

    try:
        df = pd.read_sql(sql, connections['default'], params=[articulo])
        if df.empty:
            return {}

        df['fecha'] = pd.to_datetime(df['fecha'])
        df['cantidad'] = df['cantidad'].astype(float)
        df = df.sort_values("fecha")
        df = df.set_index("fecha")

        # fill missing months with zero
        monthly = df.resample("ME").sum().fillna(0)

        model = ExponentialSmoothing(monthly, trend=trend, seasonal=seasonal, seasonal_periods=seasonal_periods)

        fitted = model.fit()

        forecast = fitted.forecast(periods)

        # Return format consistent with SARIMA
        return {str(k.date()): float(v) for k, v in forecast.items()}

    except Exception as e:
        logger.info("HW error:", e)
        return {}
