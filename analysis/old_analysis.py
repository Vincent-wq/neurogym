#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 25 09:55:06 2019

@author: linux
"""
import sys
import numpy as np
from pathlib import Path
from scipy.optimize import curve_fit
import matplotlib
home = str(Path.home())
sys.path.append(home + '/neurogym')
from neurogym.analysis import analysis as an
from neurogym.ops import utils as ut
matplotlib.use('Agg')  # Qt5Agg
import matplotlib.pyplot as plt
display_mode = False
DPI = 400


def plot_psychometric_curves(evidence, performance, action,
                             blk_dur=200,
                             plt_av=True, figs=True):
    """
    plots psychometric curves
    - evidence for right VS prob. of choosing right
    - evidence for repeating side VS prob. of repeating
    - same as above but conditionated on hits and fails
    The function assumes that a figure has been created
    before it is called.
    """
    # build the mat that indicates the current block
    blocks = an.build_block_mat(evidence.shape, blk_dur)

    # repeating probs. values
    probs_vals = np.unique(blocks)
    assert len(probs_vals) <= 2
    colors = [[1, 0, 0], [0, 0, 1]]
    if figs:
        rows = 2
        cols = 2
    else:
        rows = 0
        cols = 0

    data = {}
    for ind_sp in range(4):
        if figs:
            plt.subplot(rows, cols, ind_sp+1)
            # remove all previous plots
            ut.rm_lines()
    for ind_blk in range(len(probs_vals)):
        # filter data
        inds = (blocks == probs_vals[ind_blk])
        evidence_block = evidence[inds]
        performance_block = performance[inds]
        action_block = action[inds]
        data = get_psyCho_curves_data(performance_block,
                                      evidence_block, action_block,
                                      probs_vals[ind_blk],
                                      rows, cols, figs, colors[ind_blk],
                                      plt_av, data)
    return data


def get_psyCho_curves_data(performance, evidence, action, prob,
                           rows, cols, figs, color, plt_av, data):
    """
    plot psychometric curves for:
    right evidence VS prob. choosing right
    repeating evidence VS prob. repeating
    repeating evidence VS prob. repeating (conditionated on previous correct)
    repeating evidence VS prob. repeating (conditionated on previous wrong)
    """

    # 1. RIGHT EVIDENCE VS PROB. CHOOSING RIGHT
    # get the action
    right_choice = action == 1

    # associate invalid trials (network fixates) with incorrect choice
    right_choice[action == 0] = evidence[action == 0] > 0
    # np.random.choice([0, 1], size=(np.sum(action.flatten() == 2),))

    # convert the choice to float and flatten it
    right_choice = [float(x) for x in right_choice]
    right_choice = np.asarray(right_choice)
    # fit and plot
    if figs:
        plt.subplot(rows, cols, 1)
        plt.xlabel('right evidence')
        plt.ylabel('prob. right')
    popt, pcov, av_data =\
        fit_and_plot(evidence, right_choice,
                     plt_av, color=color, figs=figs)

    data['popt_rightProb_' + str(prob)] = popt
    data['pcov_rightProb_' + str(prob)] = pcov
    data['av_rightProb_' + str(prob)] = av_data

    # 2. REPEATING EVIDENCE VS PROB. REPEATING
    # I add a random choice to the beginning of the choice matrix
    # and differentiate to see when the network is repeating sides
    repeat = np.concatenate(
        (np.array(np.random.choice([0, 1])).reshape(1,),
         right_choice))
    repeat = np.diff(repeat) == 0
    # right_choice_repeating is just the original right_choice mat
    # but shifted one element to the left.
    right_choice_repeating = np.concatenate(
        (np.array(np.random.choice([0, 1])).reshape(1, ),
         right_choice[:-1]))
    # the rep. evidence is the original evidence with a negative sign
    # if the repeating side is the left one
    rep_ev_block = evidence *\
        (-1)**(right_choice_repeating == 0)
    # fitting
    if figs:
        label_aux = 'p. rep.: ' + str(prob)
        plt.subplot(rows, cols, 2)
        #         plt.xlabel('repetition evidence')
        #         plt.ylabel('prob. repetition')
    else:
        label_aux = ''
    popt, pcov, av_data =\
        fit_and_plot(rep_ev_block, repeat,
                     plt_av, color=color,
                     label=label_aux, figs=figs)

    data['popt_repProb_'+str(prob)] = popt
    data['pcov_repProb_'+str(prob)] = pcov
    data['av_repProb_'+str(prob)] = av_data

    # plot psycho-curves conditionated on previous performance
    # get previous trial performance
    prev_perf = np.concatenate(
        (np.array(np.random.choice([0, 1])).reshape(1,),
         performance[:-1]))
    # 3. REPEATING EVIDENCE VS PROB. REPEATING
    # (conditionated on previous correct)
    # fitting
    mask = prev_perf == 1
    if figs:
        plt.subplot(rows, cols, 3)
        plt.xlabel('repetition evidence')
        plt.ylabel('prob. repetition')
        #         plt.title('Prev. hit')
    popt, pcov, av_data =\
        fit_and_plot(rep_ev_block[mask], repeat[mask],
                     plt_av, color=color,
                     label=label_aux, figs=figs)
    data['popt_repProb_hits_'+str(prob)] = popt
    data['pcov_repProb_hits_'+str(prob)] = pcov
    data['av_repProb_hits_'+str(prob)] = av_data
    # print('bias: ' + str(round(popt[1], 3)))
    # 4. REPEATING EVIDENCE VS PROB. REPEATING
    # (conditionated on previous wrong)
    # fitting
    mask = prev_perf == 0
    if figs:
        plt.subplot(rows, cols, 4)
        plt.xlabel('repetition evidence')
        #         plt.ylabel('prob. repetition')
        #         plt.title('Prev. fail')
    popt, pcov, av_data =\
        fit_and_plot(rep_ev_block[mask], repeat[mask],
                     plt_av, color=color,
                     label=label_aux, figs=figs)

    data['popt_repProb_fails_'+str(prob)] = popt
    data['pcov_repProb_fails_'+str(prob)] = pcov
    data['av_repProb_fails_'+str(prob)] = av_data

    return data


def fit_and_plot(evidence, choice, plt_av=False,
                 color=(0, 0, 0), label='', figs=False):
    """
    uses curve_fit to fit the evidence/choice provided to a probit function
    that takes into account the lapse rates
    it also plots the corresponding fit and, if plt_av=True, plots the
    average choice values for different windows of the evidence
    """
    if evidence.shape[0] > 10 and len(np.unique(choice)) == 2:
        # fit
        popt, pcov = curve_fit(an.probit_lapse_rates,
                               evidence, choice, maxfev=10000)
    # plot averages
        if plt_av:
            av_data = plot_psychoCurves_averages(evidence, choice,
                                                 color=color, figs=figs)
        else:
            av_data = {}
        # plot obtained probit function
        if figs:
            x = np.linspace(np.min(evidence),
                            np.max(evidence), 50)
            # get the y values for the fitting
            y = an.probit_lapse_rates(x, popt[0], popt[1], popt[2], popt[3])
            if label == '':
                plt.plot(x, y, color=color, lw=0.5)
            else:
                plt.plot(x, y, color=color,  label=label
                         + ' b: ' + str(round(popt[1], 3)), lw=0.5)
                plt.legend(loc="lower right")
            an.plot_dashed_lines(-np.max(evidence), np.max(evidence))
    else:
        av_data = {}
        popt = [0, 0, 0, 0]
        pcov = 0
        print('not enough data!')
    return popt, pcov, av_data


def plot_psychoCurves_averages(x_values, y_values,
                               color=(0, 0, 0), figs=False):
    """
    plots average values of y_values for 10 (num_values) different windows
    in x_values
    """
    num_values = 10
    conf = 0.95
    x, step = np.linspace(np.min(x_values), np.max(x_values),
                          num_values, retstep=True)
    curve_mean = []
    curve_std = []
    # compute mean for each window
    for ind_x in range(num_values-1):
        inds = (x_values >= x[ind_x])*(x_values < x[ind_x+1])
        mean = np.mean(y_values[inds])
        curve_mean.append(mean)
        curve_std.append(conf*np.sqrt(mean*(1-mean)/np.sum(inds)))

    if figs:
        # make color weaker
        # np.max(np.concatenate((color, [1, 1, 1]), axis=0), axis=0)
        color_w = np.array(color) + 0.5
        color_w[color_w > 1] = 1
        # plot
        plt.errorbar(x[:-1] + step / 2, curve_mean, curve_std,
                     color=color_w, marker='+', linestyle='')

    # put values in a dictionary
    av_data = {'mean': curve_mean, 'std': curve_std, 'x': x[:-1]+step/2}
    return av_data


def behavior_analysis(file='/home/linux/PassReward0_data.npz', folder=''):
    """
    compute performance and bias across training
    """
    choice, correct_side, performance, evidence = an.load_behavioral_data(file)
    # plot performance
    num_tr = 5000000
    start_point = 0
    f = ut.get_fig(display_mode)
    an.plot_learning(performance[start_point:start_point+num_tr],
                     evidence[start_point:start_point+num_tr],
                     correct_side[start_point:start_point+num_tr], w_conv=1000)
    if folder != '':
        f.savefig(folder + 'performance.png',
                  dpi=DPI, bbox_inches='tight')
        plt.close(f)
    # plot performance last training stage
    f = ut.get_fig(display_mode)
    num_tr = 20000
    start_point = performance.shape[0]-num_tr
    an.plot_learning(performance[start_point:start_point+num_tr],
                     evidence[start_point:start_point+num_tr],
                     correct_side[start_point:start_point+num_tr])
    if folder != '':
        f.savefig(folder + 'late_performance.png',
                  dpi=DPI, bbox_inches='tight')
        plt.close(f)
    # plot trials
    correct_side_plt = correct_side[:400]
    f = ut.get_fig(display_mode)
    plt.imshow(correct_side_plt.reshape((1, 400)), aspect='auto')
    if folder != '':
        f.savefig(folder + 'trial_sequence.png',
                  dpi=DPI, bbox_inches='tight')
    an.bias_across_training(choice, evidence, performance, folder)


def test_bias():
    """
    this function just computes the bias in the old and new ways and
    compares the results
    """
    file = '/home/linux/PassReward0_data.npz'
    choice, correct_side, performance, evidence, _ =\
        an.load_behavioral_data(file)
    # plot psychometric curves
    ut.get_fig(display_mode)
    num_tr = 2000000
    start_point = performance.shape[1]-num_tr
    ev = evidence[:, start_point:start_point+num_tr]
    perf = performance[:, start_point:start_point+num_tr]
    ch = choice[:, start_point:start_point+num_tr]
    plot_psychometric_curves(ev, perf, ch, blk_dur=200,
                             plt_av=True, figs=True)
    # REPLICATE RESULTS
    # build the mat that indicates the current block
    blocks = an.build_block_mat(ev.shape, block_dur=200)
    rand_perf = np.random.choice([0, 1], size=(1,))
    prev_perf = np.concatenate((rand_perf, perf[0, :-1]))
    labels = ['error', 'correct']
    for ind_perf in reversed(range(2)):
        for ind_bl in range(2):
            mask = np.logical_and(blocks == ind_bl, prev_perf == ind_perf)
            assert np.sum(mask) > 0
            popt, pcov = an.bias_calculation(ch, ev, mask)
            print('bias block ' + str(ind_bl) + ' after ' +
                  labels[ind_perf] + ':')
            print(popt[1])


def exp_analysis(folder, file, file_bhvr, trials_fig=True,
                 neural_analysis_flag=True, behavior_analysis_flag=True,
                 n_envs=10, env=0, num_steps=20, obs_size=5,
                 num_units=64, p_lbl=['1', '2'], window=(-5, 20)):
    """
    performs neural and behabioral analyses on the exp. contained in
    folder/file (/file_bhvr)
    """
    if neural_analysis_flag:
        an.mean_neural_activity(file=file, fig=trials_fig, n_envs=n_envs,
                                env=env,
                                num_steps=num_steps, obs_size=obs_size,
                                num_units=num_units, part=[[0, 32], [32, 64]],
                                p_lbl=p_lbl, folder=folder)
        trials_fig = False
        an.neural_analysis(file=file, fig=trials_fig, n_envs=n_envs, env=env,
                           num_steps=num_steps, obs_size=obs_size,
                           num_units=num_units, window=window,
                           part=[[0, 32], [32, 64]], p_lbl=p_lbl,
                           folder=folder)
        an.transition_analysis(file=file, fig=trials_fig, n_envs=n_envs,
                               env=env,
                               num_steps=num_steps, obs_size=obs_size,
                               num_units=num_units, window=window,
                               part=[[0, 32], [32, 64]],
                               p_lbl=p_lbl,
                               folder=folder)
        an.bias_analysis(file=file, fig=trials_fig, n_envs=n_envs, env=env,
                         num_steps=num_steps, obs_size=obs_size,
                         num_units=num_units, window=window, folder=folder)
    if behavior_analysis_flag:
        an.behavior_analysis(file=file_bhvr, folder=folder)
        # bias_cond_on_history(file=file_bhvr, folder=folder)
        an.bias_after_altRep_seqs(file=file_bhvr, folder=folder)
        an.bias_after_transEv_change(file=file_bhvr, folder=folder)


def bias_cond_on_history(file='/home/linux/PassReward0_data.npz', folder=''):
    """
    computes bias conditioned on the number of repetitions during the
    last trials. This function has become a bit obsolete because the function
    bias_after_altRep_seqs does something similar but closer to the analysis
    they did in the paper
    """
    choice, correct_side, performance, evidence, _ =\
        an.load_behavioral_data(file)
    # BIAS CONDITIONED ON TRANSITION HISTORY (NUMBER OF REPETITIONS)
    num_tr = 2000000
    start_point = performance.shape[0]-num_tr
    ev = evidence[start_point:start_point+num_tr]
    perf = performance[start_point:start_point+num_tr]
    ch = choice[start_point:start_point+num_tr]
    side = correct_side[start_point:start_point+num_tr]
    conv_window = 8
    margin = 2
    # get number of repetitions during the last conv_window trials
    # (not including the current trial)
    transitions = an.get_transition_mat(side, conv_window=conv_window)
    values = np.unique(transitions)
    mat_biases = np.empty((2, conv_window))
    labels = ['error', 'correct']
    f = ut.get_fig(display_mode)
    for ind_perf in reversed(range(2)):
        plt.subplot(1, 2, int(not(ind_perf))+1)
        plt.title('after ' + labels[ind_perf])
        for ind_tr in range(margin, values.shape[0]-margin):
            aux_color = (ind_tr-margin)/(values.shape[0]-2*margin-1)
            color = np.array((1-aux_color, 0, aux_color))
            # mask finds all times in which the current trial is correct/error
            # and the trial history (num. of repetitions) is values[ind_tr]
            # we then need to shift these times to get the bias in the trial
            # following them
            mask = np.logical_and(transitions == values[ind_tr],
                                  perf == ind_perf)
            mask = np.concatenate((np.array([False]), mask[:-1]))
            assert np.sum(mask) > 2000
            popt, pcov = an.bias_calculation(ch, ev, mask)
            print('bias ' + str(values[ind_tr]) + ' repeatitions after ' +
                  labels[ind_perf] + ':')
            print(popt[1])
            mat_biases[ind_perf, ind_tr] = popt[1]
            x = np.linspace(np.min(evidence),
                            np.max(evidence), 50)
            # get the y values for the fitting
            y = an.probit_lapse_rates(x, popt[0], popt[1], popt[2], popt[3])
            plt.plot(x, y, color=color,  label=str(values[ind_tr]) +
                     ' b: ' + str(round(popt[1], 3)), lw=0.5)
        plt.xlim([-1.5, 1.5])
        plt.legend(loc="lower right")
        an.plot_dashed_lines(-np.max(evidence), np.max(evidence))
    if folder != '':
        f.savefig(folder + 'bias_cond_on_trHist.png',
                  dpi=DPI, bbox_inches='tight')
        plt.close(f)


def no_stim_analysis(file='/home/linux/PassAction.npz', save_path='',
                     fig=True):
    """
    This is the function that is called during training. It computes
    performance and the probability of repeating when the stimulus
    evidence is small (or 0) conditioned on the number of repetitions during
    the last trials. This is for different periods across training.
    """
    choice, correct_side, performance, evidence, _ =\
        an.load_behavioral_data(file)
    mask_ev = np.logical_and(evidence >= np.percentile(evidence, 40),
                             evidence <= np.percentile(evidence, 60))
    if save_path != '':
        RNN_perf = np.mean(performance[2000:].flatten())
        print('-----------------------------------------------',
              file=open(save_path + 'results', 'a'))
        print('number of trials: ' + str(choice.shape[0]),
              file=open(save_path + 'results', 'a'))
        print('net perf: ' + str(round(RNN_perf, 3)),
              file=open(save_path + 'results', 'a'))

    # compute bias across training
    labels = ['error', 'correct']
    per = 100000
    conv_window = 4
    margin = 0
    num_stps = int(choice.shape[0] / per)
    mat_biases = np.empty((num_stps, conv_window-2*margin+1, 2, 2))
    for ind_stp in range(num_stps):
        start = per*ind_stp
        end = per*(ind_stp+1)
        perf = performance[start:end]
        m_ev = mask_ev[start:end]
        # correct side transition history
        cs = correct_side[start:end]
        transitions = an.get_transition_mat(cs, conv_window=conv_window)
        values = np.unique(transitions)
        max_tr = values.shape[0]-margin
        # choice repeating
        ch = choice[start:end]
        repeat_choice = an.get_repetitions(ch)
        for ind_perf in reversed(range(2)):
            for ind_tr in range(margin, max_tr):
                # mask finds all times in which the current trial is
                # correct/error and the trial history (num. of repetitions)
                # is values[ind_tr] we then need to shift these times to get
                # the bias in the trial following them
                mask = np.logical_and(transitions == values[ind_tr],
                                      perf == ind_perf)
                mask = np.concatenate((np.array([False]), mask[:-1]))
                mask = np.logical_and(m_ev, mask)
                rp_mask = repeat_choice[mask]
                mat_biases[ind_stp, ind_tr-margin, ind_perf, 0] =\
                    np.mean(rp_mask)
                mat_biases[ind_stp, ind_tr-margin, ind_perf, 1] =\
                    np.std(rp_mask)/np.sqrt(rp_mask.shape[0])
                if ind_stp == num_stps-1 and (ind_tr == margin or
                                              ind_tr == max_tr-1):
                    if save_path != '':
                        print('bias ' + str(values[ind_tr]) +
                              ' repeatitions after ' +
                              labels[ind_perf] + ':',
                              file=open(save_path + 'results', 'a'))
                        print(np.mean(rp_mask),
                              file=open(save_path + 'results', 'a'))
                    else:
                        print('bias ' + str(values[ind_tr]) +
                              ' repeatitions after ' + labels[ind_perf] + ':')
                        print(np.mean(rp_mask))

    if fig:
        f = ut.get_fig(display_mode)
        for ind_perf in range(2):
            plt.subplot(2, 1, int(not(ind_perf))+1)
            plt.title('after ' + labels[ind_perf])
            plt.ylabel('prob. rep. previous choice')
            for ind_tr in range(margin, values.shape[0]-margin):
                aux_color = (ind_tr-margin)/(values.shape[0]-2*margin-1)
                color = np.array((1-aux_color, 0, aux_color))
                mean_ = mat_biases[:, ind_tr-margin, ind_perf, 0]
                std_ = mat_biases[:, ind_tr-margin, ind_perf, 1]
                plt.errorbar(np.arange(mean_.shape[0])*per,
                             mean_, std_, color=color, label='trans. ev. ' +
                             str(values[ind_tr]))
                if ind_perf == 0:
                    plt.xlabel('trials')
                    plt.subplot(2, 1, 1)
                    aux_color = (ind_tr-margin)/(values.shape[0]-2*margin-1)
                    color = np.array((1-aux_color, 0, aux_color)) +\
                        (1-ind_perf)*0.8
                    color[np.where(color > 1)] = 1
                    mean_ = mat_biases[:, ind_tr-margin, ind_perf, 0]
                    std_ = mat_biases[:, ind_tr-margin, ind_perf, 1]
                    plt.errorbar(np.arange(mean_.shape[0])*per,
                                 mean_, std_, color=color)
                    plt.subplot(2, 1, 2)
            values_lines = [0, .25, .5, .75, 1]
            for ind_l in range(len(values_lines)):
                an.plot_lines(mean_.shape[0]*per, values_lines[ind_l])
        plt.legend(loc='lower left')
        if save_path != '':
            f.savefig(save_path + 'bias_evolution.png',
                      dpi=DPI, bbox_inches='tight')
            plt.close(f)