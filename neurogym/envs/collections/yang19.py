"""An example collection of tasks."""

import numpy as np
import gym
from gym import spaces

import neurogym as ngym
from neurogym.wrappers.block import ScheduleEnvs
from neurogym.utils import scheduler
from neurogym.core import TrialWrapperV2


def _get_dist(original_dist):
    '''Get the distance in periodic boundary conditions'''
    return np.minimum(abs(original_dist), 2 * np.pi - abs(original_dist))


def _gaussianbump(loc, theta, strength):
    dist = _get_dist(loc - theta)  # periodic boundary
    dist /= np.pi / 8
    return 0.8 * np.exp(-dist ** 2 / 2) * strength


def _cosinebump(loc, theta, strength):
    return np.cos(theta - loc) * strength / 2 + 0.5


class _MultiModalityStimulus(TrialWrapperV2):
    """Move observation to specific modality."""
    def __init__(self, env, modality=0, n_modality=1):
        super().__init__(env)
        self.modality = modality
        if 'stimulus' not in self.task.ob_dict:
            raise KeyError('ob_dict does not have key stimulus')
        ind_stimulus = np.array(self.task.ob_dict['stimulus'])
        len_stimulus = len(ind_stimulus)
        ob_space = self.task.observation_space
        ob_shape = ob_space.shape[0] + (n_modality - 1) * len_stimulus
        self.observation_space = self.task.observation_space = gym.spaces.Box(
            -np.inf, np.inf, shape=(ob_shape,), dtype=ob_space.dtype)
        # Shift stimulus
        self.task.ob_dict['stimulus'] = ind_stimulus + len_stimulus * modality

    def new_trial(self, **kwargs):
        return self.env.new_trial(**kwargs)


class _Reach(ngym.PeriodEnv):
    """Anti-response task.

    The agent has to move in the direction opposite to the one indicated
    by the observation.
    """
    metadata = {
        'paper_link': 'https://www.nature.com/articles/nrn1345',
        'paper_name': """Look away: the anti-saccade task and
        the voluntary control of eye movement""",
        'tags': ['perceptual', 'steps action space']
    }

    def __init__(self, dt=100, anti=True, rewards=None, timing=None,
                 dim_ring=16, reaction=False):
        super().__init__(dt=dt)

        self.anti = anti
        self.reaction = reaction

        # Rewards
        self.rewards = {'abort': -0.1, 'correct': +1., 'fail': 0.}
        if rewards:
            self.rewards.update(rewards)

        self.timing = {
            'fixation': ('constant', 500),
            'stimulus': ('constant', 500),
            'delay': ('constant', 0),
            'decision': ('constant', 500)}
        if timing:
            self.timing.update(timing)

        self.abort = False

        # action and observation spaces
        self.dim_ring = dim_ring
        self.theta = np.arange(0, 2 * np.pi, 2 * np.pi / dim_ring)
        self.choices = np.arange(dim_ring)

        self.observation_space = spaces.Box(
            -np.inf, np.inf, shape=(1+dim_ring,), dtype=np.float32)
        self.ob_dict = {'fixation': 0, 'stimulus': range(1, dim_ring + 1)}

        self.action_space = spaces.Discrete(1+dim_ring)
        self.act_dict = {'fixation': 0, 'choice': range(1, dim_ring + 1)}

    def new_trial(self, **kwargs):
        # Trial info
        self.trial = {
            'ground_truth': self.rng.choice(self.choices),
            'anti': self.anti,
        }
        self.trial.update(kwargs)

        ground_truth = self.trial['ground_truth']
        if self.trial['anti']:
            stim_theta = np.mod(self.theta[ground_truth] + np.pi, 2*np.pi)
        else:
            stim_theta = self.theta[ground_truth]
        stim = _gaussianbump(stim_theta, self.theta, 1)

        if not self.reaction:
            periods = ['fixation', 'stimulus', 'delay', 'decision']
            self.add_period(periods, after=0, last_period=True)

            self.add_ob(1, period=['fixation', 'stimulus', 'delay'], where='fixation')
            self.add_ob(stim, 'stimulus', where='stimulus')
        else:
            periods = ['fixation', 'decision']
            self.add_period(periods, after=0, last_period=True)

            self.add_ob(1, period='fixation', where='fixation')
            self.add_ob(stim, 'decision', where='stimulus')

        self.set_groundtruth(self.act_dict['choice'][ground_truth], 'decision')

    def _step(self, action):
        new_trial = False
        # rewards
        reward = 0
        gt = self.gt_now
        # observations
        if self.in_period('fixation'):
            if action != 0:  # action = 0 means fixating
                new_trial = self.abort
                reward += self.rewards['abort']
        elif self.in_period('decision'):
            if action != 0:
                new_trial = True
                if action == gt:
                    reward += self.rewards['correct']
                    self.performance = 1
                else:
                    reward += self.rewards['fail']

        return self.ob_now, reward, False, {'new_trial': new_trial, 'gt': gt}


