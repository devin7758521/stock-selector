# -*- coding: utf-8 -*-
"""
ETF Zhou K Filter Module
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import requests

logger = logging.getLogger("stock_selector.etf")

def filter_etf_weekly(cfg: dict) -> List[Dict]:
    return []
