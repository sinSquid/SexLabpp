scriptname sslVoiceSlots extends Quest
{
	Script for accessing voice data
}

; Selects matching voice for this actor. Returns saved voice if it exists
String Function SelectVoice(Actor akActor) native global
String Function SelectVoiceByTags(Actor akActor, String asTags) native global
String Function SelectVoiceByTagsA(Actor akActor, String[] asTags) native global

String Function GetSavedVoice(Actor akActor) native global
Function StoreVoice(Actor akActor, String asVoice) native global
Function DeleteVoice(Actor akActor) native global

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

String[] Function GetAllVoices(String asRaceKey) native global
Actor[] Function GetAllCachedUniqueActorsSorted(Actor akSecondPriority) native global
String Function SelectVoiceByRace(String asRaceKey) native global

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

string[] Property Registry Hidden
	String[] Function Get()
		SyncBackend()
		Alias[] aliases = GetAliases()
		String[] ret = Utility.CreateStringArray(aliases.Length)
		int i = 0
		int ii = 0
		While (i < aliases.Length)
			sslBaseVoice it = aliases[i] as sslBaseVoice
			If (it && it.Registered)
				ret[ii] = it.Name
				ii += 1
			EndIf
			i += 1
		EndWhile
		return PapyrusUtil.ClearEmpty(ret)
	EndFunction
EndProperty
int property Slotted hidden
	int Function Get()
		return Registry.Length
	EndFunction
EndProperty
sslBaseVoice[] property Voices hidden
	sslBaseVoice[] function get()
		return GetSlots(1, 128)
	endFunction
endProperty

Function SyncBackend()
	Alias[] aliases = GetAliases()
	String[] arr = GetAllVoices("")
	int i = 0
	int ii = 0
	While (i < aliases.Length)
		sslBaseVoice v = aliases[i] as sslBaseVoice
		If (v)
			v.Registry = v.GOTTA_LOVE_PEOPLE_WHO_THINK_REGISTRATION_FUNCTIONS_ARE_JUST_DECORATION
			If (ii < arr.Length)
				v.Registry = arr[ii]
				ii += 1
			Else
				v.Registry = ""
			EndIf
		EndIf
		i += 1
	EndWhile
EndFunction

; Libraries
sslSystemConfig property Config hidden
	sslSystemConfig Function Get()
		return SexLabUtil.GetConfig()
	EndFunction
EndProperty
Actor property PlayerRef hidden
	Actor Function Get()
		return Game.GetPlayer()
	EndFunction
EndProperty

; ------------------------------------------------------- ;
; --- Voice Filtering                                 --- ;
; ------------------------------------------------------- ;

sslBaseVoice[] function FilterTaggedVoices(sslBaseVoice[] VoiceList, string[] Tags, bool HasTag = true) global
	if VoiceList.Length < 1
		return VoiceList
	elseIf Tags.Length < 1
		if HasTag
			return sslUtility.VoiceArray(0)
		endIf
		return VoiceList
	endIf
	int i = VoiceList.Length
	bool[] Valid = Utility.CreateBoolArray(i)
	while i
		i -= 1
		Valid[i] = VoiceList[i].HasOneTag(Tags) == HasTag
	endWhile
	; Check results
	if Valid.Find(true) == -1
		return sslUtility.VoiceArray(0) ; No valid animations
	elseIf Valid.Find(false) == -1
		return VoiceList ; All valid animations
	endIf
	; Filter output
	i = VoiceList.Length
	int n = PapyrusUtil.CountBool(Valid, true)
	sslBaseVoice[] Output = sslUtility.VoiceArray(n)
	while i && n
		i -= 1
		if Valid[i]
			n -= 1
			Output[n] = VoiceList[i]
		endIf
	endWhile
	return Output
endFunction

sslBaseVoice[] function GetAllGender(int Gender)
	sslBaseVoice[] all = GetSlots(1, 128)
	bool[] Valid = Utility.CreateBoolArray(all.Length)
	int i = 0
	While (i < all.Length)
		sslBaseVoice Slot = all[i]
		Valid[i] = Slot.Enabled && !Slot.Creature && (Gender == Slot.Gender || Slot.Gender == -1)
		i += 1
	EndWhile
	return GetList(Valid)
endFunction

sslBaseVoice function PickGender(int Gender = 1)
	sslBaseVoice[] ret = GetAllGender(Gender)
	If (!ret.Length)
		return none
	EndIf
	return ret[Utility.RandomInt(0, ret.Length - 1)]
endFunction