class _DMFamily(ngym.PeriodEnv):
    """Delay comparison.

    Two-alternative forced choice task in which the subject
    has to compare two stimuli separated by a delay to decide
    which one has a higher frequency.
    """
    def __init__(self, dt=100, rewards=None, timing=None, sigma=1.0, cohs=None,
                 dim_ring=16, w_mod=(1, 1), stim_mod=(True, True),
                 delaycomparison=True):
        super().__init__(dt=dt)

        # trial conditions
        if cohs is None:
            self.cohs = np.array([0.08, 0.16, 0.32])
        else:
            self.cohs = cohs
        self.w_mod1, self.w_mod2 = w_mod
        self.stim_mod1, self.stim_mod2 = stim_mod
        self.delaycomparison = delaycomparison

        self.sigma = sigma / np.sqrt(self.dt)  # Input noise

        # Rewards
        self.rewards = {'abort': -0.1, 'correct': +1., 'fail': 0.}
        if rewards:
            self.rewards.update(rewards)

        if self.delaycomparison:
            self.timing = {
                'fixation': ('uniform', (200, 500)),
                'stim1': ('constant', 500),
                'delay': ('constant', 1000),
                'stim2': ('constant', 500),
                'decision': ('constant', 200)}
        else:
            self.timing = {
                'fixation': ('uniform', (200, 500)),
                'stimulus': ('constant', 500),
                'decision': ('constant', 200)}
        if timing:
            self.timing.update(timing)

        self.abort = False

        # action and observation space
        self.theta = np.linspace(0, 2*np.pi, dim_ring+1)[:-1]
        self.choices = np.arange(dim_ring)

        if dim_ring < 2:
            raise ValueError('dim ring can not be smaller than 2')
        self.observation_space = spaces.Box(
            -np.inf, np.inf, shape=(1 + 2 * dim_ring,), dtype=np.float32)
        self.ob_dict = {'fixation': 0,
                        'stimulus_mod1': range(1, dim_ring + 1),
                        'stimulus_mod2': range(dim_ring + 1, 2 * dim_ring + 1)}
        self.action_space = spaces.Discrete(1+dim_ring)
        self.act_dict = {'fixation': 0, 'choice': range(1, dim_ring+1)}

    def _add_singlemod(self, mod=1):
        """Add stimulus to modality."""
        mod = '_mod' + str(mod)

        if self.delaycomparison:
            period1, period2 = 'stim1', 'stim2'
            coh1, coh2 = self.rng.choice(self.cohs, 2, replace=False)
            self.trial['coh1' + mod] = coh1
            self.trial['coh2' + mod] = coh2
        else:
            period1, period2 = 'stimulus', 'stimulus'
            coh = self.rng.choice(self.cohs) * self.rng.choice([-1, +1])
            self.trial['coh1' + mod] = coh1 = 0.5 + coh / 2
            self.trial['coh2' + mod] = coh2 = 0.5 - coh / 2

        # stim = cosinebump(self.trial['theta1'], self.theta, coh1)
        stim = _gaussianbump(self.trial['theta1'], self.theta, coh1)
        self.add_ob(stim, period1, where='stimulus' + mod)
        # stim = cosinebump(self.trial['theta2'], self.theta, coh2)
        stim = _gaussianbump(self.trial['theta2'], self.theta, coh2)
        self.add_ob(stim, period2, where='stimulus' + mod)

    def new_trial(self, **kwargs):
        self.trial = {}
        i_theta1 = self.rng.choice(self.choices)
        while True:
            i_theta2 = self.rng.choice(self.choices)
            if i_theta2 != i_theta1:
                break
        self.trial['theta1'] = self.theta[i_theta1]
        self.trial['theta2'] = self.theta[i_theta2]

        # Periods
        if self.delaycomparison:
            periods = ['fixation', 'stim1', 'delay', 'stim2', 'decision']
        else:
            periods = ['fixation', 'stimulus', 'decision']
        self.add_period(periods, after=0, last_period=True)

        self.add_ob(1, where='fixation')
        self.set_ob(0, 'decision')
        if self.delaycomparison:
            self.add_randn(0, self.sigma, ['stim1', 'stim2'])
        else:
            self.add_randn(0, self.sigma, ['stimulus'])

        coh1, coh2 = 0, 0
        if self.stim_mod1:
            self._add_singlemod(mod=1)
            coh1 += self.w_mod1 * self.trial['coh1_mod1']
            coh2 += self.w_mod1 * self.trial['coh2_mod1']
        if self.stim_mod2:
            self._add_singlemod(mod=2)
            coh1 += self.w_mod2 * self.trial['coh1_mod2']
            coh2 += self.w_mod2 * self.trial['coh2_mod2']

        i_target = i_theta1 if coh1 + self.rng.uniform(-1e-6, 1e-6) > coh2 else i_theta2
        self.set_groundtruth(self.act_dict['choice'][i_target], 'decision')

    def _step(self, action):
        # ---------------------------------------------------------------------
        # Reward and inputs
        # ---------------------------------------------------------------------
        new_trial = False
        gt = self.gt_now
        ob = self.ob_now
        # rewards
        reward = 0
        if self.in_period('fixation'):
            if action != 0:
                new_trial = self.abort
                reward = self.rewards['abort']
        elif self.in_period('decision'):
            if action != 0:
                new_trial = True
                if action == gt:
                    reward = self.rewards['correct']
                    self.performance = 1
                else:
                    reward = self.rewards['fail']

        return ob, reward, False, {'new_trial': new_trial, 'gt': gt}


