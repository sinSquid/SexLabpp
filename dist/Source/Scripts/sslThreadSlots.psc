ScriptName sslThreadSlots extends Quest
{
  Script for maintaining animation threads and immediately related functionality
}

int Function GetTotalThreadCount() global
  return 15
EndFunction

; *-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-* ;
; ----------------------------------------------------------------------------- ;
;        ██╗███╗   ██╗████████╗███████╗██████╗ ███╗   ██╗ █████╗ ██╗            ;
;        ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗████╗  ██║██╔══██╗██║            ;
;        ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝██╔██╗ ██║███████║██║            ;
;        ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗██║╚██╗██║██╔══██║██║            ;
;        ██║██║ ╚████║   ██║   ███████╗██║  ██║██║ ╚████║██║  ██║███████╗       ;
;        ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝       ;
; ----------------------------------------------------------------------------- ;
; *-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-* ;

sslThreadController[] Property Threads Auto

; ------------------------------------------------------- ;
; --- Thread Access                                   --- ;
; ------------------------------------------------------- ;

sslThreadModel Function PickModel(float TimeOut = 5.0)
  GoToState("Locked")
  int i = 0
  While (i < Threads.Length)
    If (!Threads[i].IsLocked)
      sslThreadModel model = Threads[i].Make()
      GoToState("Ready")
      return model
    EndIf
    i += 1
  EndWhile
  Debug.Trace("[SexLab] Unable to obtain new thread. All threads in locked State", 1)
  GoToState("Ready")
  return none
EndFunction

SexLabThread Function GetThread(int aiThreadID)
  return Threads[aiThreadID]
EndFunction

int Function FindActorController(Actor ActorRef)
  float f = 0
  int ret = -1
  int i = 0
  While (i < Threads.Length)
    If (Threads[i].FindSlot(ActorRef) != -1)
      ; An actor may be recognized in multiple threads if it is thrown into multiple scenes back to back
      ; To ensure this returns the most recent scene, check for active State or start time 
      int status = Threads[i].GetStatus()
      If ((status == Threads[i].STATUS_INSCENE || status == Threads[i].STATUS_SETUP) && \
            (ret == -1 || Threads[i].StartedAt > f))
        f = Threads[i].StartedAt
        ret = i
      EndIf
    EndIf
    i += 1
  Endwhile
  return ret
EndFunction

SexLabThread Function GetThreadByActor(Actor akActor)
  int i = FindActorController(akActor)
  If (i == -1)
    return none
  EndIf
  return GetThread(i)
EndFunction

int Function ActiveThreads()
  int c = 0
  int i = Threads.Length
  while i
    i -= 1
    c += Threads[i].IsLocked as int
  endwhile
  return c
endfunction

bool Function IsRunning()
  return ActiveThreads() > 0
endfunction

int _stopRequestsInProgress
int _stopRequestRevision
bool _sendingStopNotifications
bool _stopNotificationsPending
bool _loadNotificationPending

Function StopAll()
  RequestStopAll(false)
EndFunction

Function StopAllOnGameLoad()
  RequestStopAll(true)
EndFunction

Function RequestStopAll(bool abGameLoad)
  _stopRequestsInProgress += 1
  _stopRequestRevision += 1
  _stopNotificationsPending = true
  If (abGameLoad)
    _loadNotificationPending = true
  EndIf
  int i = Threads.Length
  While (i > 0)
    i -= 1
    StopThread(Threads[i])
  EndWhile
  _stopRequestsInProgress -= 1
  CompletePendingStopNotifications()
EndFunction

Function CompletePendingStopNotifications()
  If (_sendingStopNotifications || !_stopNotificationsPending || _stopRequestsInProgress > 0)
    return
  EndIf
  int revision = _stopRequestRevision
  int i = Threads.Length
  While (i > 0)
    i -= 1
    If (Threads[i].IsEndingRecyclePending())
      return
    EndIf
  EndWhile
  int handle = ModEvent.Create("SexLabStoppedActive")
  If (_sendingStopNotifications || !_stopNotificationsPending || _stopRequestsInProgress > 0 || revision != _stopRequestRevision)
    If (handle)
      ModEvent.Release(handle)
    EndIf
    return
  EndIf
  _sendingStopNotifications = true
  _stopNotificationsPending = false
  If (handle)
    ModEvent.Send(handle)
  EndIf
  If (_loadNotificationPending && revision == _stopRequestRevision)
    int loadHandle = ModEvent.Create("SexLabGameLoaded")
    If (revision == _stopRequestRevision && _stopRequestsInProgress == 0)
      _loadNotificationPending = false
      If (loadHandle)
        ModEvent.Send(loadHandle)
      EndIf
    ElseIf (loadHandle)
      ModEvent.Release(loadHandle)
    EndIf
  EndIf
  _sendingStopNotifications = false
  If (_stopNotificationsPending)
    CompletePendingStopNotifications()
  EndIf
