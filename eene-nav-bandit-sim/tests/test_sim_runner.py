# Copyright 2023 Volvo Car Corporation
# Licensed under Apache 2.0.

import sys

import numpy as np
import pytest

import sim_runner


class StopAfterLoading(Exception):
    pass


def run_sim_runner(monkeypatch, tmp_path, station_text, extra_args=(),
                   ids_text=',station_id,node_id,matrix_id\n0,S1,A,0\n'):
    station_path = tmp_path / 'stations.csv'
    station_path.write_text(station_text)
    ids_path = tmp_path / 'charging_graph_ids.csv'
    ids_path.write_text(ids_text)
    np.save(tmp_path / 'consumption.npy', np.zeros((1, 1)))
    np.save(tmp_path / 'time.npy', np.zeros((1, 1)))
    captured = {}

    def fake_create_experiments(**kwargs):
        captured.update(kwargs)
        raise StopAfterLoading()

    monkeypatch.setattr(sim_runner, 'create_experiments', fake_create_experiments)
    monkeypatch.setattr(sys, 'argv', ['sim_runner.py',
                                      '--charging-station-csv-path', str(station_path),
                                      '--charging-graph-ids-csv-path', str(ids_path),
                                      '--charging-consumption-npy-path', str(tmp_path / 'consumption.npy'),
                                      '--charging-time-npy-path', str(tmp_path / 'time.npy'),
                                      '--start-node-id', 'A',
                                      '--end-node-id', 'A'] + list(extra_args))
    with pytest.raises(StopAfterLoading):
        sim_runner.main()
    return captured


def test_station_csv_ids_stay_strings(monkeypatch, tmp_path):
    captured = run_sim_runner(monkeypatch, tmp_path,
                              ' station_id ,node_id,node_y,node_x,power\n007,0101,0.0,0.0,50000\n')
    station_df = captured['charging_station_df']
    assert station_df['station_id'].tolist() == ['007']
    assert station_df['node_id'].tolist() == ['0101']


def test_charging_graph_ids_stay_strings(monkeypatch, tmp_path):
    captured = run_sim_runner(monkeypatch, tmp_path, 'station_id,node_id,node_y,node_x,power\n1,101,0.0,0.0,50000\n',
                              ids_text=',station_id,node_id,matrix_id\n0,1,101,0\n')
    ids_df = captured['charging_graph_ids_df']
    assert ids_df['station_id'].tolist() == ['1']
    assert ids_df['node_id'].tolist() == ['101']


def test_station_csv_missing_column_is_reported(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match='missing required column\\(s\\): power'):
        run_sim_runner(monkeypatch, tmp_path, 'station_id,node_id,node_y,node_x\nS1,A,0.0,0.0\n')


def test_unknown_argument_is_rejected(monkeypatch, tmp_path):
    with pytest.raises(SystemExit):
        run_sim_runner(monkeypatch, tmp_path, 'station_id,node_id,node_y,node_x,power\nS1,A,0.0,0.0,50000\n',
                       extra_args=['--not-an-argument', '1'])
