local core = require('openmw.core')
local self = require('openmw.self')
local types = require('openmw.types')
local nearby = require('openmw.nearby')
local util = require('openmw.util')
local I = require('openmw.interfaces')
local anim = require('openmw.animation')
local camera = require('openmw.camera')
local storage = require('openmw.storage')
local rules = require('scripts.echo.combat')
local elapsed, delay, done = 0,0,false
local target, resumed
local passed = 0

local function check(condition,message)
    assert(condition,message)
end
local function pass(message)
    passed = passed+1
    print('EH_PASS '..passed..': '..message)
end
local function wait(seconds) coroutine.yield(seconds) end
local function health(actor) return types.Actor.stats.dynamic.health(actor).current end
local function arrange(options)
    target = nil
    core.sendGlobalEvent('EHTestArrange',options or {})
    for _=1,60 do
        wait(0.05)
        if target then break end
    end
    check(target,'Test arrangement did not complete')
    wait(0.15)
end
local function run()
    wait(1.5)
    if resumed then
        local snapshot = I.EchoPlayer.snapshot()
        check(snapshot.reward == 1,'Reward was not restored')
        check(snapshot.run == 'active','Run state was not restored')
        check(snapshot.nova > 0,'Ability cooldown was not restored')
        check(health(self) == 120,'Player HP was not restored')
        local count = 0
        for _,actor in ipairs(nearby.actors) do
            if (actor.recordId == 'eh_guard' or actor.recordId == 'eh_boss') and not types.Actor.isDead(actor) then count = count+1 end
        end
        check(count == 3,'Reload duplicated or lost enemies')
        pass('real save/load restores reward, cooldown, HP and three enemies')
        print('EH_TESTS_PASSED: '..passed..' checks')
        core.quit()
        return
    end

    check(self.cell.name == 'Echo Arena','Wrong starting cell')
    check(types.Actor.stats.dynamic.health(self).base == 120,'Player stats were not loaded')
    local floor = nearby.castRay(self.position+util.vector3(0,0,20),self.position-util.vector3(0,0,100),{ignore = self})
    check(floor.hit,'Arena floor has no physics collision')
    check(math.abs(floor.hitPos.z)<1,'Unexpected floor height: '..tostring(floor.hitPos))
    local count = 0
    for _,actor in ipairs(nearby.actors) do
        if actor.recordId == 'eh_guard' or actor.recordId == 'eh_boss' then count = count+1 end
    end
    check(count == 3,'Expected three arena enemies, got '..count)
    check(camera.getMode() == camera.MODE.ThirdPerson,'Third-person camera not active')
    local weapon = types.Actor.getEquipment(self,types.Actor.EQUIPMENT_SLOT.CarriedRight)
    check(weapon and weapon.recordId == 'eh_blade','Player blade is not equipped')
    pass('standalone scene, actual floor collision, player stats, enemies, camera')

    for _,fps in ipairs({30,60,120}) do
        local s = rules.new()
        local damage,hits = 0,0
        rules.attack(s)
        for _=1,fps*3 do
            if s.phase == 'attack' and s.combo < 3 and s.age > 0.15 then rules.attack(s) end
            rules.update(s,1/fps,function(event,info)
                if event == 'hit' then damage,hits = damage+info.damage,hits+1 end
            end)
        end
        check(damage == 74 and hits == 3,'Combo depends on frame rate: '..fps)
    end
    pass('combat timing produces three hits at 30 / 60 / 120 simulated FPS')

    arrange({x = 150})
    I.EchoPlayer.selectTarget()
    wait(0.45)
    check(I.EchoPlayer.snapshot().target == target.id,'Lock-on did not select the nearby enemy')
    local forward = self.rotation:apply(util.vector3(0,1,0))
    local direction = target.position-self.position
    direction = util.vector3(direction.x,direction.y,0):normalize()
    check(forward:dot(direction) > 0.9,'Lock-on did not turn the physical character towards target')
    I.EchoPlayer.selectTarget()
    check(not I.EchoPlayer.snapshot().target,'Lock-on did not release target')
    pass('target lock selects, turns the real character and releases')

    arrange()
    check(I.EchoPlayer.attack(),'Attack did not start')
    wait(0.18)
    check(anim.isPlaying(self,'weapontwohand'),'Actual player attack animation not playing')
    I.EchoPlayer.attack() -- buffer second hit
    wait(0.53)
    I.EchoPlayer.attack() -- buffer third hit
    wait(1.25)
    check(health(target) == 226,'Combo damage should be 74 once, got '..(300-health(target)))
    check(I.EchoPlayer.snapshot().phase == 'idle','Combo did not recover')
    pass('three animated attacks deal exactly 74 HP through actual engine events')

    arrange({y = -200})
    I.EchoPlayer.attack(); wait(0.7)
    check(health(target) == 300,'Out-of-range attack hit')
    pass('out-of-range attacks miss')

    arrange({wall = -560})
    I.EchoPlayer.attack(); wait(0.7)
    check(health(target) == 300,'Attack passed through a wall')
    pass('arena collision blocks melee damage through walls')

    arrange()
    check(I.EchoPlayer.dodge(1,0),'Dodge did not start')
    check(I.EchoPlayer.snapshot().invulnerable,'Dodge has no invulnerability window')
    self:sendEvent('EHHit',{damage = 20,serial = 1})
    wait(0.12)
    check(health(self) == 120,'Dodge did not prevent damage')
    wait(0.34)
    self:sendEvent('EHHit',{damage = 20,serial = 2})
    wait(0.12)
    check(health(self) == 100,'Damage remained disabled after dodge')
    check(types.Actor.stats.attributes.speed(self).base == 75,'Dodge speed was not restored')
    pass('dodge invulnerability ends and movement speed restores')

    arrange({wall = -420,y = 500})
    local before = self.position
    I.EchoPlayer.dodge(1,0)
    wait(0.6)
    check(self.position.y > before.y+20,'Dodge did not move the physical character')
    check(self.position.y < -450,'Dodge passed through physical wall: '..self.position.y)
    pass('dodge moves the real character and respects wall collision')

    arrange()
    check(I.EchoPlayer.skill('cleave'),'Cleave did not start')
    wait(0.65)
    check(health(target) == 258,'Cleave did not deal 42 damage')
    check(not I.EchoPlayer.skill('cleave'),'Cooldown allowed immediate ability reuse')
    check(I.EchoPlayer.skill('nova'),'Nova did not start')
    wait(0.65)
    check(health(target) == 228,'Nova did not deal 30 damage')
    pass('both abilities deal damage and enforce cooldowns')

    core.sendGlobalEvent('EHTestKillAll',{})
    wait(0.4)
    check(I.EchoPlayer.snapshot().run == 'victory','No victory after defeating all enemies')
    check(I.EchoPlayer.snapshot().reward == 1,'Victory reward not awarded once')
    core.sendGlobalEvent('EHEnemyDefeated',{actor = target})
    wait(0.2)
    check(I.EchoPlayer.snapshot().reward == 1,'Duplicate death duplicated rewards')
    pass('victory awards one reward despite repeated death notifications')

    core.sendGlobalEvent('EHRestart',{})
    wait(0.6)
    check(I.EchoPlayer.snapshot().run == 'active' and health(self) == 120,'Restart failed')
    self:sendEvent('EHHit',{damage = 1000,serial = 100})
    wait(0.25)
    check(I.EchoPlayer.snapshot().run == 'defeat','Defeat state did not start')
    core.sendGlobalEvent('EHRestart',{})
    wait(0.5)
    check(health(self) == 120 and I.EchoPlayer.snapshot().reward == 1,'Defeat restart changed progress')
    pass('victory and defeat can restart without losing earned progress')

    -- A real native save is loaded in the same engine process by the menu context.
    arrange({y = 500})
    I.EchoPlayer.skill('nova')
    storage.playerSection('EchoEngineTests'):set('save',true)
    print('EH_CHECKPOINT: requesting native save and reload')
    while true do wait(0.1) end
end

local routine = coroutine.create(run)
return {
    engineHandlers = {
        onUpdate = function(dt)
            if done or dt <= 0 then return end
            elapsed,delay = elapsed+dt,delay-dt
            if delay > 0 then return end
            local ok,result = coroutine.resume(routine)
            if not ok then
                done = true
                print('EH_TESTS_FAILED: '..tostring(result))
                core.quit()
            else delay = result or 0 end
        end,
        onSave = function() return {resume = true,passed = passed} end,
        onLoad = function(data)
            resumed,passed = data.resume,data.passed or 0
            elapsed,delay,done = 0,0,false
            routine = coroutine.create(run)
        end,
    },
    eventHandlers = {EHTestArranged = function(data) target = data.target end},
}
