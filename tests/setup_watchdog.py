"""Production watchdog helpers with engine wait/event stand-ins, not the Papyrus VM."""
from types import SimpleNamespace as NS
from unittest.mock import patch
import re
from papyrus_harness import helper, source

def scenario(cancel=None, old_serial=False, sender_valid=True):
    state=dict(_SetupWatchdogActive=True,_SetupWatchdogRevision=4,_SetupWatchdogSerial=7,
               _SetupWatchdogPendingSerial=-1,_SetupStartedAt=100.,LifecycleRevision=4)
    phase=['Making']; calls=[]; queued=[]; functions=[]; actor=object(); wall=[100.]
    def publish(**updates):
        state.update(updates)
        for f in functions:f.__globals__.update(state)
    def bind(name,args,writes=(),event=False):
        env=dict(state,thread_id=0,Self=actor,GetState=lambda:phase[0],STATE_SETUP='Making',
                 RegisterForModEvent=lambda *a:calls.append('register'),
                 SendModEvent=lambda *a:queued.append(a),UnregisterForModEvent=lambda *a:None,
                 Utility=NS(Wait=wait,GetCurrentRealTime=lambda:wall[0]),
                 Fatal=fatal,Initialize=initialize,ExpireSetupWatchdog=lambda *a:expire(*a),
                 sslLog=NS(Log=lambda *a:None))
        if event:
            body=re.search(r'Event OnSetupWatchdog\([^\n]*\)(.*?)EndEvent',source('sslThreadModel'),re.S)[1]
            with patch('papyrus_harness.body',return_value=body):f=helper('sslThreadModel',name,args,env,writes)
        else:f=helper('sslThreadModel',name,args,env,writes)
        functions.append(f)
        def invoke(*a):
            f.__globals__.update(state)
            try:return f(*a)
            finally:publish(**{k:f.__globals__[k] for k in writes})
        return invoke
    def fatal(*a):
        assert a[-1] is False
        calls.append('fatal')
        if cancel=='fatal-reuse':publish(LifecycleRevision=5,_SetupWatchdogSerial=8)
    def initialize():
        calls.append('reset'); phase[0]='Unlocked'
        publish(_SetupWatchdogActive=False)
    def wait(seconds):
        assert seconds==30.
        calls.append('wait')
        # Five active seconds plus forty paused menu seconds do not finish this wait.
        wall[0]=145.
        for _ in range(3):check()
        assert 'fatal' not in calls and len(queued)==1
        if cancel=='start':publish(_SetupWatchdogActive=False)
        if cancel=='reuse':publish(LifecycleRevision=5,_SetupWatchdogSerial=8)
        if cancel=='rearm':publish(_SetupWatchdogSerial=8)
        if cancel=='leave':phase[0]='Animating'
        # Native Wait returns only after the remaining 25 active seconds.
        wall[0]=170.
    check=bind('CheckSetupWatchdog','',('_SetupWatchdogPendingSerial',))
    expire=bind('ExpireSetupWatchdog','requestRevision,requestSerial',('_SetupWatchdogActive',))
    event=bind('OnSetupWatchdog','asEventName,asStringArg,afNumArg,akSender',event=True)
    check(); check()
    assert len(queued)==1 and 'fatal' not in calls
    event('event','6' if old_serial else '7',0,actor if sender_valid else None)
    if old_serial or not sender_valid:assert calls==['register']
    elif cancel=='fatal-reuse':assert calls==['register','wait','fatal']
    elif cancel:assert calls==['register','wait']
    else:
        assert calls==['register','wait','fatal','reset']
        expire(4,7); assert calls==['register','wait','fatal','reset']

for cancel in (None,'start','reuse','rearm','leave','fatal-reuse'):scenario(cancel)
scenario(old_serial=True);scenario(sender_valid=False)
s=source('sslThreadModel')
check=s[s.index('Function CheckSetupWatchdog()'):s.index('Event OnSetupWatchdog(')]
assert 'GetCurrentRealTime' not in check and 'Fatal(' not in check
assert 'Utility.Wait(30.0)' in s and 'WaitMenuMode' not in s[s.index('Event OnSetupWatchdog('):s.index('Function ExpireSetupWatchdog(')]
assert s.count('ArmSetupWatchdog()\n\t\tGoToState(STATE_SETUP)')==3
start=s[s.index('Function StartThread()'):]
assert start.index('DisarmSetupWatchdog()') < start.index('UnregisterForUpdate()')
init=s[s.index('; Reset this thread to base status'):]
assert init.index('DisarmSetupWatchdog()') < init.index('LifecycleRevision += 1')
print('PASS: 5 active + 40 menu seconds + old updates, one pending wait, real expiry, cancelled/reused/rearmed/wrong-sender callbacks, single reset and entry wiring')
