local anim = require('openmw.animation')
local camera = require('openmw.camera')
local core = require('openmw.core')
local input = require('openmw.input')
local I = require('openmw.interfaces')
local nearby = require('openmw.nearby')
local self = require('openmw.self')
local types = require('openmw.types')
local util = require('openmw.util')
local rules = require('scripts.echo.combat')
local hud = require('scripts.echo.hud')
local Actor = types.Actor

local combat = rules.new()
local run = {phase = 'active',reward = 0}
local target, initialized
local equipmentReady = false
local notice, noticeTime = '', 0
local hudTime = 0
local baseSpeed = 75
local dodgeDirection = {forward = 1, side = 0}
local hitSerial = 0
local lastIncoming = {}

local function playable()
    return not core.isWorldPaused() and run.phase == 'active'
end

local function visible(actor)
    local from = self.position + util.vector3(0,0,55)
    local to = actor.position + util.vector3(0,0,45)
    local result = nearby.castRay(from,to,{ignore = self})
    return not result.hit or result.hitObject == actor
end

local function hostile(actor)
    return actor ~= self and actor:isValid() and not Actor.isDead(actor)
        and (actor.recordId == 'eh_guard' or actor.recordId == 'eh_boss')
end

local function announce(value)
    notice, noticeTime = value, 1.2
end

local function selectTarget()
    if target then target = nil; return end
    local distance = 1500
    for _, actor in ipairs(nearby.actors) do
        if hostile(actor) and visible(actor) then
            local d = (actor.position-self.position):length()
            if d < distance then target,distance = actor,d end
        end
    end
end

local function swing(info)
    hitSerial = hitSerial + 1
    local forward = self.rotation:apply(util.vector3(0,1,0))
    for _, actor in ipairs(nearby.actors) do
        if hostile(actor) then
            local delta = actor.position-self.position
            local flat = util.vector3(delta.x,delta.y,0)
            local distance = flat:length()
            local dot = distance > 0 and forward:dot(flat)/distance or 1
            if distance <= (info.range or 230) and dot >= (info.cone or 0.25) and visible(actor) then
                actor:sendEvent('EHHit',{attacker = self.object, damage = info.damage, serial = hitSerial})
            end
        end
    end
end

local function playAttack(info)
    anim.clearAnimationQueue(self,true)
    anim.playQueued(self,'weapontwohand',{loops = 0, speed = 1.35,
        startKey = info.key..' start',stopKey = info.key..' large follow stop'})
end

local function attack()
    if not playable() then return false end
    local began = rules.attack(combat)
    if began then playAttack(rules.attacks[1]) end
    return began
end

local function dodge(forward,side)
    if not playable() or not rules.dodge(combat) then return false end
    anim.clearAnimationQueue(self,true)
    dodgeDirection = {forward = forward or 1, side = side or 0}
    local length = math.sqrt(dodgeDirection.forward^2+dodgeDirection.side^2)
    if length < 0.1 then dodgeDirection.forward,length = 1,1 end
    dodgeDirection.forward = dodgeDirection.forward/length
    dodgeDirection.side = dodgeDirection.side/length
    Actor.stats.attributes.speed(self).base = baseSpeed * 6
    announce('UNIK')
    return true
end

local function skill(key)
    if not playable() or not rules.skill(combat,key) then return false end
    swing(rules.skills[key])
    anim.clearAnimationQueue(self,true)
    anim.playQueued(self,'spellcast',{loops = 0,speed = 2.7,startKey = 'self start',stopKey = 'self stop'})
    announce(key == 'nova' and 'NOVA ECHA' or 'ROZCIĘCIE')
    return true
end

local function reset()
    combat = rules.new()
    target, lastIncoming = nil, {}
    Actor.stats.attributes.speed(self).base = baseSpeed
    local hp = Actor.stats.dynamic.health(self)
    hp.current = hp.base
    anim.clearAnimationQueue(self,true)
end

local function onFrame(dt)
    if not initialized or core.isWorldPaused() then return end
    self.controls.use = self.ATTACK_TYPE.NoAttack
    self.controls.jump = false
    I.Controls.overrideMovementControls(combat.phase ~= 'idle' or run.phase ~= 'active')
    if run.phase ~= 'active' then
        self.controls.movement,self.controls.sideMovement = 0,0
    elseif combat.phase == 'dodge' then
        self.controls.movement,self.controls.sideMovement = dodgeDirection.forward,dodgeDirection.side
        self.controls.run = true
    elseif combat.phase ~= 'idle' then
        self.controls.movement,self.controls.sideMovement = 0,0
    end
    if target then
        if not hostile(target) or (target.position-self.position):length() > 1800 then
            target = nil
        else
            local delta = target.position-self.position
            local desired = math.atan2(delta.x,delta.y)
            local current = self.rotation:getYaw()
            local difference = math.atan2(math.sin(desired-current),math.cos(desired-current))
            self.controls.yawChange = difference*math.min(1,dt*12)
            camera.setYaw(current+self.controls.yawChange)
            camera.setPitch(math.rad(10))
        end
    end
