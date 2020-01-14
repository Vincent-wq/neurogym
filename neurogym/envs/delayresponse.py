#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec  3 15:58:10 2019

@author: molano
"""

import numpy as np
from gym import spaces

import neurogym as ngym
from neurogym.ops import tasktools


class DR(ngym.EpochEnv):
    # TODO: Add paper link
    metadata = {
        'paper_link': None,
        'paper_name': None,
        'default_timing': {
            'fixation': ('constant', 500),
            'stimulus': ('truncated_exponential', [330, 80, 1500]),
            'delay': ('choice', [1000, 5000, 10000]),
            'decision': ('constant', 500)},
    }

    def __init__(self, dt=100, timing=None, stimEv=1., **kwargs):
        super().__init__(dt=dt, timing=timing)
        self.choices = [1, 2]
        # cohs specifies the amount of evidence (which is modulated by stimEv)
        self.cohs = np.array([0, 6.4, 12.8, 25.6, 51.2])*stimEv
        # Input noise
        self.sigma = np.sqrt(2*100*0.01)
        self.sigma_dt = self.sigma / np.sqrt(self.dt)

        # Rewards
        self.R_ABORTED = -0.1
        self.R_CORRECT = +1.
        self.R_FAIL = -1.
        self.R_MISS = 0.
        self.abort = False
        self.firstcounts = True
        self.first_flag = False
        # action and observation spaces
        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(3,),
                                            dtype=np.float32)

    def new_trial(self, **kwargs):
        """
        new_trial() is called when a trial ends to generate the next trial.
        The following variables are created:
            durations, which stores the duration of the different periods (in
            the case of rdm: fixation, stimulus and decision periods)
            ground truth: correct response for the trial
            coh: stimulus coherence (evidence) for the trial
            obs: observation
        """
        self.first_flag = False

        # ---------------------------------------------------------------------
        # Trial
        # ---------------------------------------------------------------------
        self.trial = {
            'ground_truth': self.rng.choice(self.choices),
            'coh': self.rng.choice(self.cohs),
            'sigma_dt': self.sigma_dt,
        }
        self.trial.update(kwargs)

        # ---------------------------------------------------------------------
        # Epochs
        # ---------------------------------------------------------------------
        self.add_epoch('fixation', after=0)
        self.add_epoch('stimulus', after='fixation')
        self.add_epoch('delay', after='stimulus')
        self.add_epoch('decision', after='delay', last_epoch=True)

        # define observations
        self.set_ob('fixation', [1, 0, 0])
        stimulus_value = [1] + [(1 - self.trial['coh']/100)/2] * 2
        stimulus_value[self.trial['ground_truth']] = (1 + self.trial['coh']/100)/2
        self.set_ob('stimulus', stimulus_value)
        self.set_ob('delay', [1, 0, 0])
        self.obs[self.stimulus_ind0:self.stimulus_ind1, 1:] += np.random.randn(
            self.stimulus_ind1-self.stimulus_ind0, 2) * self.trial['sigma_dt']

        self.set_groundtruth('decision', self.trial['ground_truth'])

    def _step(self, action):
        """
        _step receives an action and returns:
            a new observation, obs
            reward associated with the action, reward
            a boolean variable indicating whether the experiment has end, done
            a dictionary with extra information:
                ground truth correct response, info['gt']
                boolean indicating the end of the trial, info['new_trial']
        """
        # ---------------------------------------------------------------------
        # Reward and observations
        # ---------------------------------------------------------------------
        new_trial = False
        # rewards
        reward = 0
        # observations
        gt = self.gt_now

        first_trial = np.nan
        if self.in_epoch('fixation') or self.in_epoch('delay'):
            if action != 0:
                new_trial = self.abort
                reward = self.R_ABORTED
        elif self.in_epoch('decision'):
            if action == gt:
                reward = self.R_CORRECT
                new_trial = True
                if ~self.first_flag:
                    first_trial = True
                    self.first_flag = True
            elif action == 3 - gt:  # 3-action is the other act
                reward = self.R_FAIL
                new_trial = self.firstcounts
                if ~self.first_flag:
                    first_trial = False
                    self.first_flag = True

        info = {'new_trial': new_trial,
                'gt': gt,
                'first_trial': first_trial}
        return self.obs_now, reward, False, info


if __name__ == '__main__':
    env = DR()
    tasktools.plot_struct(env)