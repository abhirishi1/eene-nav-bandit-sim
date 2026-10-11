# Copyright 2023 Volvo Car Corporation
# Licensed under Apache 2.0.

import os

import matplotlib
matplotlib.use('Agg')
import pandas as pd

from sim_runner import save_results


def create_results_df():
    data = []
    for experiment_name in ['Greedy', 'BayesUCB']:
        cumulative_regret = 0.
        for iteration in range(3):
            cumulative_regret += 1.
            data.append({'experiment_name': experiment_name, 'iteration': iteration,
                         'instant_regret': 1., 'cumulative_regret': cumulative_regret})
    return pd.DataFrame(data=data)


def test_save_results_without_trailing_slash(tmp_path):
    output_dir = str(tmp_path / 'new_folder')
    results_csv_path, regret_plot_path = save_results(create_results_df(), output_dir)
    assert results_csv_path == os.path.join(output_dir, 'results.csv')
    assert regret_plot_path == os.path.join(output_dir, 'regret_plot.png')
    assert sorted(os.listdir(output_dir)) == ['regret_plot.png', 'results.csv']
    assert sorted(os.listdir(str(tmp_path))) == ['new_folder']


def test_save_results_with_trailing_slash(tmp_path):
    output_dir = str(tmp_path) + os.sep
    save_results(create_results_df(), output_dir)
    assert sorted(os.listdir(str(tmp_path))) == ['regret_plot.png', 'results.csv']