sslBaseVoice function PickVoice(Actor ActorRef)
	String v = SelectVoice(ActorRef)
	If (!v)
		return none
	EndIf
	return GetbyRegistrar(v)

	; COMEBACK: Check what this all does. Might be interesting for native implementation
	; ; Pick a taged voice based on gender and scale
	; ActorBase BaseRef = ActorRef.GetLeveledActorBase()
	; float ActorScale = ActorRef.GetScale()
	; string Tags = "Male"
	; string SuppressTags = ""
	; string[] Filters
	; VoiceType ActorVoice = BaseRef.GetVoiceType()
	; string ActorVoiceString = ""
	; if ActorVoice
	; 	ActorVoiceString = ActorVoice as String
	; 	Log(ActorVoiceString)
	; 	if StringUtil.Find(ActorVoiceString, "Orc") >= 0 || StringUtil.Find(ActorVoiceString, "Brute") >= 0
	; 		Filters = PapyrusUtil.PushString(Filters, "Rough")
	; 	endIf
	; 	if StringUtil.Find(ActorVoiceString, "Toned") >= 0 || StringUtil.Find(ActorVoiceString, "Shrill") >= 0
	; 		Filters = PapyrusUtil.PushString(Filters, "Loud")
	; 	endIf
	; 	if StringUtil.Find(ActorVoiceString, "Sultry") >= 0
	; 		Filters = PapyrusUtil.PushString(Filters, "Excited")
	; 	endIf
	; 	if StringUtil.Find(ActorVoiceString, "Coward") >= 0
	; 		Filters = PapyrusUtil.PushString(Filters, "Quiet")
	; 	endIf
	; endIf
	; if BaseRef.GetSex() == 1
	; 	Tags = "Female"
	; endIf
	; if StringUtil.Find(ActorVoiceString, "Old") >= 0 || StringUtil.Find(ActorVoiceString, "Druk") >= 0 || StringUtil.Find(ActorVoiceString, "Khajiit") >= 0 || StringUtil.Find(ActorVoiceString, "Argonian") >= 0
	; 	SuppressTags = "Young"
	; 	Filters = PapyrusUtil.PushString(Filters, "Old")
	; elseIf StringUtil.Find(ActorVoiceString, "Young") >= 0 || ActorScale < 0.95
	; 	SuppressTags = "Old"
	; 	Filters = PapyrusUtil.PushString(Filters, "Young")
	; else
	; 	SuppressTags += ",Young,Old"
	; endif
	; sslBaseVoice[] VoiceList = GetAllByTags(Tags,SuppressTags)
	
	; sslBaseVoice[] Filtered = FilterTaggedVoices(VoiceList, Filters, true)
	; if Filtered.Length > 0 && VoiceList.Length > Filtered.Length
	; 	Log("Filtered out '"+(VoiceList.Length - Filtered.Length)+"' voices without the tags: "+Filters)
	; 	VoiceList = Filtered
	; endIf
	; if VoiceList && VoiceList.Length > 0
	; 	int i = (Utility.RandomInt(0, (VoiceList.Length - 1)))
	; 	if !IsPlayer && Config.NPCSaveVoice
	; 		SaveVoice(ActorRef, VoiceList[i])
	; 	endIf
	; 	return VoiceList[i]
	; endIf
	; ; Pick a random voice based on gender
	; sslBaseVoice Picked = PickGender(BaseRef.GetSex())
	; ; Save the voice to NPC for reuse, if enabled
	; if Picked && !IsPlayer && Config.NPCSaveVoice
	; 	SaveVoice(ActorRef, Picked)
	; endIf
	; return Picked
endFunction

sslBaseVoice function GetByTags(string Tags, string TagsSuppressed = "", bool RequireAll = true)
	sslBaseVoice[] Found = GetAllByTags(Tags, TagsSuppressed, RequireAll)
	if Found.Length
		return Found[(Utility.RandomInt(0, (Found.Length - 1)))]
	endIf
	return none
endFunction

sslBaseVoice[] function GetAllByTags(string Tags, string TagsSuppressed = "", bool RequireAll = true)
	String[] arg = SexLabUtil.MergeSplitTags(Tags, TagsSuppressed, RequireAll)
	String v = SelectVoiceByTagsA(none, arg)
	If (!v)
		return sslUtility.VoiceArray(0)
	EndIf
	sslBaseVoice[] ret = new sslBaseVoice[1]
	ret[0] = GetbyRegistrar(v)
	return ret
endFunction