EndFunction

Function StopThread(sslThreadController Slot)
  int revision = Slot.RecycleRevision
  If (Slot.GetStatus() == Slot.STATUS_IDLE)
    return
  EndIf
  sslLog.Log("Stopping thread " + Slot + " in state " + Slot.GetState())
  If (revision != Slot.RecycleRevision)
    return
  EndIf
  Slot.EndAnimation()
  If (revision == Slot.RecycleRevision)
    Slot.Initialize()
  EndIf
EndFunction

; ------------------------------------------------------- ;
; --- Setup                                           --- ;
; ------------------------------------------------------- ;

Function Setup()
  GoToState("Locked")
  If (!TestSlots())
    InstallSlots()
  Else
    int i = 0
    While (i < Threads.Length)
      Threads[i].SetTID(i)
      i += 1
    EndWhile
  EndIf
  GoToState("Ready")
EndFunction

bool Function TestSlots()
  return Threads.Length == 15 && Threads.Find(none) == -1
EndFunction
Function InstallSlots()
  int[] SlotFormID = new int[15]
  SlotFormID[0]  = 0x61EEF
  SlotFormID[1]  = 0x62452
  SlotFormID[2]  = 0x6C62C
  SlotFormID[3]  = 0x6C62D
  SlotFormID[4]  = 0x6C62E
  SlotFormID[5]  = 0x6C62F
  SlotFormID[6]  = 0x6C630
  SlotFormID[7]  = 0x6C631
  SlotFormID[8]  = 0x6C632
  SlotFormID[9]  = 0x6C633
  SlotFormID[10] = 0x6C634
  SlotFormID[11] = 0x6C635
  SlotFormID[12] = 0x6C636
  SlotFormID[13] = 0x6C637
  SlotFormID[14] = 0x6C638

  Threads = new sslThreadController[15]
  int i = 0
  While (i < Threads.Length)
    Threads[i] = Game.GetFormFromFile(SlotFormID[i], "SexLab.esm") as sslThreadController
    Threads[i].SetTID(i)
    i += 1
  EndWhile
EndFunction

State Ready
  Function Setup()
    StopAll()
    GoToState("")
    Setup()
  EndFunction
EndState

State Locked
  Function Setup()
    While (GetState() == "Locked")
      Utility.WaitMenuMode(0.1)
    EndWhile
    Setup()
  EndFunction

  sslThreadModel Function PickModel(float TimeOut = 5.0)
    float deadline = Utility.GetCurrentRealTime() + TimeOut
    While (GetState() == "Locked")
      If (Utility.GetCurrentRealTime() >= deadline)
        return none
      EndIf
      Utility.WaitMenuMode(0.1)
    EndWhile
    float remaining = deadline - Utility.GetCurrentRealTime()
    If (remaining <= 0.0)
      return none
    EndIf
    return PickModel(remaining)
  EndFunction
EndState

Auto State ToBeInitialized
  sslThreadModel Function PickModel(float TimeOut = 5.0)
    return none
  EndFunction
EndState

; *-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-* ;
; ----------------------------------------------------------------------------- ;
;               ██╗     ███████╗ ██████╗  █████╗  ██████╗██╗   ██╗              ;
;               ██║     ██╔════╝██╔════╝ ██╔══██╗██╔════╝╚██╗ ██╔╝              ;
;               ██║     █████╗  ██║  ███╗███████║██║      ╚████╔╝               ;
;               ██║     ██╔══╝  ██║   ██║██╔══██║██║       ╚██╔╝                ;
;               ███████╗███████╗╚██████╔╝██║  ██║╚██████╗   ██║                 ;
;               ╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝   ╚═╝                 ;
; ----------------------------------------------------------------------------- ;
; *-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-* ;

sslSystemConfig Property Config Hidden
  sslSystemConfig Function Get()
    return Game.GetFormFromFile(0xD62, "SexLab.esm") as sslSystemConfig
  EndFunction
  Function Set(sslSystemConfig aSet)
  EndFunction
EndProperty

SexLabFramework Property SexLab Hidden
  SexLabFramework Function Get()
    return Game.GetFormFromFile(0xD62, "SexLab.esm") as SexLabFramework
  EndFunction
  Function Set(SexLabFramework aSet)
  EndFunction
EndProperty

sslThreadController Function GetController(int tid)
  return Threads[tid]
endfunction
sslThreadController Function GetActorController(Actor ActorRef)
  int i = FindActorController(ActorRef)
  If (i == -1)
    return none
  EndIf
  return GetController(i)
EndFunction
