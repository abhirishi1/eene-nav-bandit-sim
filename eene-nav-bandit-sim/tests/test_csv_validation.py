# Copyright 2023 Volvo Car Corporation
# Licensed under Apache 2.0.

import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from util.csv_validation import check_required_columns, ROAD_GRAPH_COLUMNS

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_road_graph_df():
    return pd.DataFrame({'from_id': ['A', 'B', 'B', 'C'],
                         'from_y': [0., 0., 0., 0.],
                         'from_x': [0., 1., 1., 2.],
                         'to_id': ['B', 'A', 'C', 'B'],
                         'to_y': [0., 0., 0., 0.],
                         'to_x': [1., 0., 2., 1.],
                         'mean_consumption': [100., 100., 200., 200.],
                         'mean_time': [10., 10., 20., 20.]})


def create_charging_station_df():
    return pd.DataFrame({'station_id': ['S_A', 'S_C'],
                         'node_id': ['A', 'C'],
                         'node_y': [0., 0.],
                         'node_x': [0., 2.],
                         'power': [50000., 100000.]})


def test_malformed_road_csv_names_the_column():
    missing_column_df = create_road_graph_df().drop(columns=['mean_time'])
    with pytest.raises(ValueError, match="road.csv is missing required column 'mean_time'"):
        check_required_columns(missing_column_df, ROAD_GRAPH_COLUMNS, 'road.csv')

    blank_value_df = create_road_graph_df()
    blank_value_df.loc[2, 'mean_time'] = np.nan
    with pytest.raises(ValueError, match="road.csv line 4: column 'mean_time' is blank"):
        check_required_columns(blank_value_df, ROAD_GRAPH_COLUMNS, 'road.csv')


def test_valid_csvs_preprocess_as_before(tmp_path):
    road_csv_path = str(tmp_path / 'road.csv')
    station_csv_path = str(tmp_path / 'stations.csv')
    create_road_graph_df().to_csv(road_csv_path, index=False)
    create_charging_station_df().to_csv(station_csv_path, index=False)

    result = subprocess.run([sys.executable, 'charging_graph_preprocesser.py',
                             '--road-graph-csv-path', road_csv_path,
                             '--charging-station-csv-path', station_csv_path,
                             '--output-dir', str(tmp_path) + os.sep],
                            cwd=CODE_DIR, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    np.testing.assert_array_equal(np.load(str(tmp_path / 'complete_time_array.npy')), [[0., 30.], [30., 0.]])
    np.testing.assert_array_equal(np.load(str(tmp_path / 'complete_consumption_array.npy')), [[0., 300.], [300., 0.]])
    ids_df = pd.read_csv(str(tmp_path / 'charging_graph_ids.csv'))
    assert ids_df['station_id'].tolist() == ['S_A', 'S_C']
