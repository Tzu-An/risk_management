"""Common Functions"""
import json
from pprint import pprint
from datetime import datetime

DATE_FORMAT = "%Y/%m/%d"

def load_json(fname):
    with open(fname) as f:
        return json.load(f)

def show_result(result, title):
    print(f"{title}:")
    pprint(result)

def parse_date(inp_date):
    try:
        return datetime.strptime(inp_date, DATE_FORMAT).date()
    except ValueError as err:
        err.args = (f"Date should be in the format {DATE_FORMAT}",)
        raise err

def form_date_string(inp_date):
    return datetime.strftime(inp_date, DATE_FORMAT)