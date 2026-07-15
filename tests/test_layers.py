import pytest
import pandas as pd
import os

def test_csv_exists():
    assert os.path.exists("data/metrics.csv")

def test_csv_data():
    df = pd.read_csv("data/metrics.csv")
    assert len(df) > 0
    assert 'latency_p95_ms' in df.columns
    assert 'throughput_rps' in df.columns

def test_components():
    df = pd.read_csv("data/metrics.csv")
    components = df['component'].unique()
    assert 'checkoutservice' in components
    assert 'productcatalogservice' in components
    assert 'cartservice' in components

def test_parquet():
    assert os.path.exists("data/metrics.parquet")
