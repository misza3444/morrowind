local core = require('openmw.core')
local world = require('openmw.world')
local types = require('openmw.types')
local util = require('openmw.util')

local player
local enemies = {}
local state = {version = 1, phase = 'active', reward = 0, runs = 0}

local function broadcast()
    if player then
        player:sendEvent('EHRunState', {phase = state.phase, reward = state.reward, runs = state.runs})
    end
    for _, actor in ipairs(enemies) do
        if actor:isValid() and actor.count > 0 then actor:sendEvent('EHRunState',{phase = state.phase}) end
    end
end

local function beginRun()
    for _, actor in ipairs(enemies) do
        if actor:isValid() and actor.count > 0 then actor:remove() end
    end
    enemies = {}
    state.phase = 'active'
    player:teleport('Echo Arena', util.vector3(0, -650, 5), {rotation = util.transform.rotateZ(0)})
    player:sendEvent('EHReset')
    for _, info in ipairs({{'eh_guard',-300,0},{'eh_guard',300,100},{'eh_boss',0,650}}) do
        local actor = world.createObject(info[1])
        actor:teleport('Echo Arena',util.vector3(info[2],info[3],5))
        enemies[#enemies+1] = actor
    end
    broadcast()
end

local function onPlayerAdded(actor)
    player = actor
    if #enemies == 0 then
        beginRun()
    else
        broadcast()
    end
    -- Equipment is retained in saves, so create the blade only if missing.
    if #types.Actor.inventory(player):findAll('eh_blade') == 0 then
        world.createObject('eh_blade'):moveInto(player)
    end
end

local function onEnemyDefeated(data)
    if state.phase ~= 'active' then return end
    local alive = 0
    for _, actor in ipairs(enemies) do
        if actor:isValid() and actor ~= data.actor and not types.Actor.isDead(actor) then alive = alive + 1 end
    end
    if alive == 0 then
        state.phase, state.reward, state.runs = 'victory', state.reward + 1, state.runs + 1
        broadcast()
    end
end

return {
    engineHandlers = {
        onPlayerAdded = onPlayerAdded,
        onSave = function() return {state = state, enemies = enemies} end,
        onLoad = function(data)
            state = data.state or state
            enemies = data.enemies or {}
        end,
    },
    eventHandlers = {
        EHEnemyDefeated = onEnemyDefeated,
        EHPlayerDefeated = function()
            if state.phase == 'active' then state.phase = 'defeat'; broadcast() end
        end,
        EHRestart = function()
            if player then beginRun() end
        end,
    },
}
