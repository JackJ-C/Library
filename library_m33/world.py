"""Independent small world. Hidden state belongs to the evaluator, not Queen.
Public reference markers and success feedback are explicitly trusted apparatus.
"""
from dataclasses import dataclass
from random import Random

MOD = 7
OBJECTS = ('apple', 'cup')


@dataclass
class Judge:
    """The actual arithmetic operator used by the Queen, mutable under fault injection."""
    sign: int = 1

    def __call__(self, displacement, inverse):
        return (self.sign * displacement * inverse) % MOD


class World:
    def __init__(self, seed):
        rng = Random(seed)
        self._positions = [rng.randrange(MOD), rng.randrange(MOD)]
        self._bias = [0, 0]
        self._gain = 1
        self.decoders = [0, 0]
        self.tick = 0
        self.nonlinear_worker = False
        self.nonlinear_motor = False
        self.lie_at_zero = False

    def _reading(self, worker, position):
        extra = int(self.nonlinear_worker and worker == 0 and position == 3)
        return (position + self._bias[worker] + self.decoders[worker] + extra) % MOD

    def sense(self):
        rows = []
        for worker in range(2):
            positions = [self._reading(worker, p) for p in self._positions]
            rows.append({'positions': positions, 'relations': {
                'same_place': positions[0] == positions[1],
                'apple_to_cup_clockwise': (positions[1] - positions[0]) % MOD}})
        return rows

    def move(self, obj, action, goal):
        extra = int(self.nonlinear_motor and action == 3)
        self._positions[obj] = (self._positions[obj] + self._gain * action + extra) % MOD
        return {'workers': self.sense(), 'success': self._positions[obj] == goal}

    def probe(self, query):
        kind, arg = query
        if kind in ('w0', 'w1'):
            worker = int(kind[-1])
            value = self._reading(worker, arg)
            if self.lie_at_zero and worker == 0 and arg == 0:
                value = (value + 1) % MOD
            return {'value': value, 'reference_position': arg, 'worker': worker}
        if kind == 'motor':
            before = self.sense()
            after = self.move(0, arg, 0)['workers']
            deltas = [(after[w]['positions'][0] - before[w]['positions'][0]) % MOD for w in range(2)]
            return {'value': deltas[0], 'second_delta': deltas[1],
                    'before': before, 'after': after, 'issued_action': arg}
        raise ValueError('unknown public probe')

    def adjust_decoder(self, worker, change):
        self.decoders[worker] = (self.decoders[worker] + change) % MOD

    def truth(self, queen):
        """Evaluator only; never passed into the agent's observation port."""
        return (queen._judge.sign,
                (self._bias[0] + self.decoders[0]) % MOD,
                (self._bias[1] + self.decoders[1]) % MOD, self._gain)


class Port:
    """Capability surface (not a hostile-process sandbox)."""
    def __init__(self, world):
        self.__world = world

    def sense(self):
        return self.__world.sense()

    def move(self, obj, action, goal):
        return self.__world.move(obj, action, goal)

    def probe(self, query):
        return self.__world.probe(query)

    def adjust_decoder(self, worker, change):
        self.__world.adjust_decoder(worker, change)
