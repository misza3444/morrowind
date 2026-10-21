local world = require('openmw.world')
local types = require('openmw.types')
local util = require('openmw.util')
local barrier
return {eventHandlers = {
    EHTestArrange = function(data)
        local player = world.players[1]
        if barrier and barrier:isValid() and barrier.count > 0 then barrier:remove() end
        barrier = nil
        local target
        for _,actor in ipairs(world.activeActors) do
            if actor.recordId == 'eh_guard' or actor.recordId == 'eh_boss' then
                actor:sendEvent('EHRunState',{phase = 'test'})
                if not target and actor.recordId == 'eh_guard' then
                    target = actor
                else
                    actor:teleport('Echo Arena',util.vector3(850,850,5))
                end
            end
        end
        assert(target,'No test target')
        player:teleport('Echo Arena',util.vector3(0,-650,5),{rotation = util.transform.rotateZ(0)})
        player:sendEvent('EHReset')
        target:teleport('Echo Arena',util.vector3(data.x or 0,data.y or -470,5))
        target:sendEvent('EHTestHealth',300)
        if data.wall then
            barrier = world.createObject('eh_wall')
            barrier:teleport('Echo Arena',util.vector3(0,data.wall,0))
        end
        player:sendEvent('EHTestArranged',{target = target})
    end,
    EHTestKillAll = function()
        for _,actor in ipairs(world.activeActors) do
            if actor.recordId == 'eh_guard' or actor.recordId == 'eh_boss' then
                actor:sendEvent('EHHit',{attacker = world.players[1],damage = 10000,serial = 9000})
            end
        end
    end,
}}
