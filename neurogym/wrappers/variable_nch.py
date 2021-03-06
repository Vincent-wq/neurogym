#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on  Feb  2020

@author: jorgedelpozolerida

"""

import neurogym as ngym
import numpy as np
from neurogym.core import TrialWrapperV2
import warnings


class Variable_nch(TrialWrapperV2):
    metadata = {
        'description': 'Change number of active choices every ' +
        'block_nch trials. Always less or equal than original number.',
        'paper_link': None,
        'paper_name': None
    }

    def __init__(self, env, block_nch=100, blocks_probs=None):
        """
        block_nch: duration of each block containing a specific number
        of active choices
        prob_2: probability of having only two active choices per block
        """
        super().__init__(env)

        assert isinstance(block_nch, int), 'block_nch must be integer'
        assert isinstance(self.unwrapped, ngym.TrialEnv), 'Task has to be TrialEnv'

        self.block_nch = block_nch
        self.max_nch = len(self.unwrapped.choices)  # Max number of choices

        # uniform distr. across choices unless prob(n_ch=2) (prob_2) is specified
        if blocks_probs is not None:
            self.prob = blocks_probs[:self.max_nch-1]
            if np.sum(self.prob) == 0:
                self.prob = [1/(self.max_nch-1)]*(self.max_nch-1)
            else:
                self.prob = self.prob/np.sum(self.prob)
        else:
            self.prob = [1/(self.max_nch-1)]*(self.max_nch-1)
        # Initialize with a random number of active choices (never 1)
        self.nch = self.rng.choice(range(2, self.max_nch + 1), p=self.prob)

    def new_trial(self, **kwargs):

        if 'ground_truth' in kwargs.keys():
            warnings.warn('Variable_nch wrapper ' +
                          'will ignore passed ground truth')

        if self.unwrapped.num_tr % self.block_nch == 0:
            # We change number of active choices every 'block_nch'.
            self.nch = self.rng.choice(range(2, self.max_nch + 1), p=self.prob)

        kwargs.update({'n_ch': self.nch})
        self.env.new_trial(**kwargs)

    def step(self, action):
        obs, reward, done, info = self.env.step(action)
        info['nch'] = self.nch
        return obs, reward, done, info
