"""独立小世界与窄观察接口。隐藏机制只在评估层改变。"""
from fractions import Fraction as F
from library_m12.core import Worker


class World:
    def __init__(self, apple=1, teacup=3):
        self.positions={'apple':apple,'teacup':teacup}
        self.workers=[Worker(1,0),Worker(1,0)]
        self.gain=1
        self.physical_bias=[0,0]
        self.nonlinear=False
        self.cross_drift=False
        self.moves=[]
        self.cost={'sensor_scalars':0,'calibration_scalars':0,'control_moves':0,
                   'task_moves':0,'validation_scalars':0}
        self.tick=0

    def change(self,kind,queen,rng):
        """只有评估器调用；没有事件通知、类型或正确模型送入 Queen。"""
        from library_m12.core import PROGRAMS,compile_judge
        if kind in ('self','combined'):
            options=[p for p in PROGRAMS if p!=(0,0,0)]
            p=rng.choice(options)
            queen._judge=compile_judge(p)
        else:p=None
        changed=[]
        if kind in ('worker','combined'):
            i=rng.randrange(2)
            self.physical_bias[i]=2-self.physical_bias[i]
            self.workers[i]._Worker__bias=F(self.physical_bias[i])
            changed.append(i)
        if kind in ('environment','combined'):
            self.gain=-self.gain
        if kind=='outside':self.gain=2
        if kind=='cross_drift':self.cross_drift=True
        return {'kind':kind,'judge_injected':p,'workers_changed':changed,
                'gain':self.gain,'bias':self.physical_bias[:]}

    def step(self,obj,action,diagnostic=False):
        before=dict(self.positions)
        self.positions[obj]=(self.positions[obj]+self.gain*action)%5
        if self.cross_drift and obj=='apple':
            self.positions['teacup']=(self.positions['teacup']+1)%5
        self.cost['control_moves' if diagnostic else 'task_moves']+=1
        row={'time':self.tick,'object':obj,'command':action,'before':before,
             'after':dict(self.positions),'diagnostic':diagnostic}
        self.moves.append(row)
        return row

    def port(self):return Port(self)


class Port:
    """只提供观察、标定与受限作用；无事件表、故障名或历史作者接口。"""
    __slots__=('__world',)
    def __init__(self,world):self.__world=world

    def decoders(self):return tuple(w.decoder for w in self.__world.workers)

    def sense(self):
        out=[]
        for i,w in enumerate(self.__world.workers):
            raw={};decoded={}
            for obj,p in self.__world.positions.items():
                vals=[p-1,p,p+1]
                raw[obj]=[str(F(v)+self.__world.physical_bias[i]) for v in vals]
                decoded[obj]=[str(w.emit(F(v))) for v in vals]
                self.__world.cost['sensor_scalars']+=len(vals)
            a,c=map(F,(decoded['apple'][1],decoded['teacup'][1]))
            relations={'same_position':a==c,'apple_left_of_cup':a<c}
            out.append({'raw_seen':raw,'decoded':decoded,'relations':relations,
                        'scope':'two objects; five-position ring; noisy triples'})
        return out

    def move(self,obj,action):return self.__world.step(obj,action)

    def calibrate(self,i,anchors):
        self.__world.cost['calibration_scalars']+=len(anchors)
        w=self.__world.workers[i]
        return [int(w.emit(F(x)))+(int(x==3) if self.__world.nonlinear else 0) for x in anchors]

    def recalibrate(self,i,bias):
        return self.__world.workers[i].recalibrate(F(1),F(bias))

    def validate_calibration(self):
        ok=True
        for w in self.__world.workers:
            for x in (7,-3):
                self.__world.cost['validation_scalars']+=1
                ok &= w.emit(F(x))==x
        return ok

    def control_probe(self):
        deltas=[];cross=[]
        # 两个对象都实际移动一次，其他对象变化单独检查；探测有副作用并留档。
        for obj in ('apple','teacup'):
            before=self.sense()[0]['decoded']
            self.__world.step(obj,1,True)
            after=self.sense()[0]['decoded']
            other='teacup' if obj=='apple' else 'apple'
            deltas.append((int(F(after[obj][1]))-int(F(before[obj][1])))%5)
            cross.append((int(F(after[other][1]))-int(F(before[other][1])))%5)
        return {'command':1,'objects':['apple','teacup'],'deltas':deltas,'cross_deltas':cross}