class _DelayMatch1DResponse(ngym.PeriodEnv):
    r"""Delay match-to-sample or category task.

    A sample stimulus is followed by a delay and test. Agents are required
    to indicate if the sample and test are in the same category.

    Args:
        matchto: str, 'sample' or 'category'
        matchgo: bool,
            if True (False), go to the last stimulus if match (non-match)
    """
    metadata = {
        'paper_link': 'https://www.nature.com/articles/nature05078',
        'paper_name': '''Experience-dependent representation
        of visual categories in parietal cortex''',
        'tags': ['perceptual', 'working memory', 'two-alternative',
                 'supervised']
    }

    def __init__(self, dt=100, rewards=None, timing=None, sigma=1.0,
                 dim_ring=16, matchto='sample', matchgo=True):
        super().__init__(dt=dt)
        self.matchto = matchto
        if self.matchto not in ['sample', 'category']:
            raise ValueError('Match has to be either sample or category')
        self.matchgo = matchgo
        self.choices = ['match', 'non-match']  # match, non-match

        self.sigma = sigma / np.sqrt(self.dt)  # Input noise

        # Rewards
        self.rewards = {'abort': -0.1, 'correct': +1., 'fail': 0.}
        if rewards:
            self.rewards.update(rewards)

        self.timing = {
            'fixation': ('constant', 300),
            'sample': ('constant', 500),
            'delay': ('constant', 1000),
            'test': ('constant', 500),
            'decision': ('constant', 900)}
        if timing:
            self.timing.update(timing)

        self.abort = False

        if np.mod(dim_ring, 2) != 0:
            raise ValueError('dim ring should be an even number')
        self.dim_ring = dim_ring
        self.half_ring = int(self.dim_ring/2)
        self.theta = np.linspace(0, 2 * np.pi, dim_ring + 1)[:-1]

        self.observation_space = spaces.Box(
            -np.inf, np.inf, shape=(1 + dim_ring,), dtype=np.float32)
        self.ob_dict = {'fixation': 0, 'stimulus': range(1, dim_ring + 1)}
        self.action_space = spaces.Discrete(1+dim_ring)
        self.act_dict = {'fixation': 0, 'choice': range(1, dim_ring+1)}

    def new_trial(self, **kwargs):
        # Trial info
        self.trial = {
            'ground_truth': self.rng.choice(self.choices),
        }
        self.trial.update(**kwargs)

        ground_truth = self.trial['ground_truth']
        i_sample_theta = self.rng.choice(self.dim_ring)
        if self.matchto == 'category':
            sample_category = (i_sample_theta > self.half_ring) * 1
            if ground_truth == 'match':
                test_category = sample_category
            else:
                test_category = 1 - sample_category
            i_test_theta = self.rng.choice(self.half_ring)
            i_test_theta += test_category * self.half_ring
        else:  # match to sample
            if ground_truth == 'match':
                i_test_theta = i_sample_theta
            else:
                # non-match is 180 degree apart
                i_test_theta = np.mod(
                    i_sample_theta + self.half_ring, self.dim_ring)

        self.trial['sample_theta'] = sample_theta = self.theta[i_sample_theta]
        self.trial['test_theta'] = test_theta = self.theta[i_test_theta]

        stim_sample = _gaussianbump(sample_theta, self.theta, 1)
        stim_test = _gaussianbump(test_theta, self.theta, 1)

        # Periods
        self.add_period(['fixation', 'sample', 'delay', 'test', 'decision'],
                        after=0, last_period=True)

        self.add_ob(1, where='fixation')
        self.set_ob(0, 'decision', where='fixation')
        self.add_ob(stim_sample, 'sample', where='stimulus')
        self.add_ob(stim_test, 'test', where='stimulus')
        self.add_randn(0, self.sigma, ['sample', 'test'], where='stimulus')

        if ((ground_truth == 'match' and self.matchgo) or
                (ground_truth == 'non-match' and not self.matchgo)):
            self.set_groundtruth(self.act_dict['choice'][i_test_theta], 'decision')

    def _step(self, action, **kwargs):
        new_trial = False

        ob = self.ob_now
        gt = self.gt_now

        reward = 0
        if self.in_period('fixation'):
            if action != 0:
                new_trial = self.abort
                reward = self.rewards['abort']
        elif self.in_period('decision'):
            if action != 0:
                new_trial = True
                if action == gt:
                    reward = self.rewards['correct']
                    self.performance = 1
                else:
                    reward = self.rewards['fail']

        return ob, reward, False, {'new_trial': new_trial, 'gt': gt}


