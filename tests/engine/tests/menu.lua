local core = require('openmw.core')
local menu = require('openmw.menu')
local storage = require('openmw.storage')
local state = storage.playerSection('EchoEngineTests')
state:reset()
local age = 0
return {engineHandlers = {onFrame = function(dt)
    if menu.getState() ~= menu.STATE.Running then return end
    if state:get('save') then
        state:set('save',false)
        menu.saveGame('Echo engine integration checkpoint')
        age = 0
        state:set('loading',true)
    elseif state:get('loading') then
        age = age+dt
        if age > 0.5 then
            state:set('loading',false)
            local directory = menu.getCurrentSaveDir()
            for slot,info in pairs(menu.getSaves(directory)) do
                if info.description == 'Echo engine integration checkpoint' then
                    menu.loadGame(directory,slot)
                    return
                end
            end
            error('Integration checkpoint was not written')
        end
    end
end}}
