local self = require('openmw.self')
local types = require('openmw.types')
return {eventHandlers = {EHTestHealth = function(value)
    local health = types.Actor.stats.dynamic.health(self)
    health.base,health.current = value,value
end}}
