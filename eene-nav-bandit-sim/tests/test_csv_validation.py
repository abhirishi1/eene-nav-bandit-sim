# Copyright 2023 Volvo Car Corporation
# Licensed under Apache 2.0.

import pandas as pd

from util.csv_validation import validate_road_graph_df
from util.csv_validation import validate_charging_station_df
from util.csv_validation import validate_trip_end_points
from util.csv_validation import format_validation_errors
from util.csv_validation import MAX_REPORTED_ERRORS
from tests.utils_for_tests import create_charging_station_df


def create_road_graph_df():
    data = []
    for from_id, to_id in [("1", "2"), ("2", "3"), ("3", "4")]:
        for a, b in [(from_id, to_id), (to_id, from_id)]:
            data.append({"from_id": a, "from_y": 0.0, "from_x": 0.0, "to_id": b, "to_y": 0.0, "to_x": 1.0,
                         "mean_consumption": 36000000.0, "mean_time": 3600.0})
    return pd.DataFrame(data=data)


def test_valid_inputs_have_no_errors():
    road_graph_df = create_road_graph_df()
    charging_station_df = create_charging_station_df()
    assert validate_road_graph_df(road_graph_df) == []
    assert validate_charging_station_df(charging_station_df, road_graph_df=road_graph_df) == []
    assert validate_trip_end_points(charging_station_df, "1", "3") == []


def test_validation_does_not_modify_inputs():
    road_graph_df = create_road_graph_df()
    road_graph_df.loc[1, 'mean_time'] = None
    original = road_graph_df.copy()
    validate_road_graph_df(road_graph_df)
    pd.testing.assert_frame_equal(road_graph_df, original)


def test_missing_road_graph_column():
    road_graph_df = create_road_graph_df().drop(columns=['mean_time'])
    assert validate_road_graph_df(road_graph_df, 'road.csv') == [
        'road.csv: missing required column(s): mean_time']


def test_blank_road_graph_values():
    road_graph_df = create_road_graph_df()
    road_graph_df.loc[1, 'mean_time'] = None
    road_graph_df.loc[2, 'mean_consumption'] = None
    road_graph_df.loc[3, 'to_id'] = None
    assert validate_road_graph_df(road_graph_df, 'road.csv') == [
        'road.csv line 5: to_id is blank',
        'road.csv line 4: mean_consumption is blank',
        'road.csv line 3: mean_time is blank']


def test_invalid_mean_time():
    road_graph_df = create_road_graph_df()
    road_graph_df['mean_time'] = road_graph_df['mean_time'].astype(object)
    road_graph_df.loc[0, 'mean_time'] = 'abc'
    road_graph_df.loc[1, 'mean_time'] = 0.0
    road_graph_df.loc[2, 'mean_time'] = -5.0
    assert validate_road_graph_df(road_graph_df, 'road.csv') == [
        "road.csv line 2: mean_time 'abc' is not a valid number",
        'road.csv line 3: mean_time must be greater than 0 (found 0.0)',
        'road.csv line 4: mean_time must be greater than 0 (found -5.0)']


def test_zero_and_negative_mean_consumption_are_allowed():
    road_graph_df = create_road_graph_df()
    road_graph_df.loc[0, 'mean_consumption'] = 0.0
    road_graph_df.loc[1, 'mean_consumption'] = -1000.0
    assert validate_road_graph_df(road_graph_df) == []


def test_missing_charging_station_column():
    charging_station_df = create_charging_station_df().drop(columns=['power'])
    assert validate_charging_station_df(charging_station_df, 'stations.csv') == [
        'stations.csv: missing required column(s): power']


def test_invalid_charging_station_power():
    charging_station_df = create_charging_station_df()
    charging_station_df.loc[0, 'power'] = None
    charging_station_df.loc[1, 'power'] = 0.0
    assert validate_charging_station_df(charging_station_df, 'stations.csv') == [
        'stations.csv line 2: power is blank',
        'stations.csv line 3: power must be greater than 0 (found 0.0)']


def test_duplicate_station_id():
    charging_station_df = create_charging_station_df()
    charging_station_df.loc[2, 'station_id'] = '1'
    assert validate_charging_station_df(charging_station_df, 'stations.csv') == [
        "stations.csv line 4: station_id '1' is used more than once"]


def test_station_node_not_in_road_graph():
    charging_station_df = create_charging_station_df()
    charging_station_df.loc[3, 'node_id'] = '99'
    assert validate_charging_station_df(charging_station_df, 'stations.csv',
                                        road_graph_df=create_road_graph_df()) == [
        "stations.csv line 5: node_id '99' does not appear in the road graph"]


def test_invalid_trip_end_points():
    charging_station_df = create_charging_station_df()
    assert validate_trip_end_points(charging_station_df, "99", None, 'stations.csv') == [
        "--start-node-id '99' is not the node_id of any station in stations.csv",
        '--end-node-id is required']


def test_format_validation_errors_truncates_long_lists():
    errors = ['problem {}'.format(i) for i in range(MAX_REPORTED_ERRORS + 5)]
    message = format_validation_errors(errors)
    assert message.splitlines()[0] == 'Input data validation failed with {} problem(s):'.format(len(errors))
    assert '  - problem 0' in message
    assert '  - problem {}'.format(MAX_REPORTED_ERRORS) not in message
    assert message.splitlines()[-1] == '  ... and 5 more'
