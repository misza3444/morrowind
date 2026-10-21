local menu = require('openmw.menu')
local input = require('openmw.input')
local function checkpoint()
    local directory = menu.getCurrentSaveDir()
    if not directory then return end
    local selected,creation
    for slot,info in pairs(menu.getSaves(directory)) do
        if info.description == 'Łowca Echa — punkt zapisu' and (not creation or info.creationTime > creation) then
            selected,creation = slot,info.creationTime
        end
    end
    return selected,directory
end
return {engineHandlers = {onKeyPress = function(key)
    if menu.getState() ~= menu.STATE.Running then return end
    if key.code == input.KEY.F6 then
        local slot = checkpoint()
        menu.saveGame('Łowca Echa — punkt zapisu',slot)
    elseif key.code == input.KEY.F7 then
        local slot,directory = checkpoint()
        if slot then menu.loadGame(directory,slot) end
    end
end}}