sslBaseVoice function PickByRaceKey(string RaceKey)
	String v = SelectVoiceByRace(RaceKey)
	If (!v)
		return none
	EndIf
	return GetbyRegistrar(v)
endFunction

int function FindSaved(Actor ActorRef)
	return FindByRegistrar(GetSavedVoice(ActorRef))
endFunction

sslBaseVoice function GetSaved(Actor ActorRef)
	String v = GetSavedVoice(ActorRef)
	If (!v)
		return none
	EndIf
	return GetbyRegistrar(v)
endFunction

string function GetSavedName(Actor ActorRef)
	If (!ActorRef)
		return "$SSL_Random"
	EndIf
	String v = GetSavedVoice(ActorRef)
	If (!v)
		return "$SSL_Random"
	EndIf
	return v
endFunction

function SaveVoice(Actor ActorRef, sslBaseVoice Saving)
	StoreVoice(ActorRef, Saving.Registry)
endFunction

function ForgetVoice(Actor ActorRef)
	DeleteVoice(ActorRef)
endFunction

bool function HasCustomVoice(Actor ActorRef)
	return GetSavedVoice(ActorRef)
endFunction

; ------------------------------------------------------- ;
; --- Slotting Common                                 --- ;
; ------------------------------------------------------- ;

sslBaseVoice[] function GetList(bool[] Valid)
	sslBaseVoice[] Output = sslUtility.VoiceArray(PapyrusUtil.ClampInt(PapyrusUtil.CountBool(Valid, true), 0, 128))
	Alias[] aliases = GetAliases()
	int i = 0
	int input = 0
	int outputIdx = 0
	While (i < aliases.Length && input < Valid.Length && outputIdx < Output.Length)
		sslBaseVoice it = aliases[i] as sslBaseVoice
		If (it && it.Registered)
			If (Valid[input])
				Output[outputIdx] = it
				outputIdx += 1
			EndIf
			input += 1
		EndIf
		i += 1
	EndWhile
	If (outputIdx < Output.Length || outputIdx > 100)
		sslBaseVoice[] trimmed = sslUtility.VoiceArray(PapyrusUtil.ClampInt(outputIdx, 0, 100))
		int n = 0
		While (n < trimmed.Length)
			If (outputIdx > 100)
				int random = Utility.RandomInt(n, outputIdx - 1)
				sslBaseVoice swap = Output[n]
				Output[n] = Output[random]
				Output[random] = swap
			EndIf
			trimmed[n] = Output[n]
			n += 1
		EndWhile
		return trimmed
	EndIf
	return Output
endFunction

string[] function GetNames(sslBaseVoice[] SlotList)
	int i = SlotList.Length
	string[] Names = Utility.CreateStringArray(i)
	while i
		i -= 1
		if SlotList[i]
			Names[i] = SlotList[i].Name
		endIf
	endWhile
	if Names.Find("") != -1
		Names = PapyrusUtil.RemoveString(Names, "")
	endIf
	return Names
endFunction

; ------------------------------------------------------- ;
; --- Registry Access                                     ;
; ------------------------------------------------------- ;

sslBaseVoice function GetBySlot(int index)
	if index < 0 || index >= GetNumAliases()
		return none
	endIf
	return GetNthAlias(index) as sslBaseVoice
endFunction

bool function IsRegistered(string Registrar)
	return FindByRegistrar(Registrar) != -1
endFunction

int function FindByRegistrar(string Registrar)
	If (Registrar == "")
		return -1
	EndIf
	Alias[] aliases = GetAliases()
	int i = 0
	While (i < aliases.Length)
		sslBaseVoice it = aliases[i] as sslBaseVoice
		If (it && it.Registry == Registrar)
			return i
		EndIf
		i += 1
	EndWhile
	return -1
endFunction

int function FindByName(string FindName)
	return FindByRegistrar(FindName)
endFunction

sslBaseVoice function GetByName(string FindName)
	return GetBySlot(FindByName(FindName))
endFunction

sslBaseVoice function GetbyRegistrar(string Registrar)
	return GetBySlot(FindByRegistrar(Registrar))
endFunction

; ------------------------------------------------------- ;
; --- Object MCM Pagination                               ;
; ------------------------------------------------------- ;

int function PageCount(int perpage = 125)
	perpage = PapyrusUtil.ClampInt(perpage, 1, 128)
	return Math.Ceiling(Slotted as float / perpage as float)
endFunction

int function FindPage(string Registrar, int perpage = 125)
	perpage = PapyrusUtil.ClampInt(perpage, 1, 128)
	int i = Registry.Find(Registrar)
	if i != -1
		return (i / perpage) + 1
	endIf
	return -1
