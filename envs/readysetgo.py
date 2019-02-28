#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 24 13:48:19 2019

@author: molano


Ready-Set-Go task and Contextual Ready-Set-Go task, based on

  Flexible Sensorimotor Computations through Rapid
  Reconfiguration of Cortical Dynamics
  Evan D. Remington, Devika Narain,
  Eghbal A. Hosseini, Mehrdad Jazayeri, Neuron 2018.

  https://www.cell.com/neuron/pdf/S0896-6273(18)30418-5.pdf

"""
from __future__ import division

import numpy as np
from gym import spaces
import tasktools
import ngym


class ReadySetGo(ngym.ngym):
    # Inputs
    inputs = tasktools.to_map('FIXATION', 'READY', 'SET')

    # Actions
    actions = tasktools.to_map('FIXATE', 'GO')

    # Input noise
    sigma = np.sqrt(2*100*0.01)

    # Durations
    fixation = 500
    gain = 1
    ready = 83
    set = 83
    tmax = fixation + 2500

    # Rewards
    R_ABORTED = -1.
    R_CORRECT = +1.
    R_FAIL = 0.
    R_MISS = 0.

    def __init__(self, dt=100):
        super().__init__(dt=dt)
        if dt > 80:
            raise ValueError('dt {:0.2f} too large for this task.'.format(dt))
        self.action_space = spaces.Discrete(2)
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(3,),
                                            dtype=np.float32)

        self.seed()
        self.viewer = None

        self.steps_beyond_done = None

        self.trial = self._new_trial(self.rng, self.dt)
        print('------------------------')
        print('RDM task')
        print('time step: ' + str(self.dt))
        print('------------------------')

    def _new_trial(self, rng, dt):
        # TODO: why are rng and dt inputs?
        # ---------------------------------------------------------------------
        # Epochs
        # ---------------------------------------------------------------------

        measure = rng.choice([500, 580, 660, 760, 840, 920, 1000])

        production = measure * self.gain
        tmax = self.fixation + measure + self.set + 2*production

        durations = {
            'fixation_grace': (0, 100),
            'fixation':  (0, self.fixation),
            'ready': (self.fixation, self.fixation + self.ready),
            'measure': (self.fixation, self.fixation + measure),
            'set': (self.fixation + measure,
                    self.fixation + measure + self.set),
            'production': (self.fixation + measure + self.set,
                           self.fixation + measure + self.set + 2*production),
            'tmax': tmax
            }

        # ---------------------------------------------------------------------
        # Trial
        # ---------------------------------------------------------------------

        return {
            'durations': durations,
            'measure': measure,
            'production': production,
            }

    def step(self, action):
        # ---------------------------------------------------------------------
        # Reward
        # ---------------------------------------------------------------------
        trial = self.trial
        info = {'continue': True}
        reward = 0
        tr_perf = False
        if not self.in_epoch(self.t, 'production'):
            if (action != self.actions['FIXATE'] and
                    not self.in_epoch(self.t, 'fixation_grace')):
                info['continue'] = False
                reward = self.R_ABORTED
        else:
            if action == self.actions['GO']:
                info['continue'] = False  # terminate
                # actual production time
                t_prod = self.t - trial['durations']['measure'][1]
                eps = abs(t_prod - trial['production'])
                eps_threshold = 0.2*trial['production']+25
                if eps > eps_threshold:
                    info['correct'] = False
                    reward = self.R_FAIL
                else:
                    info['correct'] = True
                    reward = (1. - eps/eps_threshold)**1.5
                    reward = min(reward, 0.1)
                    reward *= self.R_CORRECT
                tr_perf = True

                info['t_choice'] = self.t

        # ---------------------------------------------------------------------
        # Inputs
        # ---------------------------------------------------------------------

        obs = np.zeros(len(self.inputs))
        obs[self.inputs['FIXATION']] = 1  # TODO: this is always on now
        if self.in_epoch(self.t, 'ready'):
            obs[self.inputs['READY']] = 1
        if self.in_epoch(self.t, 'set'):
            obs[self.inputs['SET']] = 1

        # ---------------------------------------------------------------------
        # new trial?
        reward, new_trial = tasktools.new_trial(self.t, self.tmax, self.dt,
                                                info['continue'],
                                                self.R_MISS, reward)

        if new_trial:
            self.t = 0
            self.num_tr += 1
            # compute perf
            self.perf, self.num_tr, self.num_tr_perf =\
                tasktools.compute_perf(self.perf, reward, self.num_tr,
                                       self.p_stp, self.num_tr_perf, tr_perf)
            self.trial = self._new_trial(self.rng, self.dt)
        else:
            self.t += self.dt

        done = False  # TODO: revisit
        return obs, reward, done, info

    def terminate(perf):
        p_decision, p_correct = tasktools.correct_2AFC(perf)

        return p_decision >= 0.99 and p_correct >= 0.8