"""Independent induction obligations; does not import the VM or discovery code.
The tail denotes the induction hypothesis, not an untested arbitrary output.
"""


def symbolic(p,empty,hit=None,kind='find'):
    op=p[0]
    if op=='empty':return symbolic(p[1] if empty else p[2],empty,hit,kind)
    if op=='hit':
        if empty:raise ValueError('unprotected predicate')
        return symbolic(p[1] if hit else p[2],empty,hit,kind)
    if kind=='find':
        if op=='none':return 'NONE'
        if op=='here' and not empty:return 'HERE'
        if op=='recur' and not empty:return 'TAIL_SEARCH'
    else:
        if op=='nil':return ()
        if op=='mapped' and not empty:return ('MAP_HEAD',)
        if op=='recur' and not empty:return ('MAP_TAIL',)
        if op=='raw':return () if empty else ('RAW_INPUT',)
        if op=='join':return symbolic(p[1],empty,hit,kind)+symbolic(p[2],empty,hit,kind)
    raise ValueError('unprotected or unknown instruction')


def prove(p,kind):
    try:
        if kind=='find':
            actual=[symbolic(p,True,kind=kind),symbolic(p,False,True,kind),symbolic(p,False,False,kind)]
            expected=['NONE','HERE','TAIL_SEARCH']
        elif kind=='flatmap':
            actual=[symbolic(p,True,kind=kind),symbolic(p,False,kind=kind)]
            expected=[(),('MAP_HEAD','MAP_TAIL')]
        else:raise ValueError('unknown kind')
        return {'passed':actual==expected,'actual':actual,'expected':expected,
                'assumptions':['finite inputs','pure callbacks','correct primitives','sufficient fuel']}
    except (ValueError,IndexError,TypeError) as e:return {'passed':False,'error':str(e)}
