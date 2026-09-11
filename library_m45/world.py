"""Evaluation-only physics and three actual action sources observed through two Workers.
The learner sees no commands of others and no source labels. Paths are tracked within a
synchronised interval, randomly re-aliased at the next interval. This is an assumption.
"""
from random import Random
from fractions import Fraction
from library_m37.world import World as BaseWorld
from .core import DOMAIN, MODELS, LINEAR


class World(BaseWorld):
    def __init__(self, seed):
        super().__init__(seed % 5, (seed+2)%5)
        self.permutation=tuple(range(5))
        rng=Random(seed ^ 0x9137)
        nonlinear=[m for m in MODELS if m not in LINEAR]
        self.contexts=[rng.choice(LINEAR),rng.choice(nonlinear),rng.choice(LINEAR),rng.choice(nonlinear)]
        self.others=[{'apple':rng.randrange(5),'teacup':rng.randrange(5)} for _ in range(2)]
        self.other_maps=[rng.choice(MODELS),rng.choice(MODELS)]
        self.scene=0
        self.phase=0
        self.seed=seed
        self.position_switch=False
        self.interval_counter=0

    def set_scene(self, scene, phase):
        # Only evaluator calls this; observable scene is a context, NOT an event label.
        if phase in (8,10):
            rng=Random(self.seed*919+phase)
            self.contexts[scene]=rng.choice([m for m in MODELS if m!=self.contexts[scene] and m not in LINEAR])
        self.scene=scene;self.phase=phase;self.permutation=self.contexts[scene]
        self.tick=phase

    def step(self,obj,action,diagnostic=False):
        before=dict(self.positions)
        delta=self.permutation[action % 5]
        if self.position_switch and before[obj]==4:delta=(delta+1)%5
        self.positions[obj]=(before[obj]+delta)%5
        self.cost['control_moves' if diagnostic else 'task_moves']+=1
        row={'time':self.tick,'object':obj,'command':action,'before':before,
             'after':dict(self.positions),'diagnostic':diagnostic}
        self.moves.append(row)
        return row

    def capture(self,positions):
        return [[int(w.emit(Fraction(positions[o])))%5 for o in ('apple','teacup')]
                for w in self.workers]


class AnonymousPort:
    __slots__=('__world','__rng','__order','__paths','__mode','__serial','__interval','private_log')
    def __init__(self,world,mode='independent'):
        self.__world=world;self.__mode=mode;self.__serial=0
        self.private_log=[]  # evaluator only; not read by learner; not a hostile-process boundary.

    def open_interval(self):
        w=self.__world;w.interval_counter+=1;self.__serial=w.interval_counter
        self.__rng=Random(w.seed*100003+w.phase*97+self.__serial)
        self.__order=[0,1,2];self.__rng.shuffle(self.__order)
        self.__paths=[[],[],[]]
        self.__interval=(w.phase*100+self.__serial)
        self.private_log.append({'interval':self.__interval,'phase':w.phase,'scene':w.scene,
             'order':self.__order[:],'true_source_index':self.__order.index(0),
             'own_map':list(w.permutation),'rounds':[],'mode':self.__mode})
        return self.__interval

    def probe(self,obj,command):
        w=self.__world;object_name=('apple','teacup')[obj]
        commands=[(obj,command)]
        for _ in range(2):
            commands.append((obj,command) if self.__mode.startswith('echo') else
                            (self.__rng.randrange(2),self.__rng.randrange(5)))
        private=[]
        for actor,(o,cmd) in enumerate(commands):
            name=('apple','teacup')[o]
            positions=w.positions if actor==0 else w.others[actor-1]
            before=w.capture(positions)
            old=dict(positions)
            mapping=w.permutation if actor==0 or self.__mode=='echo_equal' else w.other_maps[actor-1]
            if actor==0:w.step(name,cmd,True)
            else:positions[name]=(positions[name]+mapping[cmd])%5
            after=w.capture(positions)
            self.__paths[actor].append({'before':before,'after':after})
            private.append({'actor':actor,'object':o,'command':cmd,'map':list(mapping),
                            'before':old,'after':dict(positions)})
        self.private_log[-1]['rounds'].append(private)
        # No role names, author IDs, true commands, path keys, refs or fingerprints.
        return {'paths':[[dict(f) for f in self.__paths[a]] for a in self.__order]}
