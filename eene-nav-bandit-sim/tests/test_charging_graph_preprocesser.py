# Copyright 2023 Volvo Car Corporation
# Licensed under Apache 2.0.

import sys

import pandas as pd
import pytest

import charging_graph_preprocesser
from util.input_validation import (read_csv_with_string_ids, validate_columns, coerce_numeric,
                                   CHARGING_STATION_REQUIRED_COLUMNS)

ROAD_GRAPH_HEADER = 'from_id,from_y,from_x,to_id,to_y,to_x,mean_consumption,mean_time\n'
STATION_HEADER = 'station_id,node_id,node_y,node_x,power\n'


def two_way_road_rows(from_id, to_id):
    return (from_id + ',0.0,0.0,' + to_id + ',0.0,1.0,3600000.0,60.0\n' +
            to_id + ',0.0,1.0,' + from_id + ',0.0,0.0,3600000.0,60.0\n')


def write_csv(path, text):
    path.write_text(text)
    return str(path)


def run_preprocessor(monkeypatch, tmp_path, road_graph_text, station_text, extra_args=()):
    road_graph_path = write_csv(tmp_path / 'road_graph.csv', road_graph_text)
    station_path = write_csv(tmp_path / 'stations.csv', station_text)
    output_dir = tmp_path / 'output'
    output_dir.mkdir()
    monkeypatch.setattr(sys, 'argv', ['charging_graph_preprocesser.py',
                                      '--road-graph-csv-path', road_graph_path,
                                      '--charging-station-csv-path', station_path,
                                      '--output-dir', str(output_dir) + '/'] + list(extra_args))
    charging_graph_preprocesser.main()
    return output_dir


def test_valid_input_is_preprocessed(monkeypatch, tmp_path):
    output_dir = run_preprocessor(monkeypatch, tmp_path,
                                  ROAD_GRAPH_HEADER + two_way_road_rows('A', 'B'),
                                  STATION_HEADER + 'SA,A,0.0,0.0,50000\nSB,B,0.0,1.0,100000\n')
    assert (output_dir / 'complete_time_array.npy').exists()
    assert (output_dir / 'complete_consumption_array.npy').exists()
    assert (output_dir / 'charging_graph_ids.csv').exists()


def test_unknown_argument_is_rejected(monkeypatch, tmp_path):
    with pytest.raises(SystemExit):
        run_preprocessor(monkeypatch, tmp_path,
                         ROAD_GRAPH_HEADER + two_way_road_rows('A', 'B'),
                         STATION_HEADER + 'SA,A,0.0,0.0,50000\n',
                         extra_args=['--not-an-argument', '1'])


def test_missing_column_is_reported():
    df = pd.DataFrame({'station_id': ['S1'], 'node_id': ['A'], 'node_y': [0.0], 'node_x': [0.0]})
    with pytest.raises(ValueError, match='missing required column\\(s\\): power'):
        validate_columns(df, CHARGING_STATION_REQUIRED_COLUMNS, 'Charging station CSV')


def test_missing_road_graph_column_stops_preprocessing(monkeypatch, tmp_path):
    road_graph_text = ('from_id,from_y,from_x,to_id,to_y,to_x,mean_consumption\n'
                       'A,0.0,0.0,B,0.0,1.0,3600000.0\n')
    with pytest.raises(ValueError, match='Road graph CSV .* missing required column\\(s\\): mean_time'):
        run_preprocessor(monkeypatch, tmp_path, road_graph_text, STATION_HEADER + 'SA,A,0.0,0.0,50000\n')


def test_non_numeric_power_is_reported():
    df = pd.DataFrame({'station_id': ['S1', 'S2', 'S3'], 'power': ['50000', 'fast', None]})
    with pytest.raises(ValueError) as error:
        coerce_numeric(df, ['power'], 'Charging station CSV')
    assert "row 1 power='fast'" in str(error.value)
    assert 'row 2 power=<blank>' in str(error.value)
    assert 'row 0' not in str(error.value)


def test_non_numeric_power_stops_preprocessing(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="non-numeric values: row 1 power='fast'"):
        run_preprocessor(monkeypatch, tmp_path,
                         ROAD_GRAPH_HEADER + two_way_road_rows('A', 'B'),
                         STATION_HEADER + 'SA,A,0.0,0.0,50000\nSB,B,0.0,1.0,fast\n')


def test_numeric_columns_become_numbers():
    df = pd.DataFrame({'power': ['50000', '100000']})
    coerce_numeric(df, ['power'])
    assert df['power'].tolist() == [50000.0, 100000.0]


def test_numeric_looking_ids_stay_strings(tmp_path):
    station_path = write_csv(tmp_path / 'stations.csv',
                             ' station_id , node_id ,node_y,node_x,power\n007,0101,0.0,0.0,50000\n')
    df = read_csv_with_string_ids(station_path)
    assert list(df.columns) == CHARGING_STATION_REQUIRED_COLUMNS
    assert df['station_id'].tolist() == ['007']
    assert df['node_id'].tolist() == ['0101']


def test_numeric_looking_ids_survive_preprocessing(monkeypatch, tmp_path):
    output_dir = run_preprocessor(monkeypatch, tmp_path,
                                  ROAD_GRAPH_HEADER + two_way_road_rows('0101', '0102'),
                                  STATION_HEADER + '007,0101,0.0,0.0,50000\n008,0102,0.0,1.0,100000\n')
    ids_df = pd.read_csv(output_dir / 'charging_graph_ids.csv', dtype=str)
    assert ids_df['station_id'].tolist() == ['007', '008']
    assert ids_df['node_id'].tolist() == ['0101', '0102']


def test_station_node_not_in_graph_is_reported(monkeypatch, tmp_path):
    with pytest.raises(ValueError) as error:
        run_preprocessor(monkeypatch, tmp_path,
                         ROAD_GRAPH_HEADER + two_way_road_rows('A', 'B'),
                         STATION_HEADER + 'SA,A,0.0,0.0,50000\nSZ,Z,5.0,5.0,100000\n')
    assert '1 charging station(s) have a node_id that is not in the road graph' in str(error.value)
    assert 'station_id=SZ node_id=Z' in str(error.value)
    assert 'SA' not in str(error.value)


def test_unreachable_station_pairs_are_reported(monkeypatch, tmp_path):
    one_way_road = ROAD_GRAPH_HEADER + 'A,0.0,0.0,B,0.0,1.0,3600000.0,60.0\n'
    with pytest.raises(ValueError) as error:
        run_preprocessor(monkeypatch, tmp_path, one_way_road,
                         STATION_HEADER + 'SA,A,0.0,0.0,50000\nSB,B,0.0,1.0,100000\n')
    assert '1 charging station pair(s) are unreachable' in str(error.value)
    assert 'SB -> SA' in str(error.value)
    assert not (tmp_path / 'output' / 'complete_time_array.npy').exists()
    assert not (tmp_path / 'output' / 'complete_consumption_array.npy').exists()
