local anim = require('openmw.animation')
local core = require('openmw.core')
local nearby = require('openmw.nearby')
local self = require('openmw.self')
local types = require('openmw.types')
local util = require('openmw.util')
local Actor = types.Actor
local active = self.recordId == 'eh_guard' or self.recordId == 'eh_boss'
local initialized, dead
local paused = false
local age,serial = 0,0
local state = 'chase'
local lastIncoming = {}
local boss = self.recordId == 'eh_boss'

local function hit(data)
    if not active or dead then return end
    local source = data.attacker and data.attacker.id or 'unknown'
    if data.serial and lastIncoming[source] == data.serial then return end
    lastIncoming[source] = data.serial
    local health = Actor.stats.dynamic.health(self)
    health.current = math.max(0,health.current-math.max(0,data.damage or 0))
    if health.current <= 0 then
        dead = true
        anim.clearAnimationQueue(self,true)
        core.sendGlobalEvent('EHEnemyDefeated',{actor = self.object})
    end
end

local function update(dt)
    if not active or dt <= 0 then return end
    if not initialized then self:enableAI(false); initialized = true end
    self.controls.movement,self.controls.sideMovement = 0,0
    self.controls.use = self.ATTACK_TYPE.NoAttack
    if dead or paused or Actor.isDead(self) then return end
    local player
    for _, actor in ipairs(nearby.actors) do
        if types.Player.objectIsInstance(actor) then player = actor; break end
    end
    if not player then return end
    local delta = player.position-self.position
    local distance = util.vector3(delta.x,delta.y,0):length()
    local desired = math.atan2(delta.x,delta.y)
    local current = self.rotation:getYaw()
    self.controls.yawChange = math.atan2(math.sin(desired-current),math.cos(desired-current))*math.min(1,dt*8)
    age = age+dt
    local range = boss and 260 or 165
    if state == 'chase' then
        if distance > range and distance < 1500 then
            self.controls.movement,self.controls.run = 1,true
        elseif distance <= range then
            state,age = 'windup',0
            anim.clearAnimationQueue(self,true)
            anim.playQueued(self,'attack1',{loops = 0,speed = boss and 0.65 or 0.85})
            player:sendEvent('EHEnemyWarning',{boss = boss})
        end
    elseif state == 'windup' and age >= (boss and 1.05 or 0.8) then
        local ray = nearby.castRay(self.position+util.vector3(0,0,45),player.position+util.vector3(0,0,50),{ignore = self})
        if distance <= range+35 and (not ray.hit or ray.hitObject == player) then
            serial = serial+1
            player:sendEvent('EHHit',{attacker = self.object,damage = boss and 28 or 12,serial = serial})
        end
        state,age = 'recover',0
    elseif state == 'recover' and age >= (boss and 1.35 or 1.0) then
        state,age = 'chase',0
        anim.clearAnimationQueue(self,true)
    end
end

return {
    engineHandlers = {
        onUpdate = update,
        onSave = function() return {dead = dead,serial = serial} end,
        onLoad = function(data) dead,serial = data.dead,data.serial or 0; initialized = false; state,age = 'chase',0 end,
    },
    eventHandlers = {EHHit = hit,EHRunState = function(data) paused = data.phase ~= 'active' end},
}
