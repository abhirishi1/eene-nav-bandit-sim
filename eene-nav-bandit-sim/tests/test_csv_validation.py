# Copyright 2023 Volvo Car Corporation
# Licensed under Apache 2.0.

import os
import subprocess
import sys

import numpy as np
import pandas as pd

from util.csv_validation import find_missing_data, ROAD_GRAPH_COLUMNS, CHARGING_STATION_COLUMNS

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


def run_preprocesser(tmp_path, road_graph_df, charging_station_df):
    road_csv_path = str(tmp_path / 'road.csv')
    station_csv_path = str(tmp_path / 'stations.csv')
    road_graph_df.to_csv(road_csv_path, index=False)
    charging_station_df.to_csv(station_csv_path, index=False)
    return subprocess.run([sys.executable, 'charging_graph_preprocesser.py',
                           '--road-graph-csv-path', road_csv_path,
                           '--charging-station-csv-path', station_csv_path,
                           '--output-dir', str(tmp_path) + os.sep],
                          cwd=CODE_DIR, capture_output=True, text=True)


def write_csv(tmp_path, file_name, text):
    csv_path = str(tmp_path / file_name)
    with open(csv_path, 'w', newline='') as csv_file:
        csv_file.write(text)
    return csv_path


def test_complete_csvs_have_no_missing_data(tmp_path):
    road_csv_path = str(tmp_path / 'road.csv')
    station_csv_path = str(tmp_path / 'stations.csv')
    create_road_graph_df().to_csv(road_csv_path, index=False)
    create_charging_station_df().to_csv(station_csv_path, index=False)
    assert find_missing_data(pd.read_csv(road_csv_path), ROAD_GRAPH_COLUMNS, road_csv_path) == []
    assert find_missing_data(pd.read_csv(station_csv_path), CHARGING_STATION_COLUMNS, station_csv_path) == []


def test_blank_values_are_highlighted_in_their_row(tmp_path):
    road_graph_df = create_road_graph_df()
    road_graph_df.loc[2, 'mean_time'] = np.nan
    road_graph_df.loc[2, 'mean_consumption'] = np.nan
    road_csv_path = str(tmp_path / 'road.csv')
    road_graph_df.to_csv(road_csv_path, index=False)
    problems = find_missing_data(pd.read_csv(road_csv_path), ROAD_GRAPH_COLUMNS, road_csv_path)
    assert len(problems) == 1
    assert problems[0].startswith("road.csv line 4: blank 'mean_consumption', 'mean_time'")
    assert 'from_id=B | ' in problems[0]
    assert 'mean_consumption=>>> MISSING <<< | mean_time=>>> MISSING <<<' in problems[0]


def test_space_only_cells_count_as_blank(tmp_path):
    station_csv_path = write_csv(tmp_path, 'stations.csv',
                                 'station_id,node_id,node_y,node_x,power\n'
                                 'S_A,A,0.0,0.0,50000\n'
                                 'S_C,C,0.0,2.0,   \n')
    problems = find_missing_data(pd.read_csv(station_csv_path), CHARGING_STATION_COLUMNS, station_csv_path)
    assert len(problems) == 1
    assert problems[0].startswith("stations.csv line 3: blank 'power'")


def test_line_numbers_count_empty_lines_and_multi_line_cells(tmp_path):
    station_csv_path = write_csv(tmp_path, 'stations.csv',
                                 'station_id,node_id,node_y,node_x,power\n'
                                 '"S\nA",A,0.0,0.0,50000\n'
                                 '\n'
                                 '   \n'
                                 'S_B,B,0.0,1.0,\n'
                                 '\r\n'
                                 'S_C,,0.0,2.0,100000\r\n')
    problems = find_missing_data(pd.read_csv(station_csv_path), CHARGING_STATION_COLUMNS, station_csv_path)
    assert [problem.split(':')[0] for problem in problems] == ['stations.csv line 6', 'stations.csv line 8']


def test_missing_column_is_reported(tmp_path):
    station_csv_path = str(tmp_path / 'stations.csv')
    create_charging_station_df().drop(columns=['power']).to_csv(station_csv_path, index=False)
    problems = find_missing_data(pd.read_csv(station_csv_path), CHARGING_STATION_COLUMNS, station_csv_path)
    assert problems == ["stations.csv: required column 'power' is missing "
                        "(columns found: station_id, node_id, node_y, node_x)"]


def test_preprocesser_stops_before_processing_and_lists_every_gap(tmp_path):
    road_graph_df = create_road_graph_df()
    road_graph_df.loc[0, 'mean_time'] = np.nan
    charging_station_df = create_charging_station_df()
    charging_station_df.loc[1, 'power'] = np.nan

    result = run_preprocesser(tmp_path, road_graph_df, charging_station_df)

    assert result.returncode == 1
    assert '2 problem(s)' in result.stderr
    assert "road.csv line 2: blank 'mean_time'" in result.stderr
    assert "stations.csv line 3: blank 'power'" in result.stderr
    assert 'power=>>> MISSING <<<' in result.stderr
    assert 'Traceback' not in result.stderr
    assert not os.path.exists(str(tmp_path / 'complete_time_array.npy'))


def test_complete_csvs_preprocess_as_before(tmp_path):
    result = run_preprocesser(tmp_path, create_road_graph_df(), create_charging_station_df())

    assert result.returncode == 0, result.stderr
    np.testing.assert_array_equal(np.load(str(tmp_path / 'complete_time_array.npy')), [[0., 30.], [30., 0.]])
    np.testing.assert_array_equal(np.load(str(tmp_path / 'complete_consumption_array.npy')), [[0., 300.], [300., 0.]])
    ids_df = pd.read_csv(str(tmp_path / 'charging_graph_ids.csv'))
    assert ids_df['station_id'].tolist() == ['S_A', 'S_C']
