"""Reference-only heterogeneous observation-stream worlds.

These *hidden* generator specifications MUST NOT be passed to the learner.
The actions here are randomized interventions selected by the evaluator, not
an agent's model-derived decisions. One world is continued across all steps;
no hidden-world reset is available during the trial.
"""
from __future__ import annotations
from random import Random
from dataclasses import dataclass

FAMILIES=('action_bias','lagged','two_step_delay','xor_memory','regime_switch','hidden_flip','noisy_adversary')

@dataclass
class World:
    seed:int
    family:str
    length:int=90

    def __post_init__(self):
        if self.family not in FAMILIES:raise ValueError(self.family)
        self.rng=Random(self.seed*3307+61)
        self.previous_outputs=[]
        self.previous_actions=[]
        self.hidden=self.rng.randrange(2)
        self.p0=.12+.16*self.rng.random()
        self.p1=.72+.15*self.rng.random()
        self.flip=self.rng.randrange(2)
        self.shift_at=self.length//2 + self.rng.randrange(-8,9)

    def observe(self,a:int):
        if a not in (0,1):raise ValueError('action')
        i=len(self.previous_outputs)
        yprev=self.previous_outputs[-1] if self.previous_outputs else 0
        yprev2=self.previous_outputs[-2] if len(self.previous_outputs)>=2 else 0
        action_prev2=self.previous_actions[-2] if len(self.previous_actions)>=2 else 0
        if self.family=='action_bias':p=self.p1 if a else self.p0
        elif self.family=='lagged':p=.94 if (yprev ^ a ^ self.flip) else .06
        elif self.family=='two_step_delay':p=.92 if (action_prev2 ^ self.flip) else .08
        elif self.family=='xor_memory':p=.95 if (yprev ^ yprev2 ^ a ^ self.flip) else .05
        elif self.family=='regime_switch':
            base=self.p1 if a else self.p0
            p=base if i<self.shift_at else 1-base
        elif self.family=='hidden_flip':
            if self.rng.random() < (.06 if a else .18):self.hidden ^= 1
            p=.93 if self.hidden else .07
        else:
            # Data generating process deliberately not in the small fixed
            # local conditional grammar; no safety or optimality claim.
            p=.5+.35*((2*self.rng.random()-1))
        output=int(self.rng.random()<p)
        self.previous_actions.append(a);self.previous_outputs.append(output)
        return output


def exogenous_actions(seed,length):
    r=Random(seed*81023+94)
    return [r.randrange(2) for _ in range(length)]