def _reach(**kwargs):
    envs = list()
    for modality in [0, 1]:
        env = _Reach(**kwargs)
        env = _MultiModalityStimulus(env, modality=modality, n_modality=2)
        envs.append(env)
    schedule = scheduler.RandomSchedule(len(envs))
    env = ScheduleEnvs(envs, schedule, env_input=False)
    return env


def go(**kwargs):
    env_kwargs = kwargs.copy()
    env_kwargs['anti'] = False
    return _reach(**env_kwargs)


def anti(**kwargs):
    env_kwargs = kwargs.copy()
    env_kwargs['anti'] = True
    return _reach(**env_kwargs)


def rtgo(**kwargs):
    env_kwargs = kwargs.copy()
    env_kwargs['anti'] = False
    env_kwargs['reaction'] = True
    return _reach(**env_kwargs)


def rtanti(**kwargs):
    env_kwargs = kwargs.copy()
    env_kwargs['anti'] = True
    env_kwargs['reaction'] = True
    return _reach(**env_kwargs)


def dlygo(**kwargs):
    env_kwargs = kwargs.copy()
    env_kwargs['anti'] = False
    env_kwargs['timing'] = {'delay': ('constant', 500)}
    return _reach(**env_kwargs)


def dlyanti(**kwargs):
    env_kwargs = kwargs.copy()
    env_kwargs['anti'] = True
    env_kwargs['timing'] = {'delay': ('constant', 500)}
    return _reach(**env_kwargs)