endFunction

string[] function GetSlotNames(int page = 1, int perpage = 125)
	return GetNames(GetSlots(page, perpage))
endfunction

sslBaseVoice[] function GetSlots(int page = 1, int perpage = 125)
	SyncBackend()
	perpage = PapyrusUtil.ClampInt(perpage, 1, 128)
	if page > PageCount(perpage) || page < 1
		return sslUtility.VoiceArray(0)
	endIf
	sslBaseVoice[] PageSlots
	int skippages = (page - 1) * perpage
	if page == PageCount(perpage)
		PageSlots = sslUtility.VoiceArray(Slotted - skippages)
	else
		PageSlots = sslUtility.VoiceArray(perpage)
	endIf
	Alias[] aliases = GetAliases()
	int i = 0
	int ii = 0
	While (i < aliases.Length && ii < PageSlots.Length)
		sslBaseVoice it = aliases[i] as sslBaseVoice
		If (it && it.Registered)
			If (skippages == 0)
				PageSlots[ii] = it
				ii += 1
			Else
				skippages -= 1
			EndIf
		EndIf
		i += 1
	EndWhile
	return PageSlots
endFunction

string[] function GetNormalSlotNames(bool WithRandom = false)
	sslBaseVoice[] all = GetSlots(1, 128)
	string[] Output = Utility.CreateStringArray(PapyrusUtil.ClampInt(GetCount(1) + (WithRandom as int), 0, 128))
	int n = 0
	If (WithRandom)
		Output[0] = "$SSL_Random"
		n = 1
	EndIf
	int i = 0
	While (i < all.Length && n < Output.Length)
		If (!all[i].Creature)
			Output[n] = all[i].Name
			n += 1
		EndIf
		i += 1
	EndWhile
	return Output
endFunction

int function GetCount(int flag = 0)
	if flag == 0
		return Slotted
	endIf
	sslBaseVoice[] all = GetSlots(1, 128)
	int count = 0
	int i = 0
	While (i < all.Length)
		If (all[i].Creature == (flag == -1))
			count += 1
		EndIf
		i += 1
	EndWhile
	return count
endFunction

; ------------------------------------------------------- ;
; --- Object Registration                                 ;
; ------------------------------------------------------- ;

int Function FindEmpty()
	Alias[] aliases = GetAliases()
	int i = 0
	While (i < aliases.Length)
		sslBaseVoice it = aliases[i] as sslBaseVoice
		If (it && !it.Registered)
			return i
		EndIf
		i += 1
	EndWhile
	return -1
EndFunction

bool RegisterLock = false
int function Register(string Registrar)
	if Registrar == ""
		return -1
	endIf
	while RegisterLock
		Utility.WaitMenuMode(0.5)
	endWhile
	RegisterLock = true
	SyncBackend()
	If (FindByRegistrar(Registrar) != -1 || FindEmpty() == -1)
		RegisterLock = false
		return -1
	EndIf
	If (!sslBaseVoice.InitializeVoiceObject(Registrar))
		RegisterLock = false
		return -1
	EndIf
	; Native IDs can reorder the aliases, so return the actual bound slot.
	SyncBackend()
	int ret = FindByRegistrar(Registrar)
	RegisterLock = false
	return ret
endFunction

sslBaseVoice function RegisterVoice(string Registrar, Form CallbackForm = none, ReferenceAlias CallbackAlias = none)
	; Return existing Voice
	if Registrar == "" || FindByRegistrar(Registrar) != -1
		return GetbyRegistrar(Registrar)
	endIf
	; Get free Voice slot
	int id = Register(Registrar)
	sslBaseVoice Slot = GetBySlot(id)
	if id != -1 && Slot != none
		Slot.Initialize()
		Slot.Registry = Slot.GOTTA_LOVE_PEOPLE_WHO_THINK_REGISTRATION_FUNCTIONS_ARE_JUST_DECORATION
		Slot.Registry = Registrar
		Slot.Enabled  = true
		sslObjectFactory.SendCallback(Registrar, id, CallbackForm, CallbackAlias)
	endIf
	return Slot
endFunction

function RegisterSlots()
endFunction

bool function UnregisterVoice(string Registrar)
	return false
endFunction

; ------------------------------------------------------- ;
; --- System Use Only                                 --- ;
; ------------------------------------------------------- ;

function Setup()
endFunction

function Log(string msg)
	sslLog.Log(msg)
endFunction

bool function TestSlots()
	return true
endFunction