end

local function onUpdate(dt)
    if dt <= 0 then return end
    if not equipmentReady and #Actor.inventory(self):findAll('eh_blade') > 0 then
        local equipment = Actor.getEquipment(self)
        equipment[Actor.EQUIPMENT_SLOT.CarriedRight] = 'eh_blade'
        Actor.setEquipment(self,equipment)
        Actor.setStance(self,Actor.STANCE.Weapon)
        equipmentReady = true
    end
    if not initialized then
        I.Controls.overrideCombatControls(true)
        I.Controls.overrideUiControls(true)
        I.Camera.disableStandingPreview('Echo')
        I.Camera.disableModeControl('Echo')
        I.Camera.disableThirdPersonOffsetControl('Echo')
        I.UI.setHudVisibility(false)
        camera.setMode(camera.MODE.ThirdPerson)
        camera.setPreferredThirdPersonDistance(260)
        camera.setFocalPreferredOffset(util.vector2(22,8))
        camera.setPitch(math.rad(10))
        Actor.setStance(self,Actor.STANCE.Weapon)
        initialized = true
        print('EH_READY: Echo Arena player initialized')
    end
    local previous = combat.phase
    rules.update(combat,dt,function(event,info)
        if event == 'hit' then swing(info)
        elseif event == 'animation' then playAttack(info)
        elseif event == 'idle' then anim.clearAnimationQueue(self,true) end
    end)
    if previous == 'dodge' and combat.phase ~= 'dodge' then
        Actor.stats.attributes.speed(self).base = baseSpeed
    end
    noticeTime = math.max(0,noticeTime-dt)
    if noticeTime == 0 then notice = '' end
    hudTime = hudTime+dt
    if hudTime >= 0.08 then
        hudTime = 0
        local health = Actor.stats.dynamic.health(self)
        local targetData
        if target and hostile(target) then
            local hp = Actor.stats.dynamic.health(target)
            targetData = {name = types.Creature.record(target).name,hp = hp.current,maxHp = hp.base}
        end
        hud.update({hp = health.current,maxHp = health.base,cooldowns = combat.cooldowns,
            reward = run.reward,phase = run.phase,target = targetData,notice = notice})
    end
end

local function onHit(data)
    if not playable() or rules.invulnerable(combat) then return end
    local source = data.attacker and data.attacker.id or 'unknown'
    if data.serial and lastIncoming[source] == data.serial then return end
    lastIncoming[source] = data.serial
    local hp = Actor.stats.dynamic.health(self)
    -- Keep the player alive for the defeat/restart screen; native death is not this game's loop.
    hp.current = math.max(1,hp.current-math.max(0,data.damage or 0))
    announce('TRAFIENIE')
    if hp.current <= 1 then core.sendGlobalEvent('EHPlayerDefeated',{}) end
end

return {
    interfaceName = 'EchoPlayer',
    interface = {attack = attack,dodge = dodge,skill = skill,selectTarget = selectTarget,
        snapshot = function() return {phase = combat.phase,combo = combat.combo,invulnerable = rules.invulnerable(combat),
            cleave = combat.cooldowns.cleave,nova = combat.cooldowns.nova,run = run.phase,reward = run.reward,
            target = target and target.id or nil} end},
    engineHandlers = {
        onFrame = onFrame,onUpdate = onUpdate,
        onMouseButtonPress = function(button) if button == 1 then attack() end end,
        onKeyPress = function(key)
            if core.isWorldPaused() then return end
            if key.symbol == 'q' then skill('cleave')
            elseif key.symbol == 'e' then skill('nova')
            elseif key.symbol == 'r' then core.sendGlobalEvent('EHRestart',{})
            elseif key.code == input.KEY.Tab then selectTarget()
            elseif key.code == input.KEY.Space then
                local forward = (input.isKeyPressed(input.KEY.W) and 1 or 0)-(input.isKeyPressed(input.KEY.S) and 1 or 0)
                local side = (input.isKeyPressed(input.KEY.D) and 1 or 0)-(input.isKeyPressed(input.KEY.A) and 1 or 0)
                dodge(forward,side)
            end
        end,
        onSave = function()
            return {version = 1,cooldowns = combat.cooldowns,dodgeCooldown = combat.dodgeCooldown,
                run = run,hitSerial = hitSerial,baseSpeed = baseSpeed}
        end,
        onLoad = function(data)
            combat = rules.new()
            combat.cooldowns = data.cooldowns or combat.cooldowns
            combat.dodgeCooldown = data.dodgeCooldown or 0
            run = data.run or run
            hitSerial,baseSpeed = data.hitSerial or 0,data.baseSpeed or 75
            Actor.stats.attributes.speed(self).base = baseSpeed
            initialized,equipmentReady = false,false
            hud.destroy()
        end,
    },
    eventHandlers = {EHHit = onHit,EHReset = reset,EHRunState = function(data) run = data end,
        EHEnemyWarning = function(data) announce(data.boss and 'WŁADCA SZYKUJE ATAK' or 'UWAGA — ATAK') end},
}