def _dm_kwargs():
    env_kwargs = {'cohs': [0.08, 0.16, 0.32, 0.64],
                  'delaycomparison': False}
    return env_kwargs


def dm1(**kwargs):
    env_kwargs = _dm_kwargs()
    env_kwargs.update({'w_mod': (1, 1), 'stim_mod': (True, False)})
    env_kwargs.update(kwargs)
    return _DMFamily(**env_kwargs)


def dm2(**kwargs):
    env_kwargs = _dm_kwargs()
    env_kwargs.update({'w_mod': (1, 1), 'stim_mod': (False, True)})
    env_kwargs.update(kwargs)
    return _DMFamily(**env_kwargs)


def ctxdm1(**kwargs):
    env_kwargs = _dm_kwargs()
    env_kwargs.update({'w_mod': (1, 0), 'stim_mod': (True, True)})
    env_kwargs.update(kwargs)
    return _DMFamily(**env_kwargs)


def ctxdm2(**kwargs):
    env_kwargs = _dm_kwargs()
    env_kwargs.update({'w_mod': (0, 1), 'stim_mod': (True, True)})
    env_kwargs.update(kwargs)
    return _DMFamily(**env_kwargs)


def multidm(**kwargs):
    env_kwargs = _dm_kwargs()
    env_kwargs.update({'w_mod': (1, 1), 'stim_mod': (True, True)})
    env_kwargs.update(kwargs)
    return _DMFamily(**env_kwargs)


def _dlydm_kwargs():
    env_kwargs = {'cohs': [0.3, 0.6, 1.0],
                  'delaycomparison': True}
    return env_kwargs


def dlydm1(**kwargs):
    env_kwargs = _dlydm_kwargs()
    env_kwargs.update({'w_mod': (1, 1), 'stim_mod': (True, False)})
    env_kwargs.update(kwargs)
    return _DMFamily(**env_kwargs)


def dlydm2(**kwargs):
    env_kwargs = _dlydm_kwargs()
    env_kwargs.update({'w_mod': (1, 1), 'stim_mod': (False, True)})
    env_kwargs.update(kwargs)
    return _DMFamily(**env_kwargs)


def ctxdlydm1(**kwargs):
    env_kwargs = _dlydm_kwargs()
    env_kwargs.update({'w_mod': (1, 0), 'stim_mod': (True, True)})
    env_kwargs.update(kwargs)
    return _DMFamily(**env_kwargs)


def ctxdlydm2(**kwargs):
    env_kwargs = _dlydm_kwargs()
    env_kwargs.update({'w_mod': (0, 1), 'stim_mod': (True, True)})
    env_kwargs.update(kwargs)
    return _DMFamily(**env_kwargs)


def multidlydm(**kwargs):
    env_kwargs = _dlydm_kwargs()
    env_kwargs.update({'w_mod': (1, 1), 'stim_mod': (True, True)})
    env_kwargs.update(kwargs)
    return _DMFamily(**env_kwargs)


def _dlymatch(matchto, matchgo, **kwargs):
    envs = list()
    for modality in [0, 1]:
        env_kwargs = {'matchto': matchto, 'matchgo': matchgo}
        env_kwargs.update(kwargs)
        env = _DelayMatch1DResponse(**env_kwargs)
        env = _MultiModalityStimulus(env, modality=modality, n_modality=2)
        envs.append(env)
    schedule = scheduler.RandomSchedule(len(envs))
    env = ScheduleEnvs(envs, schedule, env_input=False)
    return env


def dms(**kwargs):
    return _dlymatch(matchto='sample', matchgo=True, **kwargs)


def dnms(**kwargs):
    return _dlymatch(matchto='sample', matchgo=False, **kwargs)


def dmc(**kwargs):
    return _dlymatch(matchto='category', matchgo=True, **kwargs)


def dnmc(**kwargs):
    return _dlymatch(matchto='category', matchgo=False, **kwargs)
