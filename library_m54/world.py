"""Hidden simulator and observation-only capability port. No task success is returned."""
from collections import Counter
P=7
class World:
    def __init__(self,parameters):
        self.parameters=parameters;self.level=0
        self.positions=[0,2];self.last=0;self.bias=[0,0]
        self.cost=Counter();self.events=[];self.outside=False
    def gain(self,s):
        p,o,obj,h=s;d,k,op,t,g=self.parameters
        if self.level==0:return g[0]
        if (p-o)%P==d:
            return g[3] if self.level>=3 and (h<t if op=='less' else h==t) else g[1]
        return g[2] if self.level>=2 and obj==k else g[0]
    def sense(self):
        self.cost['sensor_scalars']+=4
        return {'workers':[[(p+b)%P for p in self.positions] for b in self.bias]}
    def move(self,obj,a,mode='task'):
        before=self.positions[:];s=(before[obj],before[1-obj],obj,self.last)
        gain=self.gain(s);shift=gain*a%P
        if self.outside and s[0]==5 and s[3]==6:shift=(shift+1)%P
        self.positions[obj]=(before[obj]+shift)%P;self.last=a
        self.cost[mode+'_moves']+=1
        self.events.append({'before':before,'after':self.positions[:],'state':list(s),'command':a,'gain_gold':gain,'level_gold':self.level,'mode':mode})
        return self.sense()
    def place(self,positions):
        if len(positions)!=2 or any(type(v)is not int or not 0<=v<7 for v in positions):raise ValueError('fixture values')
        self.positions=positions[:];self.cost['fixture_placements']+=2;return self.sense()
    def calibrate(self,anchor):
        self.cost['calibration_scalars']+=2
        return {'anchor':anchor,'readings':[(anchor+b)%7 for b in self.bias]}
class Port:
    __slots__=('__world',)
    def __init__(self,w):self.__world=w
    def sense(self):return self.__world.sense()
    def move(self,obj,a,mode='task'):return self.__world.move(obj,a,mode)
    def place(self,positions):return self.__world.place(positions)
    def calibrate(self,anchor):return self.__world.calibrate(anchor)
